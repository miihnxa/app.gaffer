"""When to play your chips.

Recomputed from live fixtures every time, not read from a plan written weeks
ago. Fixture lists move — cup rounds and postponements create blanks and
doubles that weren't there in September — so a chip plan fixed in advance goes
stale silently. This one re-derives and says when its own advice has changed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from ..api.model import Bootstrap, Player
from .fixtures import FixtureBook

CHIP_NAMES = {
    "wildcard": "Wildcard",
    "3xc": "Triple Captain",
    "bboost": "Bench Boost",
    "freehit": "Free Hit",
}


@dataclass
class ChipPick:
    chip: str
    label: str
    gw: int | None
    headline: str
    reason: str
    detail: list[str] = field(default_factory=list)
    confidence: str = "provisional"   # firm | provisional
    used: bool = False
    used_gw: int | None = None

    def dict(self) -> dict:
        return asdict(self)


def _diff(fb: FixtureBook, p: Player, gw: int) -> int | None:
    fx = fb.for_team(p.raw["team"], gw)
    return min(x.difficulty for x in fx) if fx else None


def _squad_mean(fb: FixtureBook, players: list[Player], gw: int) -> float:
    ds = [d for d in (_diff(fb, p, gw) for p in players) if d is not None]
    return sum(ds) / len(ds) if ds else 5.0


def blanks_and_doubles(bs: Bootstrap, fb: FixtureBook, gw: int) -> tuple[list[str], list[str]]:
    blanks, doubles = [], []
    for tid in bs.teams:
        n = len(fb.for_team(tid, gw))
        if n == 0:
            blanks.append(bs.team_short(tid))
        elif n > 1:
            doubles.append(bs.team_short(tid))
    return blanks, doubles


def _premium(players: list[Player]) -> Player | None:
    """The player a Triple Captain would realistically go on."""
    forwards_mids = [p for p in players if p.pos in ("MID", "FWD")]
    return max(forwards_mids, key=lambda p: p.price, default=None)


def plan(bs: Bootstrap, fb: FixtureBook, players: list[Player], bench: list[Player],
         from_gw: int, expiry: int, used: dict[str, int] | None = None) -> list[ChipPick]:
    used = used or {}
    horizon = list(range(from_gw, expiry + 1))
    picks: list[ChipPick] = []

    # Anything past roughly ten gameweeks out is a provisional fixture list.
    def confidence(gw: int | None) -> str:
        return "firm" if gw is not None and gw - from_gw <= 6 else "provisional"

    # ---- Triple Captain: the premium's kindest home game ------------
    star = _premium(players)
    best_tc, tc_detail = None, []
    if star:
        cands = []
        for gw in horizon:
            for f in fb.for_team(star.raw["team"], gw):
                if not f.home:
                    continue
                opp = next((t for t in bs.teams.values()
                            if t["short_name"] == f.opponent), None)
                away_strength = (opp or {}).get("strength_overall_away", 3)
                cands.append((f.difficulty, away_strength, -gw, gw, f.opponent))
        cands.sort()
        if cands:
            d, strength, _, gw, opp = cands[0]
            best_tc = gw
            tc_detail = [f"{star.name} at home to {opp}, difficulty {d}",
                         "The weakest visitor he gets before the deadline"]
    picks.append(ChipPick(
        "3xc", CHIP_NAMES["3xc"], best_tc,
        f"Triple Captain in GW{best_tc}" if best_tc else "No standout week",
        (f"{star.name}'s easiest home fixture in the window." if star and best_tc
         else "No home fixture stands out for your premium."),
        tc_detail, confidence(best_tc),
        "3xc" in used, used.get("3xc")))

    # ---- Bench Boost: the whole fifteen's easiest week ---------------
    bb_rows = []
    for gw in horizon:
        blanks, doubles = blanks_and_doubles(bs, fb, gw)
        playing = sum(1 for p in players if fb.for_team(p.raw["team"], gw))
        bench_home = sum(1 for p in bench
                         if any(f.home for f in fb.for_team(p.raw["team"], gw)))
        # A double gameweek beats any single-week difficulty edge.
        doubled = sum(1 for p in players if len(fb.for_team(p.raw["team"], gw)) > 1)
        bb_rows.append((-doubled, -playing, _squad_mean(fb, players, gw), -bench_home, gw))
    bb_rows.sort()
    doubled, negplaying, mean, neg_home, bb_gw = bb_rows[0]
    bb_detail = [f"Your squad's mean fixture difficulty is {mean:.2f}, the lowest in the window",
                 f"{-neg_home} of your four bench players are at home"]
    if -doubled:
        bb_detail.insert(0, f"{-doubled} of your players have two fixtures that week")
    picks.append(ChipPick(
        "bboost", CHIP_NAMES["bboost"], bb_gw,
        f"Bench Boost in GW{bb_gw}",
        "Every one of your fifteen plays, on the kindest set of fixtures available."
        if not -doubled else "A double gameweek — the best a Bench Boost ever gets.",
        bb_detail, confidence(bb_gw), "bboost" in used, used.get("bboost")))

    # ---- Wildcard: the best five-week run you can buy into -----------
    wc_rows = []
    for gw in horizon[:-4]:
        ds = []
        for p in players:
            for g in range(gw, gw + 5):
                d = _diff(fb, p, g)
                if d is not None:
                    ds.append(d)
        if ds:
            wc_rows.append((sum(ds) / len(ds), gw))
    wc_rows.sort()
    wc_gw = wc_rows[0][1] if wc_rows else None
    picks.append(ChipPick(
        "wildcard", CHIP_NAMES["wildcard"], wc_gw,
        f"Wildcard in GW{wc_gw}" if wc_gw else "No clear week",
        "The best five-gameweek run you can rebuild into." if wc_gw else "",
        [f"Average difficulty {wc_rows[0][0]:.2f} across GW{wc_gw}-{wc_gw + 4}"] if wc_gw else [],
        confidence(wc_gw), "wildcard" in used, used.get("wildcard")))

    # ---- Free Hit: only worth it against a blank or a bad week -------
    fh_gw, fh_reason, fh_detail = None, "", []
    worst = None
    for gw in horizon:
        blanks, _ = blanks_and_doubles(bs, fb, gw)
        missing = sum(1 for p in players if not fb.for_team(p.raw["team"], gw))
        m = _squad_mean(fb, players, gw)
        if missing >= 4:
            fh_gw, fh_reason = gw, f"{missing} of your players have no fixture"
            fh_detail = [f"Blank gameweek — {', '.join(blanks[:8])}"]
            break
        if worst is None or m > worst[0]:
            worst = (m, gw)
    if fh_gw is None and worst:
        fh_reason = ("No blank gameweek exists in the window, so a Free Hit has "
                     "nothing to rescue. Hold it.")
        fh_detail = [f"Your hardest week is GW{worst[1]} at {worst[0]:.2f} average difficulty",
                     "Cup rounds usually create blanks later — check again around GW9",
                     f"If nothing appears by GW{expiry - 2}, play it anyway rather than lose it"]
    picks.append(ChipPick(
        "freehit", CHIP_NAMES["freehit"], fh_gw,
        f"Free Hit in GW{fh_gw}" if fh_gw else "Hold the Free Hit",
        fh_reason, fh_detail, confidence(fh_gw),
        "freehit" in used, used.get("freehit")))

    return picks


def due_now(picks: list[ChipPick], gw: int) -> list[ChipPick]:
    """Chips whose recommended gameweek is the one about to be played."""
    return [p for p in picks if p.gw == gw and not p.used]


def expiring(picks: list[ChipPick], gw: int, expiry: int,
             warn_within: int = 4) -> list[ChipPick]:
    """Unused chips running out of gameweeks. There is no rollover."""
    if expiry - gw > warn_within:
        return []
    return [p for p in picks if not p.used]
