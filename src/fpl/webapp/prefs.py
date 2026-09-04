"""Preferences that survive a restart.

The window's localStorage is not a safe home for anything that matters: it is
per-WebKit-data-store and can be cleared without warning. The app's own state
lives in a JSON file under the user directory instead, written atomically.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any

from ..config import DATA_DIR

log = logging.getLogger(__name__)
PREFS_FILE = DATA_DIR / "prefs.json"

DEFAULTS: dict[str, Any] = {
    "team_id": None,
    "recents": [],          # [{id, name, manager}]
    "toggles": {},
    "bench_budget": 19.0,
    "swaps": {},            # {"<team_id>:<gw>": {"<out_id>": <in_id>}}
    "anthropic_key": "",    # the user's own key; never sent to the page
}


def _read() -> dict[str, Any]:
    if not PREFS_FILE.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(PREFS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("prefs unreadable (%s) — starting from defaults", exc)
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def _write(data: dict[str, Any]) -> None:
    PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file and rename, so a crash mid-write can't truncate the
    # file and lose someone's recorded transfers.
    fd, tmp = tempfile.mkstemp(dir=PREFS_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, PREFS_FILE)
    except Exception:
        os.unlink(tmp)
        raise


def all() -> dict[str, Any]:
    """Safe to hand to the page: the API key is replaced with a presence flag."""
    data = _read()
    key = data.pop("anthropic_key", "")
    data["has_key"] = bool(key)
    return data


def api_key() -> str:
    return _read().get("anthropic_key", "")


def update(patch: dict[str, Any]) -> dict[str, Any]:
    data = _read()
    for k, v in patch.items():
        if k in DEFAULTS:
            data[k] = v
    _write(data)
    if PREFS_FILE.exists():
        # The key is a credential: no group or other access.
        PREFS_FILE.chmod(0o600)
    return all()


def _swap_key(team_id: int, gw: int) -> str:
    return f"{int(team_id)}:{int(gw)}"


def get_swaps(team_id: int, gw: int) -> dict[str, int]:
    return _read()["swaps"].get(_swap_key(team_id, gw), {})


def set_swap(team_id: int, gw: int, out_id: int, in_id: int) -> dict[str, int]:
    data = _read()
    key = _swap_key(team_id, gw)
    data["swaps"].setdefault(key, {})[str(int(out_id))] = int(in_id)
    _write(data)
    return data["swaps"][key]


def clear_swap(team_id: int, gw: int, out_id: int | None = None) -> dict[str, int]:
    data = _read()
    key = _swap_key(team_id, gw)
    if out_id is None:
        data["swaps"].pop(key, None)
    else:
        data["swaps"].get(key, {}).pop(str(int(out_id)), None)
    _write(data)
    return data["swaps"].get(key, {})
