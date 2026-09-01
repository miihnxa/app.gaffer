"""Spec 1.2 — deadline reminders at T-24h, T-3h, T-45m."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..api.model import Bootstrap
from ..notify import Alert


@dataclass
class DeadlineInfo:
    gw: int
    name: str
    deadline_utc: datetime

    def local(self, tz: ZoneInfo) -> datetime:
        return self.deadline_utc.astimezone(tz)

    @property
    def minutes_away(self) -> float:
        return (self.deadline_utc - datetime.now(timezone.utc)).total_seconds() / 60

    @property
    def passed(self) -> bool:
        return self.minutes_away < 0

    def countdown(self) -> str:
        m = int(self.minutes_away)
        if m < 0:
            return "passed"
        d, rem = divmod(m, 1440)
        h, mi = divmod(rem, 60)
        if d:
            return f"{d}d {h}h {mi}m"
        return f"{h}h {mi}m" if h else f"{mi}m"


def next_deadline(bs: Bootstrap) -> DeadlineInfo | None:
    now = datetime.now(timezone.utc)
    upcoming = [
        DeadlineInfo(e["id"], e["name"], Bootstrap.deadline(e))
        for e in bs.events
        if Bootstrap.deadline(e) > now
    ]
    return min(upcoming, key=lambda d: d.deadline_utc) if upcoming else None


def due_reminders(info: DeadlineInfo, windows: list[int],
                  slack_minutes: int = 70) -> list[int]:
    """Which T-minus windows we're currently inside.

    slack_minutes must exceed the polling interval, or a reminder fires between
    two runs and is missed entirely. Dedupe stops repeats.
    """
    out = []
    for w in sorted(windows, reverse=True):
        if w >= info.minutes_away > w - slack_minutes:
            out.append(w)
    return out


def _window_label(minutes: int) -> str:
    if minutes >= 1440:
        return f"T-{minutes // 1440}d"
    if minutes >= 60:
        return f"T-{minutes // 60}h"
    return f"T-{minutes}m"


def to_alert(info: DeadlineInfo, window: int, tz: ZoneInfo, *,
             free_transfers: int | str = "?", captain: str = "?",
             flagged: list[str] | None = None, chip: str | None = None) -> Alert:
    local = info.local(tz)
    urgent = window <= 45
    body = [
        f"{info.name} deadline: {local:%a %d %b, %H:%M} ({tz.key})",
        f"Time left: {info.countdown()}",
        "",
        f"Free transfers: {free_transfers}",
        f"Captain: {captain}",
    ]
    if chip:
        body.append(f"Chip planned: {chip.upper()}")
    if flagged:
        body += ["", f"⚠️ Flagged in your squad: {', '.join(flagged)}"]
    return Alert(
        title=f"⏳ {_window_label(window)} — GW{info.gw} deadline",
        body="\n".join(body),
        priority="urgent" if urgent else ("high" if window <= 180 else "default"),
        tags=["hourglass_flowing_sand"],
        dedupe_key=f"deadline:{info.gw}:{window}",
    )
