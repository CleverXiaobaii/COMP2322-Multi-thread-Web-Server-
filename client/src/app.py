#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import socket
from pathlib import Path


def build_request(
    cfg: dict,
    path: str,
    method: str = "GET",
    connection: str = "close",
    if_modified_since: str | None = None,
) -> bytes:
    version = cfg["http_version"]
    host = cfg["host"]
    user_agent = cfg["user_agent"]

    request_lines = [
        f"{method} {path} {version}",
        f"Host: {host}",
        f"User-Agent: {user_agent}",
        "Accept: */*",
        f"Connection: {connection}",
    ]

    if if_modified_since:
        request_lines.append(f"If-Modified-Since: {if_modified_since}")

    request_lines.extend(["", ""])
    return "\r\n".join(request_lines).encode("ascii")


def receive_response(sock: socket.socket, buffer_size: int = 4096) -> bytes:
    return receive_response_with_method(sock, buffer_size, method="GET")


def receive_response_with_method(sock: socket.socket, buffer_size: int = 4096, method: str = "GET") -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(buffer_size)
        if not chunk:
            return data
        data += chunk

    header_part, body_part = data.split(b"\r\n\r\n", 1)
    if method.upper() == "HEAD":
        # HEAD 响应没有 body，直接返回 header
        return header_part + b"\r\n\r\n"

    header_text = header_part.decode("iso-8859-1", errors="replace")
    content_length = 0
    for line in header_text.split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":", 1)[1].strip())
            except ValueError:
                content_length = 0
            break
    # ...existing code...
    # 读取 body
    body = body_part
    while len(body) < content_length:
        chunk = sock.recv(buffer_size)
        if not chunk:
            break
        body += chunk
    return header_part + b"\r\n\r\n" + body


# 新增：请求 /logo 并保存图片
def fetch_logo_and_save(cfg: dict):
    import os
    path = "/logo"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((cfg["host"], cfg["port"]))
        req = build_request(cfg, path, method="GET")
        sock.sendall(req)
        resp = receive_response(sock)
    # 解析响应头和体
    header, body = resp.split(b"\r\n\r\n", 1)
    status_line = header.split(b"\r\n", 1)[0].decode()
    if "200" not in status_line:
        print("[ERROR] 获取 logo 失败：", status_line)
        return
    # 保存图片
    save_dir = Path(__file__).parents[1] / "resource"
    os.makedirs(save_dir, exist_ok=True)
    save_path = save_dir / "logo.jpg"
    with open(save_path, "wb") as f:
        f.write(body)
    print(f"[INFO] logo.jpg 已保存到 {save_path}")


def print_response(raw_response: bytes) -> None:
    text = raw_response.decode("iso-8859-1", errors="replace")
    split_index = text.find("\r\n\r\n")
    status_line = text.split("\r\n", 1)[0] if text else ""
    if status_line.startswith("HTTP/"):
        parts = status_line.split(" ", 2)
        if len(parts) >= 3:
            print(f"[Client] HTTP Status: {parts[1]} {parts[2]}")
        else:
            print(f"[Client] HTTP Status: {status_line}")
    if split_index != -1:
        print(text[split_index + 4:])
    else:
        print(text)


def send_request(
    cfg: dict,
    path: str,
    method: str = "GET",
    connection: str = "close",
    sock: socket.socket | None = None,
    if_modified_since: str | None = None,
) -> tuple[bool, bytes]:
    host = cfg["host"]
    port = cfg["port"]
    timeout = cfg["timeout"]

    if sock is not None:
        request_data = build_request(
            cfg,
            path=path,
            method=method,
            connection=connection,
            if_modified_since=if_modified_since,
        )
        sock.sendall(request_data)
        response = receive_response_with_method(sock, method=method)
        return True, response

    try:
        with socket.create_connection((host, port), timeout=timeout) as temp_sock:
            temp_sock.settimeout(timeout)
            request_data = build_request(
                cfg,
                path=path,
                method=method,
                connection=connection,
                if_modified_since=if_modified_since,
            )
            temp_sock.sendall(request_data)
            response = receive_response_with_method(temp_sock, method=method)
            return True, response
    except Exception as exc:
        print(f"[Client] Request failed: {exc}")
        return False, b""


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "client" / "src" / "config.py"
    spec = importlib.util.spec_from_file_location("client_src_config", config_path)
    if spec is None or spec.loader is None:
        print("config加载失败")
        return 1
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg = module.CLIENT_CONFIG

    host = cfg["host"]
    port = cfg["port"]
    timeout = cfg["timeout"]
    print(f"[Client] Connected to {host}:{port}\n")

    mode_input = input("[Client] Connection mode (keep-alive/close) [keep-alive]: ").strip().lower()
    connection_mode = "close" if mode_input == "close" else "keep-alive"
    print(f"[Client] Mode: {connection_mode}\n")

    persistent_sock: socket.socket | None = None
    if connection_mode == "keep-alive":
        persistent_sock = socket.create_connection((host, port), timeout=timeout)
        persistent_sock.settimeout(timeout)

    ok, response = send_request(
        cfg,
        "/init",
        "GET",
        connection=connection_mode,
        sock=persistent_sock,
    )
    if not ok:
        return 1
    print_response(response)

    try:
        while True:
            cmd = input("\n> ").strip()
            if not cmd:
                continue

            if cmd.lower() in ("quit", "exit"):
                break

            if_modified_since = None
            command_text = cmd
            if "|" in cmd:
                command_text, header_value = cmd.split("|", 1)
                command_text = command_text.strip()
                if_modified_since = header_value.strip() or None

            parts = command_text.split()
            if len(parts) < 2:
                print("[Client] Invalid format. Use: METHOD PATH (e.g., GET /data)")
                continue

            method = parts[0].upper()
            path = parts[1]
            # 如果是 GET /logo，调用专用保存逻辑
            if method == "GET" and path == "/logo":
                fetch_logo_and_save(cfg)
            else:
                ok, response = send_request(
                    cfg,
                    path,
                    method,
                    connection=connection_mode,
                    sock=persistent_sock,
                    if_modified_since=if_modified_since,
                )
                if ok:
                    print_response(response)
    except KeyboardInterrupt:
        pass
    if persistent_sock is not None:
        persistent_sock.close()
    print("\n[Client] Disconnected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
