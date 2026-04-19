from __future__ import annotations

import datetime
import json
import threading
from http import HTTPStatus
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path


LOG_LOCK = threading.Lock()
DATA_LOCK = threading.Lock()


def write_log(log_path: Path, client_ip: str, client_port: int, request_line: str, status_code: int, last_modified: str = "-", if_modified_since: str = "-") -> None:
    reason = HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else "Unknown"
    status = f"{status_code} {reason}"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 新增last_modified和if_modified_since字段
    log_line = f'{timestamp} {client_ip}:{client_port} "{request_line}" {status} Last-Modified: {last_modified} If-Modified-Since: {if_modified_since}\n'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with LOG_LOCK:
        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(log_line)


def ensure_data_file(data_path: Path) -> None:
    data_path.parent.mkdir(parents=True, exist_ok=True)
    if data_path.exists():
        return
    with DATA_LOCK:
        if not data_path.exists():
            data_path.write_text("{}\n", encoding="utf-8")


def load_data(data_path: Path) -> dict:
    with DATA_LOCK:
        with data_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError("data.json root must be object")
    return data


def is_not_modified(data_path: Path, if_modified_since: str) -> bool:
    since = parsedate_to_datetime(if_modified_since)
    if since.tzinfo is None:
        since = since.replace(tzinfo=datetime.timezone.utc)

    modified_ts = data_path.stat().st_mtime
    modified_dt = datetime.datetime.fromtimestamp(modified_ts, tz=datetime.timezone.utc)
    modified_dt = modified_dt.replace(microsecond=0)
    return modified_dt <= since


def format_last_modified(data_path: Path) -> str:
    return format_datetime(
        datetime.datetime.fromtimestamp(data_path.stat().st_mtime, tz=datetime.timezone.utc),
        usegmt=True,
    )


def read_instruction(instruction_path: Path) -> str:
    return instruction_path.read_text(encoding="utf-8")
