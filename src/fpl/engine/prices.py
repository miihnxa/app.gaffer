"""Spec 1.3 — price change alerts.

Two sources, both used:
  1. A nightly snapshot diff of now_cost — confirmed, already-happened changes.
  2. price_change_percent / price_change_projections, which this season's API
     exposes directly — a forward warning before the ~01:30 UK run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..api.model import Player
from ..config import SNAPSHOT_DIR
from ..notify import Alert

SNAPSHOT = SNAPSHOT_DIR / "prices.json"

RISE_WARN = 90.0    # percent toward a rise
FALL_WARN = -90.0


@dataclass
class PriceChange:
    player: Player
    old_price: float
    new_price: float
    owned: bool

    @property
    def delta(self) -> float:
        return round(self.new_price - self.old_price, 1)

    @property
    def rose(self) -> bool:
        return self.delta > 0


def _read() -> dict:
    if not SNAPSHOT.exists():
        return {}
    try:
        return json.loads(SNAPSHOT.read_text()).get("players", {})
    except json.JSONDecodeError:
        return {}


def _write(players: list[Player]) -> None:
    SNAPSHOT.write_text(json.dumps({
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "players": {str(p.id): {"price": p.price, "name": p.name} for p in players},
    }, indent=1))


def check(owned: list[Player], watched: list[Player]) -> list[PriceChange]:
    prev = _read()
    owned_ids = {p.id for p in owned}
    everyone = {p.id: p for p in owned + watched}

    changes = []
    for pid, p in everyone.items():
        before = prev.get(str(pid))
        if before is None:
            continue
        if abs(before["price"] - p.price) > 1e-9:
            changes.append(PriceChange(p, before["price"], p.price, pid in owned_ids))

    _write(list(everyone.values()))
    return changes


def imminent(players: list[Player], owned_ids: set[int]) -> list[Player]:
    """Players close to a price change tonight."""
    out = []
    for p in players:
        pct = p.price_rise_percent
        if pct >= RISE_WARN or pct <= FALL_WARN:
            out.append(p)
    return out


def to_alerts(changes: list[PriceChange]) -> list[Alert]:
    alerts = []
    for c in changes:
        tag = "OWNED" if c.owned else "WATCHLIST"
        direction = "rose" if c.rose else "fell"
        # A watchlist rise costs you money; an owned fall costs you value.
        hurts = (c.rose and not c.owned) or (not c.rose and c.owned)
        alerts.append(Alert(
            title=f"{'📈' if c.rose else '📉'} {c.player.name} {direction} to £{c.new_price:.1f}m",
            body=(f"[{tag}] {c.player.label()}\n"
                  f"£{c.old_price:.1f}m → £{c.new_price:.1f}m ({c.delta:+.1f})\n"
                  f"Form {c.player.form} · owned by {c.player.selected_by}%"
                  + ("\n\nThis one costs you." if hurts else "")),
            priority="default" if hurts else "low",
            tags=["chart_with_upwards_trend" if c.rose else "chart_with_downwards_trend"],
            dedupe_key=f"price:{c.player.id}:{c.new_price}",
        ))
    return alerts


def imminent_alerts(players: list[Player], owned_ids: set[int]) -> list[Alert]:
    alerts = []
    for p in players:
        rising = p.price_rise_percent >= RISE_WARN
        owned = p.id in owned_ids
        if rising and owned:
            continue  # a rise on a player you already own is free money, not an action
        alerts.append(Alert(
            title=f"⏰ {p.name} may {'rise' if rising else 'fall'} tonight",
            body=(f"{p.label()} is at {p.price_rise_percent:.0f}% toward a "
                  f"{'rise' if rising else 'fall'}.\n"
                  + ("Buy before ~01:30 UK if you want him at this price."
                     if rising else
                     "Selling after a fall loses you £0.1m of value.")),
            priority="high" if not rising and owned else "default",
            tags=["alarm_clock"],
            dedupe_key=f"price-imminent:{p.id}:{datetime.now(timezone.utc):%Y-%m-%d}",
        ))
    return alerts
