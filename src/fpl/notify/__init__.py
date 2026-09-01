"""Notifier factory."""
from __future__ import annotations

import logging

from ..config import Config
from .base import Alert, DedupeGate, Notifier
from .console import ConsoleNotifier

log = logging.getLogger(__name__)
__all__ = ["Alert", "Notifier", "DedupeGate", "build_notifier", "Dispatcher"]


def build_notifier(cfg: Config, override: str | None = None) -> Notifier:
    n = cfg.settings.get("notify", {})
    provider = override or n.get("provider", "console")

    if provider == "console":
        return ConsoleNotifier()
    if provider == "ntfy":
        from .ntfy import NtfyNotifier
        c = n.get("ntfy", {})
        return NtfyNotifier(c.get("server", "https://ntfy.sh"), c.get("topic", ""))
    if provider == "email":
        from .email import EmailNotifier
        c = n.get("email", {})
        return EmailNotifier(c["smtp_host"], int(c.get("smtp_port", 587)),
                             c["username"], c.get("password_env", "FPL_SMTP_PASSWORD"),
                             c["to"])
    raise ValueError(f"unknown notify provider: {provider!r}")


class Dispatcher:
    """Notifier + dedupe + dry-run, so jobs never touch either directly."""

    def __init__(self, cfg: Config, notifier: Notifier, dry_run: bool = False):
        self.notifier = notifier
        self.dry_run = dry_run
        self.gate = DedupeGate(int(cfg.settings.get("notify", {}).get("dedupe_hours", 12)))
        self.sent = 0
        self.suppressed = 0

    def send(self, alert: Alert) -> bool:
        if not self.gate.should_send(alert):
            self.suppressed += 1
            return False
        if self.dry_run:
            ConsoleNotifier().send(alert)
            print("   (dry run — not delivered, not recorded)")
            self.sent += 1
            return True
        self.notifier.send(alert)
        self.gate.record(alert)
        self.sent += 1
        return True
