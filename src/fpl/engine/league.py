"""Phase 3 — mini-league tracking and rival squad diffing.

Spec 3.2: "When leading, matching rival differentials is often correct — don't
chase my own." The diff is presented from that angle.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..api.model import Bootstrap, Player
from ..config import SNAPSHOT_DIR
from ..notify import Alert

SNAPSHOT = SNAPSHOT_DIR / "league.json"


@dataclass
class Rival:
    entry: int
    name: str          # team name
    manager: str
    rank: int
    last_rank: int
    total: int
    gw_points: int

    @property
    def moved(self) -> int:
        return self.last_rank - self.rank if self.last_rank else 0


@dataclass
class Diff:
    rival: Rival
    their_differentials: list[Player]   # they own, you don't
    your_differentials: list[Player]    # you own, they don't
    their_captain: Player | None
    your_captain: Player | None
    gap: int                            # your total minus theirs

    @property
    def leading(self) -> bool:
        return self.gap > 0


def standings(client, league_id: int) -> tuple[str, list[Rival]]:
    data = client.standings(league_id)
    name = data.get("league", {}).get("name", f"League {league_id}")
    rows = data.get("standings", {}).get("results", [])
    return name, [
        Rival(
            entry=r["entry"], name=r["entry_name"], manager=r["player_name"],
            rank=r["rank"], last_rank=r.get("last_rank") or 0,
            total=r["total"], gw_points=r.get("event_total", 0),
        ) for r in rows
    ]


def find_me(rivals: list[Rival], team_id: int) -> Rival | None:
    return next((r for r in rivals if r.entry == int(team_id)), None)


def diff_against(client, bs: Bootstrap, my_ids: set[int], my_captain: Player | None,
                 me: Rival, rival: Rival, gw: int) -> Diff | None:
    try:
        picks = client.picks(rival.entry, gw)
    except Exception:  # noqa: BLE001 — a rival's picks stay private until the deadline
        return None
    theirs = {p["element"] for p in picks["picks"]}
    their_cap = next((bs.player(p["element"]) for p in picks["picks"]
                      if p["is_captain"]), None)
    return Diff(
        rival=rival,
        their_differentials=sorted(
            (bs.player(i) for i in theirs - my_ids), key=lambda p: -p.form),
        your_differentials=sorted(
            (bs.player(i) for i in my_ids - theirs), key=lambda p: -p.form),
        their_captain=their_cap, your_captain=my_captain,
        gap=me.total - rival.total,
    )


def _read() -> dict:
    if not SNAPSHOT.exists():
        return {}
    try:
        return json.loads(SNAPSHOT.read_text())
    except json.JSONDecodeError:
        return {}


def _write(name: str, rivals: list[Rival]) -> None:
    SNAPSHOT.write_text(json.dumps({
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "league": name,
        "rows": {str(r.entry): {"rank": r.rank, "total": r.total, "name": r.name}
                 for r in rivals},
    }, indent=1))


def movement_alerts(name: str, rivals: list[Rival], team_id: int) -> list[Alert]:
    prev = _read().get("rows", {})
    me = find_me(rivals, team_id)
    alerts: list[Alert] = []

    if me and prev:
        before = prev.get(str(team_id))
        if before and before["rank"] != me.rank:
            better = me.rank < before["rank"]
            leader = rivals[0]
            alerts.append(Alert(
                title=(f"{'🔼' if better else '🔽'} You are now "
                       f"{_ordinal(me.rank)} in {name}"),
                body=(f"{_ordinal(before['rank'])} → {_ordinal(me.rank)}\n"
                      f"{me.total} pts\n"
                      + (f"Leader: {leader.name} on {leader.total} "
                         f"({me.total - leader.total:+d})"
                         if leader.entry != me.entry else "You lead.")),
                priority="high" if not better else "default",
                tags=["chart_with_upwards_trend" if better else "chart_with_downwards_trend"],
                dedupe_key=f"league-rank:{me.rank}:{me.total}",
            ))

        # Abandon-plan trigger: more than 15 points behind the leader.
        leader = rivals[0]
        behind = leader.total - me.total
        if behind > 15:
            alerts.append(Alert(
                title=f"🚨 {behind} points behind {leader.name}",
                body=("Abandon-plan trigger met (more than 15 points behind the "
                      f"leader).\nYou: {me.total} · {leader.name}: {leader.total}\n\n"
                      "If a second trigger is also true, pull the Wildcard forward."),
                priority="urgent", tags=["rotating_light"],
                dedupe_key=f"league-behind:{behind // 5}",
            ))

    _write(name, rivals)
    return alerts


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def render_diff(d: Diff) -> str:
    lines = [
        f"{d.rival.name} ({d.rival.manager}) — {_ordinal(d.rival.rank)}, "
        f"{d.rival.total} pts  [{d.gap:+d} vs you]",
    ]
    if d.their_captain and d.your_captain and d.their_captain.id != d.your_captain.id:
        lines.append(f"  Captain: they have {d.their_captain.name}, "
                     f"you have {d.your_captain.name}")
    if d.their_differentials:
        lines.append("  They own, you don't:")
        for p in d.their_differentials[:6]:
            lines.append(f"    {p.name:<15}{p.team_short:<5}£{p.price:>4.1f}m  form {p.form}")
    if d.your_differentials:
        lines.append("  You own, they don't:")
        for p in d.your_differentials[:6]:
            lines.append(f"    {p.name:<15}{p.team_short:<5}£{p.price:>4.1f}m  form {p.form}")
    if d.leading and d.their_differentials:
        lines.append("  You're ahead of this rival — covering their differentials "
                     "protects the lead better than backing your own.")
    return "\n".join(lines)
