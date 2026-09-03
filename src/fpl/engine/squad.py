"""Resolve the current squad — live from the API, or the plan's GW3 fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..api.client import FPLClient, FPLError
from ..api.model import Bootstrap, Player
from ..config import Config

log = logging.getLogger(__name__)


@dataclass
class Pick:
    player: Player
    position: int          # 1-11 = XI, 12-15 = bench in order
    is_captain: bool = False
    is_vice_captain: bool = False
    multiplier: int = 1

    @property
    def on_bench(self) -> bool:
        return self.position > 11


@dataclass
class Squad:
    picks: list[Pick]
    event: int
    bank: float
    value: float
    source: str            # "api" | "plan-fallback"
    # True when `event` is a completed gameweek and a later deadline is still
    # open — i.e. transfers you have already made are NOT reflected here.
    stale: bool = False
    chip: str | None = None

    @property
    def xi(self) -> list[Pick]:
        return [p for p in self.picks if not p.on_bench]

    @property
    def bench(self) -> list[Pick]:
        return sorted((p for p in self.picks if p.on_bench), key=lambda p: p.position)

    @property
    def players(self) -> list[Player]:
        return [p.player for p in self.picks]

    @property
    def captain(self) -> Player | None:
        return next((p.player for p in self.picks if p.is_captain), None)

    @property
    def vice(self) -> Player | None:
        return next((p.player for p in self.picks if p.is_vice_captain), None)

    @property
    def total_value(self) -> float:
        """Selling value isn't public; this is squad price at current cost."""
        return round(sum(p.player.price for p in self.picks), 1)

    def formation(self) -> str:
        d = sum(1 for p in self.xi if p.player.pos == "DEF")
        m = sum(1 for p in self.xi if p.player.pos == "MID")
        f = sum(1 for p in self.xi if p.player.pos == "FWD")
        return f"{d}-{m}-{f}"

    def by_club(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.picks:
            out[p.player.team_short] = out.get(p.player.team_short, 0) + 1
        return out


def _latest_event_with_picks(bs: Bootstrap) -> int | None:
    cur = bs.current_event()
    return cur["id"] if cur else None


def resolve(cfg: Config, client: FPLClient, bs: Bootstrap,
            event: int | None = None) -> Squad:
    """Live picks if team_id is configured, otherwise the plan's GW3 squad."""
    if cfg.team_id:
        gw = event or _latest_event_with_picks(bs)
        if gw:
            try:
                data = client.picks(int(cfg.team_id), gw)
                entry = client.entry(int(cfg.team_id))
                picks = [
                    Pick(
                        player=bs.player(p["element"]),
                        position=p["position"],
                        is_captain=p["is_captain"],
                        is_vice_captain=p["is_vice_captain"],
                        multiplier=p["multiplier"],
                    )
                    for p in data["picks"]
                ]
                eh = data.get("entry_history", {})
                nxt = bs.next_event()
                squad = Squad(
                    picks=picks,
                    event=gw,
                    bank=eh.get("bank", 0) / 10.0,
                    value=eh.get("value", 0) / 10.0,
                    source="api",
                    chip=data.get("active_chip"),
                    stale=bool(nxt and nxt["id"] != gw),
                )
                # Picks for the upcoming gameweek aren't public yet, so prefer
                # the hand-recorded pending squad when one is current.
                if squad.stale and nxt:
                    pending = _pending(cfg, bs, nxt["id"], live_bank=squad.bank)
                    if pending is not None:
                        return pending
                return squad
            except FPLError as exc:
                log.warning("live picks unavailable (%s) — falling back to the plan", exc)

    return _fallback(cfg, bs)


def _pending(cfg: Config, bs: Bootstrap, next_gw: int,
             live_bank: float = 0.0) -> Squad | None:
    """The hand-recorded squad for the upcoming deadline, if it is current."""
    spec = cfg.pending_squad()
    if not spec or int(spec.get("gw", -1)) != int(next_gw):
        return None
    sq = _from_spec(cfg, bs, spec, next_gw, "pending-recorded")
    sq.bank = live_bank
    return sq


def _fallback(cfg: Config, bs: Bootstrap) -> Squad:
    nxt = bs.next_event()
    gw = nxt["id"] if nxt else 0
    return _from_spec(cfg, bs, cfg.pending_squad(), gw, "plan-fallback")


def _from_spec(cfg: Config, bs: Bootstrap, squad: dict, gw: int,
               source: str) -> Squad:
    picks: list[Pick] = []
    pos = 1
    for entry in squad.get("starting_xi", []):
        picks.append(Pick(
            player=bs.player(entry["id"]), position=pos,
            is_captain=bool(entry.get("captain")),
            is_vice_captain=bool(entry.get("vice_captain")),
            multiplier=2 if entry.get("captain") else 1,
        ))
        pos += 1
    for entry in squad.get("bench", []):
        picks.append(Pick(player=bs.player(entry["id"]), position=pos))
        pos += 1

    return Squad(
        picks=picks, event=gw, bank=0.0,
        value=round(sum(p.player.price for p in picks), 1),
        source=source,
    )


def staleness_note(sq: "Squad", next_gw: int | None, amended: bool = False) -> str:
    """The public API exposes picks only for gameweeks that have started.

    Transfers made for the upcoming deadline, and any captain change, are
    invisible until that gameweek begins — `entry/{id}/event/{gw}/picks/`
    404s, and `entry/{id}/transfers/` stays empty. Only the auth-gated
    `my-team/{id}` shows a pending squad, and this tool deliberately avoids it.
    """
    if amended:
        return (f"Showing your GW{next_gw} squad with the transfers you've recorded "
                f"applied. FPL doesn't publish a squad before its gameweek starts, so "
                f"these came from you — everything else below is live.")
    if sq.source == "pending-recorded":
        spec = ""
        return (f"Your GW{sq.event} team as recorded by hand in "
                f"season-plan.yaml{spec} — the public API cannot see a squad "
                f"before its gameweek starts. Prices, form, fixtures and flags "
                f"below are all live.")
    if sq.source != "api":
        return ("Squad from your season plan — team_id is not configured, "
                "so this is not your live team.")
    if sq.stale and next_gw:
        return (f"This is your GW{sq.event} team as it was played. Transfers, "
                f"captain changes and bench order you have already set for "
                f"GW{next_gw} are NOT visible here — the public API only "
                f"publishes picks once a gameweek starts. Check the FPL site "
                f"to confirm your pending team.")
    return f"Live GW{sq.event} team."
