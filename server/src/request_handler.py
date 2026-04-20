from __future__ import annotations

import json
import socket
from pathlib import Path

from http_utils import (
    build_response,
    build_response_with_headers,
    parse_http_request,
)

from storage_utils import format_last_modified, is_not_modified, load_data, read_instruction, write_log



def handle_get(path: str, headers: dict[str, str], data_path: Path, init_path: Path) -> tuple[int, bytes]:
    # Unified GET/HEAD logic, HEAD only strips body.
    if path == "/init":
        instruction = read_instruction(init_path)
        body = instruction if instruction.endswith("\n") else instruction + "\n"
        return 200, build_response(200, "OK", body)

    if ".." in path:
        return 403, build_response(403, "Forbidden", "Forbidden\n")

    if path == "/logo":
        logo_path = Path(__file__).parent.parent / "resource" / "logo.jpg"
        if not logo_path.exists():
            return 404, build_response(404, "File Not Found", "File Not Found\n")
        last_modified = format_last_modified(logo_path)
        if headers.get("__method__", "GET").upper() in ("GET", "HEAD"):
            if_modified_since = headers.get("if-modified-since")
            if if_modified_since:
                from email.utils import parsedate_to_datetime
                since = parsedate_to_datetime(if_modified_since)
                mtime = int(logo_path.stat().st_mtime)
                if mtime <= int(since.timestamp()):
                    resp_headers = [f"Last-Modified: {last_modified}"]
                    return 304, build_response_with_headers(304, "Not Modified", "", resp_headers)
        with open(logo_path, "rb") as f:
            img_data = f.read()
        resp_headers = [
            "Content-Type: image/jpeg",
            f"Content-Length: {len(img_data)}",
            f"Last-Modified: {last_modified}"
        ]
        return 200, build_response_with_headers(200, "OK", img_data, resp_headers)

    if not path.startswith("/data"):
        return 404, build_response(404, "File Not Found", "File Not Found\n")

    if_modified_since = headers.get("if-modified-since")
    last_modified = format_last_modified(data_path)
    if if_modified_since and is_not_modified(data_path, if_modified_since):
        return 304, build_response_with_headers(304, "Not Modified", "", [f"Last-Modified: {last_modified}"])

    data = load_data(data_path)
    if path == "/data":
        payload = json.dumps(data, ensure_ascii=False)
        return 200, build_response_with_headers(200, "OK", payload + "\n", [f"Last-Modified: {last_modified}"])

    path_parts = path.split("/", 2)
    if len(path_parts) != 3 or not path_parts[2]:
        return 400, build_response(400, "Bad Request", "Bad Request\n")

    key = path_parts[2]
    if key not in data:
        return 404, build_response(404, "File Not Found", "File Not Found\n")

    payload = json.dumps({key: data[key]}, ensure_ascii=False)
    return 200, build_response_with_headers(200, "OK", payload + "\n", [f"Last-Modified: {last_modified}"])


def handle_head(path: str, headers: dict[str, str], data_path: Path, init_path: Path) -> tuple[int, bytes]:
    # HEAD reuses GET logic, only strips body.
    headers = dict(headers)
    headers["__method__"] = "HEAD"
    status, response = handle_get(path, headers, data_path, init_path)
    # Strip body, keep only header
    if b"\r\n\r\n" in response:
        header_end = response.index(b"\r\n\r\n") + 4
        response = response[:header_end]
    return status, response



def preprocess_request(
    conn: socket.socket,
    client: tuple[str, int],
    cfg: dict,
) -> tuple[bool, str, str, dict[str, str], str, int, bytes]:
    request_line_for_log = "<unparsed>"
    
    try:
        #  Call the new parse_http_request function (only parsing)
        method, path, version, headers, raw_header = parse_http_request(
            conn, cfg["buffer_size"], cfg["max_header_bytes"]
        )
        
        # Print request
        header_text = raw_header.decode("iso-8859-1", errors="replace")
        print(f"\n--- Request from {client[0]}:{client[1]} ---")
        print(header_text)
        print("--- End Request ---\n")
        
        # Generate log line
        request_line_for_log = f"{method} {path} {version}"
        
        return True, method, path, headers, request_line_for_log, 0, b""
        
    except Exception as exc:
        print(f"[parse_http_request error] {exc}")
        if str(exc) == "Empty request":
            return False, "", "", {}, request_line_for_log, 0, b""
        # Build 400 error response
        response = build_response(400, "Bad Request", f"Bad Request: {str(exc)}\n")
        return False, "", "", {}, request_line_for_log, 400, response


def handle_client(
    conn: socket.socket,
    client: tuple[str, int],
    cfg: dict,
    log_path: Path,
    data_path: Path,
    init_path: Path,
) -> None:
    conn.settimeout(60)
    try:
        while True:
            ok, method, path, headers, request_line_for_log, status, response = preprocess_request(conn, client, cfg)
            if not ok:
                if status == 0:
                    return
                conn.sendall(response)
                write_log(log_path, client[0], client[1], request_line_for_log, status,)
                return

            wants_keep_alive = headers.get("connection", "").lower() == "keep-alive"
            response_connection = "keep-alive" if wants_keep_alive else "close"


            # Only log If-Modified-Since for GET/HEAD /logo, otherwise "-"
            if method == "GET":
                status, response = handle_get(path, headers, data_path, init_path)
                last_modified = format_last_modified(data_path)
                if method == "GET" and path == "/logo" and "if-modified-since" in headers:
                    if_modified_since = headers["if-modified-since"]
                else:
                    if_modified_since = "-"
            elif method == "HEAD":
                status, response = handle_head(path, headers, data_path, init_path)
                last_modified = format_last_modified(data_path)
                if path == "/logo" and "if-modified-since" in headers:
                    if_modified_since = headers["if-modified-since"]
                else:
                    if_modified_since = "-"
            elif method == "POST":
                status, response = 405, build_response(405, "Method Not Allowed", "Method Not Allowed\n")
                last_modified = "-"
                if_modified_since = "-"
            else:
                status, response = 400, build_response(400, "Bad Request", "Bad Request\n")
                last_modified = "-"
                if_modified_since = "-"

            response = response.replace(b"Connection: close", f"Connection: {response_connection}".encode("ascii"), 1)
            conn.sendall(response)
            write_log(log_path, client[0], client[1], request_line_for_log, status, last_modified, if_modified_since)

            if response_connection == "close":
                return
    except socket.timeout:
        write_log(log_path, client[0], client[1], "<timeout>", 400)
    except Exception as exc:
        print(f"[Worker Error] {client[0]}:{client[1]} -> {exc}")
        write_log(log_path, client[0], client[1], "<error>", 400)
    conn.close()