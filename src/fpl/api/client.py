"""FPL API client — read-only, cached, schema-validated."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from ..config import Config, DATA_DIR
from . import schema

log = logging.getLogger(__name__)

CACHE_DIR = DATA_DIR / "cache"


class FPLError(RuntimeError):
    pass


class FPLClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        api = cfg.api
        self.base = api.get("base_url", "https://fantasy.premierleague.com/api").rstrip("/")
        self.timeout = int(api.get("timeout_seconds", 20))
        self.retries = int(api.get("retries", 3))
        self.cache_minutes = int(api.get("bootstrap_cache_minutes", 30))
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": api.get("user_agent", "fpl-assistant/1.0")})
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # --- transport -------------------------------------------------
    def _get(self, path: str) -> Any:
        url = f"{self.base}/{path.lstrip('/')}"
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code == 404:
                    raise FPLError(
                        f"404 from {url}. entry/ endpoints 404 before GW1 and for "
                        f"unknown team ids — check your team_id."
                    )
                r.raise_for_status()
                return r.json()
            except FPLError:
                raise
            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt < self.retries:
                    backoff = 2 ** attempt
                    log.warning("GET %s failed (%s), retrying in %ss", url, exc, backoff)
                    time.sleep(backoff)
        raise FPLError(f"GET {url} failed after {self.retries} attempts: {last}")

    def _cached(self, path: str, cache_name: str, minutes: int) -> Any:
        f = CACHE_DIR / cache_name
        if f.exists():
            age = datetime.now(timezone.utc) - datetime.fromtimestamp(
                f.stat().st_mtime, tz=timezone.utc
            )
            if age < timedelta(minutes=minutes):
                log.debug("cache hit %s (age %s)", cache_name, age)
                return json.loads(f.read_text())
        data = self._get(path)
        f.write_text(json.dumps(data))
        return data

    # --- endpoints -------------------------------------------------
    def bootstrap(self, force: bool = False) -> dict:
        """The workhorse. Cached 30+ min per spec, validated before return."""
        minutes = 0 if force else self.cache_minutes
        data = self._cached("bootstrap-static/", "bootstrap-static.json", minutes)
        schema.validate_bootstrap(data)
        return data

    def fixtures(self, event: int | None = None) -> list:
        path = f"fixtures/?event={event}" if event else "fixtures/"
        name = f"fixtures-{event or 'all'}.json"
        data = self._cached(path, name, 60)
        schema.validate_fixtures(data)
        return data

    def entry(self, team_id: int) -> dict:
        data = self._get(f"entry/{team_id}/")
        schema.validate_entry(data)
        return data

    def picks(self, team_id: int, event: int) -> dict:
        data = self._get(f"entry/{team_id}/event/{event}/picks/")
        schema.validate_picks(data)
        return data

    def history(self, team_id: int) -> dict:
        return self._get(f"entry/{team_id}/history/")

    def transfers(self, team_id: int) -> list:
        return self._get(f"entry/{team_id}/transfers/")

    def element_summary(self, player_id: int) -> dict:
        return self._get(f"element-summary/{player_id}/")

    def live(self, event: int) -> dict:
        return self._get(f"event/{event}/live/")

    def standings(self, league_id: int, page: int = 1) -> dict:
        return self._get(f"leagues-classic/{league_id}/standings/?page_standings={page}")
