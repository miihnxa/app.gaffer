"""Phase 3.3 — live gameweek tracker."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..api.model import Bootstrap, Player
from .fixtures import FixtureBook

# Point-scoring events worth a push notification.
WATCHED = {
    "goals_scored": ("⚽", "goal"),
    "assists": ("🅰️", "assist"),
    "penalties_saved": ("🧤", "penalty save"),
    "penalties_missed": ("❌", "penalty miss"),
    "red_cards": ("🟥", "red card"),
    "own_goals": ("😬", "own goal"),
}


@dataclass
class LivePlayer:
    player: Player
    points: int
    minutes: int
    stats: dict
    multiplier: int
    benched: bool

    @property
    def contributed(self) -> int:
        return self.points * self.multiplier


def fixtures_in_play(bs: Bootstrap, fb: FixtureBook, gw: int) -> bool:
    """True if any GW fixture is currently running — so the tracker only polls
    during matches instead of every five minutes around the clock."""
    now = datetime.now(timezone.utc)
    for team_fx in fb.by_team.values():
        for f in team_fx:
            if f.gw != gw or not f.kickoff:
                continue
            if f.kickoff <= now <= f.kickoff + timedelta(hours=2, minutes=15):
                return True
    return False


def snapshot(client, bs: Bootstrap, squad, gw: int) -> tuple[list[LivePlayer], int]:
    data = client.live(gw)
    by_id = {e["id"]: e for e in data.get("elements", [])}
    rows: list[LivePlayer] = []
    total = 0
    for pick in squad.picks:
        e = by_id.get(pick.player.id)
        if not e:
            continue
        stats = e.get("stats", {})
        lp = LivePlayer(
            player=pick.player, points=int(stats.get("total_points", 0)),
            minutes=int(stats.get("minutes", 0)), stats=stats,
            multiplier=pick.multiplier, benched=pick.on_bench,
        )
        rows.append(lp)
        if not pick.on_bench:
            total += lp.contributed
    return rows, total


def render(rows: list[LivePlayer], total: int, gw: int) -> str:
    lines = [f"GW{gw} live: {total} pts", ""]
    for r in sorted(rows, key=lambda r: (r.benched, -r.contributed)):
        events = []
        for key, (icon, _label) in WATCHED.items():
            n = int(r.stats.get(key, 0) or 0)
            if n:
                events.append(icon * n)
        mark = "B" if r.benched else ("C" if r.multiplier > 1 else " ")
        lines.append(f"  {mark} {r.player.name:<15}{r.minutes:>4}'  "
                     f"{r.contributed:>3} pts  {''.join(events)}")
    return "\n".join(lines)
