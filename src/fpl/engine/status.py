"""Spec 1.1 — injury and status watch. The highest-value feature.

Diffs each owned/watchlisted player's status and chance_of_playing against the
last snapshot, and alerts on any deterioration.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..api.model import Player, STATUS_TEXT
from ..config import SNAPSHOT_DIR
from ..notify import Alert

SNAPSHOT = SNAPSHOT_DIR / "status.json"

# Higher = worse. Used to tell deterioration from recovery.
SEVERITY = {"a": 0, "d": 1, "u": 2, "n": 2, "s": 3, "i": 4}


@dataclass
class StatusChange:
    player: Player
    owned: bool
    old_status: str
    new_status: str
    old_chance: int | None
    new_chance: int | None

    @property
    def worsened(self) -> bool:
        if SEVERITY.get(self.new_status, 0) > SEVERITY.get(self.old_status, 0):
            return True
        old = 100 if self.old_chance is None else self.old_chance
        new = 100 if self.new_chance is None else self.new_chance
        return new < old

    @property
    def recovered(self) -> bool:
        return not self.worsened

    def describe(self) -> str:
        bits = []
        if self.old_status != self.new_status:
            bits.append(
                f"{STATUS_TEXT.get(self.old_status, self.old_status)} → "
                f"{STATUS_TEXT.get(self.new_status, self.new_status)}"
            )
        if self.old_chance != self.new_chance:
            fmt = lambda v: "—" if v is None else f"{v}%"
            bits.append(f"chance {fmt(self.old_chance)} → {fmt(self.new_chance)}")
        return "; ".join(bits) or "flag updated"


def _read_snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {}
    try:
        return json.loads(SNAPSHOT.read_text()).get("players", {})
    except json.JSONDecodeError:
        return {}


def _write_snapshot(players: list[Player]) -> None:
    SNAPSHOT.write_text(json.dumps({
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "players": {
            str(p.id): {
                "status": p.status,
                "chance": p.chance,
                "news": p.news,
                "name": p.name,
            } for p in players
        },
    }, indent=1))


def check(owned: list[Player], watched: list[Player]) -> tuple[list[StatusChange], list[Player]]:
    """Returns (changes since last run, everyone currently flagged)."""
    prev = _read_snapshot()
    owned_ids = {p.id for p in owned}
    everyone = {p.id: p for p in owned + watched}

    changes: list[StatusChange] = []
    for pid, p in everyone.items():
        before = prev.get(str(pid))
        if before is None:
            continue  # first run — record only, never alert on a cold start
        if before["status"] == p.status and before.get("chance") == p.chance:
            continue
        changes.append(StatusChange(
            player=p, owned=pid in owned_ids,
            old_status=before["status"], new_status=p.status,
            old_chance=before.get("chance"), new_chance=p.chance,
        ))

    _write_snapshot(list(everyone.values()))
    flagged = [p for p in owned if p.is_flagged]
    return changes, flagged


def to_alerts(changes: list[StatusChange]) -> list[Alert]:
    alerts = []
    for c in changes:
        p = c.player
        tag = "OWNED" if c.owned else "WATCHLIST"
        if c.worsened:
            urgent = c.owned and (p.status in ("i", "s") or p.effective_chance <= 25)
            alerts.append(Alert(
                title=f"⚠️ {p.name} — {STATUS_TEXT.get(p.status, p.status)}",
                body=(
                    f"[{tag}] {p.label()}\n"
                    f"{c.describe()}\n"
                    f"{p.news or 'No news text from FPL.'}\n"
                    f"Form {p.form} · {p.total_points} pts"
                ),
                priority="urgent" if urgent else "high",
                tags=["rotating_light"] if urgent else ["warning"],
                dedupe_key=f"status:{p.id}:{p.status}:{p.chance}",
            ))
        else:
            alerts.append(Alert(
                title=f"✅ {p.name} — {STATUS_TEXT.get(p.status, p.status)}",
                body=f"[{tag}] {p.label()}\n{c.describe()}\n{p.news or 'Flag cleared.'}",
                priority="default", tags=["white_check_mark"],
                dedupe_key=f"status:{p.id}:{p.status}:{p.chance}",
            ))
    return alerts
