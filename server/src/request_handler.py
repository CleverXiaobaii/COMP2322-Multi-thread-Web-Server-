def handle_head(path: str, headers: dict[str, str], data_path: Path, init_path: Path) -> tuple[int, bytes]:
    # 复用GET逻辑获取响应头，但body置空
    status, response = handle_get(path, headers, data_path, init_path)
    # 找到header和body的分界，去除body
    if b"\r\n\r\n" in response:
        header_end = response.index(b"\r\n\r\n") + 4
        response = response[:header_end]
    return status, response
from __future__ import annotations

import json
import socket
from http import HTTPStatus
from pathlib import Path

from .http_utils import (
    build_response,
    build_response_with_headers,
    parse_headers,
    parse_http_request,
    parse_request_line,
    read_request_header,
)
from .storage_utils import format_last_modified, is_not_modified, load_data, read_instruction, write_log


def handle_get(path: str, headers: dict[str, str], data_path: Path, init_path: Path) -> tuple[int, bytes]:
    if path == "/init":
        instruction = read_instruction(init_path)
        body = instruction if instruction.endswith("\n") else instruction + "\n"
        return 200, build_response(200, "OK", body)

    if ".." in path:
        return 403, build_response(403, "Forbidden", "Forbidden\n")

    if not path.startswith("/data"):
        return 404, build_response(404, "File Not Found", "File Not Found\n")

    if_modified_since = headers.get("if-modified-since")
    if if_modified_since and is_not_modified(data_path, if_modified_since):
        last_modified = format_last_modified(data_path)
        response = build_response_with_headers(304, "Not Modified", "", [f"Last-Modified: {last_modified}"])
        return 304, response

    data = load_data(data_path)
    
    if path == "/data":
        payload = json.dumps(data, ensure_ascii=False)
        last_modified = format_last_modified(data_path)
        response = build_response_with_headers(200, "OK", payload + "\n", [f"Last-Modified: {last_modified}"])
        return 200, response

    path_parts = path.split("/", 2)
    if len(path_parts) != 3 or not path_parts[2]:
        return 400, build_response(400, "Bad Request", "Bad Request\n")

    key = path_parts[2]
    if key not in data:
        return 404, build_response(404, "File Not Found", "File Not Found\n")

    payload = json.dumps({key: data[key]}, ensure_ascii=False)
    last_modified = format_last_modified(data_path)
    response = build_response_with_headers(200, "OK", payload + "\n", [f"Last-Modified: {last_modified}"])
    return 200, response


def handle_post(path: str, headers: dict[str, str], data_path: Path, init_path: Path) -> tuple[int, bytes]:
    _ = (path, headers, data_path, init_path)
    return 400, build_response(400, "Bad Request", "Bad Request\n")


def preprocess_request(
    conn: socket.socket,
    client: tuple[str, int],
    cfg: dict,
) -> tuple[bool, str, str, dict[str, str], str, int, bytes]:
    request_line_for_log = "<unparsed>"
    
    try:
        # 调用新的 parse_http_request 函数（纯解析）
        method, path, version, headers, raw_header = parse_http_request(
            conn, cfg["buffer_size"], cfg["max_header_bytes"]
        )
        
        # 业务逻辑：打印请求
        header_text = raw_header.decode("iso-8859-1", errors="replace")
        print(f"\n--- Request from {client[0]}:{client[1]} ---")
        print(header_text)
        print("--- End Request ---\n")
        
        # 业务逻辑：生成日志行
        request_line_for_log = f"{method} {path} {version}"
        
        return True, method, path, headers, request_line_for_log, 0, b""
        
    except Exception as exc:
        if str(exc) == "Empty request":
            return False, "", "", {}, request_line_for_log, 0, b""
        # 业务逻辑：构建 400 错误响应
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
    conn.settimeout(5)
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

            if method == "GET":
                status, response = handle_get(path, headers, data_path, init_path)
            elif method == "POST":
                status, response = handle_post(path, headers, data_path, init_path)
            elif method == "HEAD":
                status, response = handle_head(path, headers, data_path, init_path)
            else:
                status, response = 400, build_response(400, "Bad Request", "Bad Request\n")

            response = response.replace(b"Connection: close", f"Connection: {response_connection}".encode("ascii"), 1)
            conn.sendall(response)
            write_log(log_path, client[0], client[1], request_line_for_log, status,)

            if response_connection == "close":
                return
    except socket.timeout:
        write_log(log_path, client[0], client[1], "<timeout>", 400)
    except Exception as exc:
        print(f"[Worker Error] {client[0]}:{client[1]} -> {exc}")
        write_log(log_path, client[0], client[1], "<error>", 400)
    conn.close()