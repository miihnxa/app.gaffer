"""Notifier interface + dedupe. Spec 3: build the notifier as swappable."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import DATA_DIR

log = logging.getLogger(__name__)
SENT_LOG = DATA_DIR / "sent-alerts.json"


@dataclass
class Alert:
    title: str
    body: str
    priority: str = "default"   # min | low | default | high | urgent
    tags: list[str] = field(default_factory=list)
    # Alerts sharing a dedupe_key inside the dedupe window are sent once.
    dedupe_key: str | None = None

    def fingerprint(self) -> str:
        basis = self.dedupe_key or f"{self.title}|{self.body}"
        return hashlib.sha256(basis.encode()).hexdigest()[:16]


class Notifier:
    """Implement send(). Everything else is shared."""
    name = "base"

    def send(self, alert: Alert) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class DedupeGate:
    def __init__(self, hours: int = 12):
        self.hours = hours
        self.state: dict[str, str] = {}
        if SENT_LOG.exists():
            try:
                self.state = json.loads(SENT_LOG.read_text())
            except json.JSONDecodeError:
                log.warning("sent-alerts.json unreadable, starting fresh")

    def should_send(self, alert: Alert) -> bool:
        fp = alert.fingerprint()
        prev = self.state.get(fp)
        if prev:
            when = datetime.fromisoformat(prev)
            if datetime.now(timezone.utc) - when < timedelta(hours=self.hours):
                log.info("suppressed duplicate: %s", alert.title)
                return False
        return True

    def record(self, alert: Alert) -> None:
        self.state[alert.fingerprint()] = datetime.now(timezone.utc).isoformat()
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        self.state = {
            k: v for k, v in self.state.items()
            if datetime.fromisoformat(v) > cutoff
        }
        SENT_LOG.write_text(json.dumps(self.state, indent=1))
