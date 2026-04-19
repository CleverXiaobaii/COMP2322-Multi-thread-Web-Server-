#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import socket
import threading
from pathlib import Path


from storage_utils import ensure_data_file
from request_handler import handle_client


def main() -> int:
    #load data
    project_root = Path(__file__).resolve().parents[2]
    data_path = project_root / "server" / "resource" / "data.json"
    init_path = project_root / "server" / "resource" / "init" / "instruction.txt"
    config_path = project_root / "server" / "src" / "config.py"
    spec = importlib.util.spec_from_file_location("server_src_config", config_path)
    if spec is None or spec.loader is None:
        print("config load failed")
        return 1
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg = module.SERVER_CONFIG

    log_path = Path(cfg["log_path"])
    if not log_path.is_absolute():
        log_path = project_root / log_path

    ensure_data_file(data_path)


    #start a server listening on 127.0.0.1:8080
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


    #if a client connects, start a new thread to handle the request and log the request line and response status code to server.log
    try:
        while True:
            conn, client = server_socket.accept()
            worker = threading.Thread(
                target=handle_client,
                args=(conn, client, cfg, log_path, data_path, init_path),
                daemon=True,
            )
            worker.start()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    server_socket.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
