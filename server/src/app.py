#!/usr/bin/env python3
from __future__ import annotations

import datetime
import importlib.util
import socket
import threading
from pathlib import Path
from typing import Optional


LOG_LOCK = threading.Lock()


def load_server_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "resource" / "config.py"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    spec = importlib.util.spec_from_file_location("server_resource_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load config module: {config_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SERVER_CONFIG


def write_log(log_path: Path, client_ip: str, client_port: int, request_line: str, status: int) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f'{timestamp} {client_ip}:{client_port} "{request_line}" {status}\n'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with LOG_LOCK:
        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(log_line)


def read_request_header(
    conn: socket.socket, buffer_size: int, max_header_bytes: int
) -> tuple[bytes, Optional[str]]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(buffer_size)
        if not chunk:
            break
        data += chunk
        if len(data) > max_header_bytes:
            return data, "Header too large"
    if not data:
        return data, "Empty request"
    return data, None


def parse_request_line(raw_header: bytes) -> tuple[Optional[str], Optional[tuple[str, str, str]]]:
    try:
        header_text = raw_header.decode("iso-8859-1", errors="replace")
    except Exception:
        return "Decode failed", None

    lines = header_text.split("\r\n")
    if not lines or not lines[0].strip():
        return "Missing request line", None

    parts = lines[0].split()
    if len(parts) != 3:
        return "Malformed request line", None

    method, path, version = parts
    return None, (method, path, version)


def build_response(status_code: int, reason: str, body: str) -> bytes:
    body_bytes = body.encode("utf-8")
    headers = [
        f"HTTP/1.1 {status_code} {reason}",
        "Content-Type: text/plain; charset=utf-8",
        f"Content-Length: {len(body_bytes)}",
        "Connection: close",
        "",
        "",
    ]
    return "\r\n".join(headers).encode("ascii") + body_bytes


def handle_client(conn: socket.socket, client: tuple[str, int], cfg: dict, log_path: Path) -> None:
    conn.settimeout(5)
    request_line_for_log = "<unparsed>"
    status = 400
    try:
        raw_header, read_error = read_request_header(conn, cfg["buffer_size"], cfg["max_header_bytes"])
        if read_error is not None:
            response = build_response(400, "Bad Request", f"Bad Request: {read_error}\n")
            conn.sendall(response)
            write_log(log_path, client[0], client[1], request_line_for_log, 400)
            return

        parse_error, parsed = parse_request_line(raw_header)
        header_text = raw_header.decode("iso-8859-1", errors="replace")
        print(f"\n--- Request from {client[0]}:{client[1]} ---")
        print(header_text)
        print("--- End Request ---\n")

        if parse_error is not None or parsed is None:
            response = build_response(400, "Bad Request", f"Bad Request: {parse_error}\n")
            conn.sendall(response)
            write_log(log_path, client[0], client[1], request_line_for_log, 400)
            return

        method, path, version = parsed
        request_line_for_log = f"{method} {path} {version}"
        status = 200
        body = "First stage server is running. Request received and logged.\n"
        conn.sendall(build_response(200, "OK", body))
        write_log(log_path, client[0], client[1], request_line_for_log, 200)
    except socket.timeout:
        write_log(log_path, client[0], client[1], request_line_for_log, status)
    except Exception as exc:
        print(f"[Worker Error] {client[0]}:{client[1]} -> {exc}")
        write_log(log_path, client[0], client[1], request_line_for_log, status)
    finally:
        conn.close()


def main() -> int:
    try:
        cfg = load_server_config()
    except Exception as exc:
        print(f"Error: failed to load config -> {exc}")
        return 1

    project_root = Path(__file__).resolve().parents[2]
    log_path = Path(cfg["log_path"])
    if not log_path.is_absolute():
        log_path = project_root / log_path

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((cfg["host"], cfg["port"]))
        server_socket.listen(50)
    except OSError as exc:
        print(f"Error: unable to start server on {cfg['host']}:{cfg['port']} -> {exc}")
        return 1

    print(f"First-stage server listening on {cfg['host']}:{cfg['port']}")
    print(f"Logging to {log_path}")

    try:
        while True:
            conn, client = server_socket.accept()
            worker = threading.Thread(
                target=handle_client,
                args=(conn, client, cfg, log_path),
                daemon=True,
            )
            worker.start()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    finally:
        server_socket.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
