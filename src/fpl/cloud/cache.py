"""One shared FPL data cache for the whole process.

A public service must never fetch bootstrap-static per user. This holds a
single Service instance behind a lock and refreshes it on the FPL API's own
cadence (`cache-control: max-age=300`).
"""
from __future__ import annotations

import logging
import threading
import time

from ..config import Config
from ..webapp.service import Service

log = logging.getLogger(__name__)

REFRESH_SECONDS = 300  # matches the FPL API's own max-age

_svc: Service | None = None
_lock = threading.Lock()
_loaded_at = 0.0


def service() -> Service:
    global _svc, _loaded_at
    with _lock:
        now = time.monotonic()
        if _svc is None:
            cfg = Config.load()
            # A hosted service has no personal team: never apply one user's
            # season plan to somebody else's squad.
            cfg.settings.setdefault("entry", {})["team_id"] = None
            cfg.plan = {"rules": cfg.plan.get("rules", {})}
            _svc = Service(cfg)
            _loaded_at = now
        elif now - _loaded_at > REFRESH_SECONDS:
            _svc._fetched = None  # force the next property access to refetch
            _loaded_at = now
        return _svc
