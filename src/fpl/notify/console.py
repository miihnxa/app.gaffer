"""Console notifier — the default while testing, and the dry-run target."""
from __future__ import annotations

from .base import Alert, Notifier

ICON = {"urgent": "\033[91m!!\033[0m", "high": "\033[93m! \033[0m",
        "default": "  ", "low": "  ", "min": "  "}


class ConsoleNotifier(Notifier):
    name = "console"

    def send(self, alert: Alert) -> None:
        bar = "─" * 64
        print(f"\n{bar}\n{ICON.get(alert.priority,'  ')} \033[1m{alert.title}\033[0m")
        if alert.tags:
            print(f"   [{' '.join(alert.tags)}]")
        print(bar)
        print(alert.body)
        print(bar)
