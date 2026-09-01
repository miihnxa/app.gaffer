"""ntfy.sh notifier — spec 3 option A."""
from __future__ import annotations

import logging

import requests

from .base import Alert, Notifier

log = logging.getLogger(__name__)


class NtfyNotifier(Notifier):
    name = "ntfy"

    def __init__(self, server: str, topic: str, timeout: int = 15):
        if not topic or "CHANGE-ME" in topic:
            raise ValueError(
                "ntfy topic is unset. Pick a private, hard-to-guess topic in "
                "config/settings.yaml — anyone who knows the topic can read your alerts."
            )
        self.url = f"{server.rstrip('/')}/{topic}"
        self.timeout = timeout

    def send(self, alert: Alert) -> None:
        headers = {
            "Title": alert.title.encode("utf-8"),
            "Priority": alert.priority,
        }
        if alert.tags:
            headers["Tags"] = ",".join(alert.tags)
        r = requests.post(
            self.url, data=alert.body.encode("utf-8"),
            headers=headers, timeout=self.timeout,
        )
        r.raise_for_status()
        log.info("ntfy sent: %s", alert.title)
