from __future__ import annotations

import socket
from typing import Optional


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


def parse_headers(raw_header: bytes) -> dict[str, str]:
    header_text = raw_header.decode("iso-8859-1", errors="replace")
    lines = header_text.split("\r\n")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


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


def build_response_with_headers(
    status_code: int, reason: str, body: str, extra_headers: Optional[list[str]] = None
) -> bytes:
    body_bytes = body.encode("utf-8")
    headers = [
        f"HTTP/1.1 {status_code} {reason}",
        "Content-Type: application/json; charset=utf-8",
        f"Content-Length: {len(body_bytes)}",
        "Connection: close",
    ]
    if extra_headers:
        headers.extend(extra_headers)
    headers.extend(["", ""])
    return "\r\n".join(headers).encode("ascii") + body_bytes
