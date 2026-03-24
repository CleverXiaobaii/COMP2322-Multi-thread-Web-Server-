#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import socket
from pathlib import Path


def build_request(cfg: dict) -> bytes:
    method = cfg["method"]
    path = cfg["path"]
    version = cfg["http_version"]
    host = cfg["host"]
    user_agent = cfg["user_agent"]

    request_lines = [
        f"{method} {path} {version}",
        f"Host: {host}",
        f"User-Agent: {user_agent}",
        "Accept: */*",
        "Connection: close",
        "",
        "",
    ]
    return "\r\n".join(request_lines).encode("ascii")


def receive_all(sock: socket.socket, buffer_size: int = 4096) -> bytes:
    chunks = []
    while True:
        data = sock.recv(buffer_size)
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def print_response(raw_response: bytes) -> None:
    text = raw_response.decode("iso-8859-1", errors="replace")
    split_index = text.find("\r\n\r\n")
    if split_index == -1:
        print("[Client] Raw response (no header separator found):")
        print(text)
        return

    header_text = text[:split_index]
    body_text = text[split_index + 4 :]
    header_lines = header_text.split("\r\n")
    status_line = header_lines[0] if header_lines else "<missing status line>"

    print("\n[Client] Response Status:")
    print(status_line)
    print("\n[Client] Response Headers:")
    for line in header_lines[1:]:
        print(line)
    print("\n[Client] Response Body:")
    print(body_text)


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "client" / "src" / "config.py"
    try:
        spec = importlib.util.spec_from_file_location("client_src_config", config_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("invalid spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cfg = module.CLIENT_CONFIG
    except Exception:
        print("config加载失败")
        return 1

    host = cfg["host"]
    port = cfg["port"]
    timeout = cfg["timeout"]
    request_line = f"{cfg['method']} {cfg['path']} {cfg['http_version']}"

    print(f"[Client] Target: {host}:{port}")
    print(f"[Client] Request: {request_line}")

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            request_data = build_request(cfg)
            sock.sendall(request_data)
            response = receive_all(sock)
    except Exception as exc:
        print(f"[Client] Request failed: {exc}")
        return 1

    print_response(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
