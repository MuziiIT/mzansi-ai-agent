"""
quota_tracker.py — tracks how many Gemini calls have been made today in a
small local JSON file, so the pipeline can check its budget BEFORE calling
the API, instead of finding out via a wall of failed retries (as happened
when the free-tier 20/day limit was hit mid-run).

Not a substitute for real billing/usage data from Google — just a local
safety net so this pipeline behaves predictably around its own budget.
"""

import json
import os
from datetime import datetime, timezone

from config import GEMINI_DAILY_REQUEST_BUDGET

_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quota_state.json")


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_state() -> dict:
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}

    if state.get("date") != _today_str():
        # New day — reset the counter.
        state = {"date": _today_str(), "count": 0}
    return state


def _save_state(state: dict):
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def has_budget() -> bool:
    """Check this BEFORE making a Gemini call."""
    return _load_state()["count"] < GEMINI_DAILY_REQUEST_BUDGET


def remaining() -> int:
    state = _load_state()
    return max(0, GEMINI_DAILY_REQUEST_BUDGET - state["count"])


def record_call():
    """Call this after every Gemini request attempt (success or failure —
    a failed attempt still used up part of your window/rate limit)."""
    state = _load_state()
    state["count"] += 1
    _save_state(state)