"""Rate limiting.

Two jobs: keep one abusive client from burning the service, and keep the
service from hammering the FPL API on everyone's behalf. The FPL API sends
`cache-control: max-age=300`, so a shared 5-minute cache is what they ask for —
see cache.py.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from flask import jsonify, request

_hits: dict[str, deque] = defaultdict(deque)
_lock = Lock()

# requests per window, per identity
ANON_PER_MIN = 20
USER_PER_MIN = 60
PRO_PER_MIN = 180


def identity(user) -> tuple[str, int]:
    if user is None:
        ip = (request.headers.get("Fly-Client-IP")
              or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
              or request.remote_addr or "anon")
        return f"ip:{ip}", ANON_PER_MIN
    return f"user:{user.id}", PRO_PER_MIN if user.is_pro else USER_PER_MIN


def check(user) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds)."""
    key, limit = identity(user)
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return False, max(1, int(60 - (now - q[0])))
        q.append(now)
    return True, 0


def too_many(retry_after: int):
    r = jsonify({
        "error": f"Too many requests. Try again in {retry_after}s.",
        "code": "rate_limited",
    })
    r.status_code = 429
    r.headers["Retry-After"] = str(retry_after)
    return r
