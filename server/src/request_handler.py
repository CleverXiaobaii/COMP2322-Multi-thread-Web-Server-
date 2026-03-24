from __future__ import annotations

import json
import socket
from pathlib import Path

from .http_utils import (
    build_response,
    build_response_with_headers,
    parse_headers,
    parse_request_line,
    read_request_header,
)
from .storage_utils import format_last_modified, is_not_modified, load_data, write_log


def handle_client(conn: socket.socket, client: tuple[str, int], cfg: dict, log_path: Path, data_path: Path) -> None:
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
        headers = parse_headers(raw_header)
        request_line_for_log = f"{method} {path} {version}"

        if method != "GET":
            status = 400
            conn.sendall(build_response(400, "Bad Request", "Bad Request\n"))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        if ".." in path:
            status = 403
            conn.sendall(build_response(403, "Forbidden", "Forbidden\n"))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        if not path.startswith("/data"):
            status = 404
            conn.sendall(build_response(404, "File Not Found", "File Not Found\n"))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        if_modified_since = headers.get("if-modified-since")
        if if_modified_since and is_not_modified(data_path, if_modified_since):
            status = 304
            last_modified = format_last_modified(data_path)
            conn.sendall(build_response_with_headers(304, "Not Modified", "", [f"Last-Modified: {last_modified}"]))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        try:
            data = load_data(data_path)
        except Exception:
            status = 400
            conn.sendall(build_response(400, "Bad Request", "Bad Request\n"))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        path_parts = path.split("/", 2)
        if path == "/data":
            payload = json.dumps(data, ensure_ascii=False)
            last_modified = format_last_modified(data_path)
            status = 200
            conn.sendall(build_response_with_headers(200, "OK", payload + "\n", [f"Last-Modified: {last_modified}"]))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        if len(path_parts) != 3 or not path_parts[2]:
            status = 400
            conn.sendall(build_response(400, "Bad Request", "Bad Request\n"))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        key = path_parts[2]
        if key not in data:
            status = 404
            conn.sendall(build_response(404, "File Not Found", "File Not Found\n"))
            write_log(log_path, client[0], client[1], request_line_for_log, status)
            return

        payload = json.dumps({key: data[key]}, ensure_ascii=False)
        last_modified = format_last_modified(data_path)
        status = 200
        conn.sendall(build_response_with_headers(200, "OK", payload + "\n", [f"Last-Modified: {last_modified}"]))
        write_log(log_path, client[0], client[1], request_line_for_log, status)
    except socket.timeout:
        write_log(log_path, client[0], client[1], request_line_for_log, status)
    except Exception as exc:
        print(f"[Worker Error] {client[0]}:{client[1]} -> {exc}")
        write_log(log_path, client[0], client[1], request_line_for_log, status)
    finally:
        conn.close()
