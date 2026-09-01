"""SMTP notifier — spec 3 option D. Good for digests, too slow for urgent."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from .base import Alert, Notifier

log = logging.getLogger(__name__)


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, host: str, port: int, username: str,
                 password_env: str, to: str):
        self.host, self.port, self.username, self.to = host, port, username, to
        self.password = os.environ.get(password_env, "")
        if not self.password:
            raise ValueError(
                f"SMTP password not found in ${password_env}. "
                f"Export it in your shell — never put it in settings.yaml."
            )

    def send(self, alert: Alert) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"[FPL] {alert.title}"
        msg["From"], msg["To"] = self.username, self.to
        msg.set_content(alert.body)
        with smtplib.SMTP(self.host, self.port, timeout=30) as s:
            s.starttls()
            s.login(self.username, self.password)
            s.send_message(msg)
        log.info("email sent: %s", alert.title)
