"""
progress_logger.py — Writes pipeline progress to a local JSON file so it
can be watched live in a browser dashboard, without touching Firestore
or anything your teammate is working on. Pure local file I/O only.
"""

import json
import os
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline_run_log.json")


def start_run():
    """Call once at the top of a pipeline run. Resets the log file."""
    with _LOCK:
        data = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "finished": False,
            "events": [],
        }
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def log_event(stage: str, message: str, status: str = "info", data: dict = None):
    """
    stage: 'discover' | 'scrape' | 'classify' | 'extract' | 'publish' | 'reject' | 'skip' | 'error'
    status: 'info' | 'success' | 'warning' | 'error'
    """
    with _LOCK:
        try:
            with open(_LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished": False,
                "events": [],
            }

        log["events"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "status": status,
            "message": message,
            "data": data or {},
        })
        log["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)


def finish_run():
    with _LOCK:
        try:
            with open(_LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        log["finished"] = True
        log["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)