"""Account client for the desktop app.

The app talks to the hosted account service on your behalf and keeps the
session token in a file only your user can read — a desktop app can protect a
token better than a browser can, so it never reaches the page.

Accounts are optional. With GAFFER_ACCOUNT_URL unset, every endpoint here
reports "unavailable" and the app runs signed out on local data alone.
"""
from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path

import requests

log = logging.getLogger(__name__)

SESSION_FILE = Path.home() / ".gaffer" / "session.json"
TIMEOUT = 20


def service_url() -> str:
    return os.environ.get("GAFFER_ACCOUNT_URL", "").rstrip("/")


def enabled() -> bool:
    return bool(service_url())


# --- token on disk ------------------------------------------------
def _read_token() -> str | None:
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text()).get("token")
    except (json.JSONDecodeError, OSError):
        return None


def _write_token(token: str) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({"token": token}))
    # 0600: owner read/write only. Other accounts on this Mac can't read it.
    SESSION_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def clear_token() -> None:
    SESSION_FILE.unlink(missing_ok=True)


def signed_in() -> bool:
    return _read_token() is not None


# --- calls --------------------------------------------------------
def _call(method: str, path: str, *, body: dict | None = None,
          auth: bool = False) -> tuple[int, dict]:
    if not enabled():
        return 503, {"error": "Accounts aren't configured for this install.",
                     "code": "accounts_disabled"}
    headers = {}
    if auth:
        token = _read_token()
        if not token:
            return 401, {"error": "Not signed in.", "code": "auth_required"}
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.request(method, f"{service_url()}{path}", json=body,
                             headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        log.warning("account service unreachable: %s", exc)
        return 503, {"error": "Can't reach the account service. You can keep "
                              "using Gaffer signed out.",
                     "code": "service_unreachable"}
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"error": f"Unexpected reply ({r.status_code})."}


def request_code(email: str) -> tuple[int, dict]:
    return _call("POST", "/api/auth/request", body={"email": email})


def verify_code(email: str, code: str) -> tuple[int, dict]:
    status, body = _call("POST", "/api/auth/verify",
                         body={"email": email, "code": code})
    if status == 200 and body.get("token"):
        _write_token(body.pop("token"))
    return status, body


def me() -> tuple[int, dict]:
    if not enabled():
        return 200, {"signed_in": False, "available": False}
    if not signed_in():
        return 200, {"signed_in": False, "available": True}
    status, body = _call("GET", "/api/me", auth=True)
    if status == 401:
        clear_token()          # expired or deleted server-side
        return 200, {"signed_in": False, "available": True}
    body["available"] = True
    return status, body


def save_team(team_id: int | None) -> tuple[int, dict]:
    return _call("POST", "/api/me/team", body={"team_id": team_id}, auth=True)


def delete_account() -> tuple[int, dict]:
    status, body = _call("POST", "/api/me/delete", auth=True)
    if status == 200:
        clear_token()
    return status, body


def logout() -> tuple[int, dict]:
    clear_token()
    return 200, {"ok": True}
