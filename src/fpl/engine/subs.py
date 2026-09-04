"""Substitutions — who to bring on from your own bench, and why.

The transfer planner answers "who should I buy". This answers the cheaper
question most managers actually face on a Friday: given the fifteen players you
already own, is the right eleven on the pitch?

Everything here is deterministic and derived from live data. No model, no key,
no cost.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from ..api.model import Player
from .fixtures import FixtureBook
from .squad import Pick, Squad

# FPL's legal formations: exactly 1 keeper, then these bounds.
MIN_DEF, MAX_DEF = 3, 5
MIN_MID, MAX_MID = 2, 5
MIN_FWD, MAX_FWD = 1, 3


@dataclass
class Sub:
    out_id: int
    out_name: str
    out_club: str
    out_pos: str
    out_form: float
    out_fdr: int
    in_id: int
    in_name: str
    in_club: str
    in_pos: str
    in_form: float
    in_fdr: int
    severity: str          # critical | warning | info
    headline: str
    reasons: list[str]
    formation_after: str
    score: float

    def dict(self) -> dict:
        return asdict(self)


def _fdr(fb: FixtureBook, p: Player, gw: int) -> int:
    fx = fb.for_team(p.raw["team"], gw)
    return min((f.difficulty for f in fx), default=5)


def _fixture_label(fb: FixtureBook, p: Player, gw: int) -> str:
    fx = fb.for_team(p.raw["team"], gw)
    if not fx:
        return "no fixture"
    f = fx[0]
    return f"{f.opponent} {'at home' if f.home else 'away'}"


def _has_fixture(fb: FixtureBook, p: Player, gw: int) -> bool:
    return bool(fb.for_team(p.raw["team"], gw))


def _formation(xi: list[Player]) -> tuple[int, int, int]:
    return (sum(1 for p in xi if p.pos == "DEF"),
            sum(1 for p in xi if p.pos == "MID"),
            sum(1 for p in xi if p.pos == "FWD"))


def _legal(xi: list[Player]) -> bool:
    if sum(1 for p in xi if p.pos == "GKP") != 1:
        return False
    d, m, f = _formation(xi)
    return (MIN_DEF <= d <= MAX_DEF and MIN_MID <= m <= MAX_MID
            and MIN_FWD <= f <= MAX_FWD and d + m + f == 10)


def suggest(sq: Squad, fb: FixtureBook, gw: int) -> list[Sub]:
    """Every legal bench-for-XI swap worth making, best first."""
    xi_picks: list[Pick] = sq.xi
    bench_picks: list[Pick] = sq.bench
    out: list[Sub] = []

    for bp in bench_picks:
        bench_p = bp.player
        # A player who can't play can't rescue anyone.
        if bench_p.is_flagged and bench_p.effective_chance <= 25:
            continue
        if not _has_fixture(fb, bench_p, gw):
            continue

        for xp in xi_picks:
            xi_p = xp.player
            if bench_p.pos == "GKP" and xi_p.pos != "GKP":
                continue
            if xi_p.pos == "GKP" and bench_p.pos != "GKP":
                continue

            after = [p.player for p in xi_picks if p.player.id != xi_p.id] + [bench_p]
            if not _legal(after):
                continue

            b_fdr, x_fdr = _fdr(fb, bench_p, gw), _fdr(fb, xi_p, gw)
            x_blank = not _has_fixture(fb, xi_p, gw)
            reasons: list[str] = []
            score = 0.0
            severity = "info"

            if x_blank:
                reasons.append(f"{xi_p.name} has no fixture this gameweek — he scores nothing")
                score += 100
                severity = "critical"
            elif xi_p.is_flagged:
                chance = xi_p.effective_chance
                reasons.append(
                    f"{xi_p.name} is {xi_p.status_text}"
                    + (f" and only {chance}% to play" if chance < 100 else "")
                    + (f" — {xi_p.news}" if xi_p.news else ""))
                score += 60 if chance <= 25 else 30
                severity = "critical" if chance <= 25 else "warning"

            form_gap = bench_p.form - xi_p.form
            if form_gap > 0:
                reasons.append(f"{bench_p.name} is on form {bench_p.form} against "
                               f"{xi_p.name}'s {xi_p.form}")
                score += form_gap * 4
            elif form_gap < 0 and not x_blank and not xi_p.is_flagged:
                continue          # don't bench a better player on a whim

            caveats: list[str] = []
            if not x_blank and b_fdr < x_fdr:
                reasons.append(
                    f"{bench_p.name} has the kinder fixture — "
                    f"{_fixture_label(fb, bench_p, gw)} (difficulty {b_fdr}) against "
                    f"{_fixture_label(fb, xi_p, gw)} (difficulty {x_fdr})")
                score += (x_fdr - b_fdr) * 3
            elif not x_blank and b_fdr > x_fdr:
                # A form edge should not quietly override a worse fixture, and
                # the manager deserves to see the argument against.
                score -= (b_fdr - x_fdr) * 5
                caveats.append(
                    f"Against that: {bench_p.name} has the harder game — "
                    f"{_fixture_label(fb, bench_p, gw)} (difficulty {b_fdr}) against "
                    f"{_fixture_label(fb, xi_p, gw)} (difficulty {x_fdr})")

            mins_gap = int(bench_p.raw.get("minutes") or 0) - int(xi_p.raw.get("minutes") or 0)
            if mins_gap > 90:
                reasons.append(f"{bench_p.name} has played {mins_gap} more minutes, "
                               f"so he is the likelier starter")
                score += 4

            if not reasons or score < 6:
                continue
            reasons = reasons + caveats

            d, m, f = _formation(after)
            out.append(Sub(
                out_id=xi_p.id, out_name=xi_p.name, out_club=xi_p.team_short,
                out_pos=xi_p.pos, out_form=xi_p.form, out_fdr=x_fdr,
                in_id=bench_p.id, in_name=bench_p.name, in_club=bench_p.team_short,
                in_pos=bench_p.pos, in_form=bench_p.form, in_fdr=b_fdr,
                severity=severity,
                headline=f"Bring {bench_p.name} on for {xi_p.name}",
                reasons=reasons, formation_after=f"{d}-{m}-{f}",
                score=round(score, 1),
            ))

    out.sort(key=lambda s: -s.score)

    # A bench player can only come on once, and an XI player can only go off
    # once — so take the best pairing, retire both, and repeat. Deduping only
    # by the outgoing player would list the same substitute against every
    # weak starter, which reads like six options when it is really one.
    used_in: set[int] = set()
    used_out: set[int] = set()
    chosen: list[Sub] = []
    for s in out:
        if s.in_id in used_in or s.out_id in used_out:
            continue
        used_in.add(s.in_id)
        used_out.add(s.out_id)
        chosen.append(s)

    # Each swap after the first assumed the original XI, so its formation note
    # can be wrong. Recompute along the chain.
    xi_now = [p.player for p in xi_picks]
    for s in chosen:
        xi_now = [p for p in xi_now if p.id != s.out_id]
        xi_now.append(next(b.player for b in bench_picks if b.player.id == s.in_id))
        d, m, f = _formation(xi_now)
        s.formation_after = f"{d}-{m}-{f}"
    return chosen


def bench_order(sq: Squad, fb: FixtureBook, gw: int) -> list[dict]:
    """How the bench should be ordered, and whether it currently is.

    Bench order only pays out when someone in the XI doesn't play, so it should
    rank by who is most likely to play and score.
    """
    outfield = [p for p in sq.bench if p.player.pos != "GKP"]
    def rank(pick: Pick) -> float:
        p = pick.player
        if p.is_flagged and p.effective_chance <= 25:
            return -100.0
        if not _has_fixture(fb, p, gw):
            return -50.0
        return p.form * 2 + (5 - _fdr(fb, p, gw)) * 1.5 + min(
            int(p.raw.get("minutes") or 0) / 90.0, 3) * 2

    ideal = sorted(outfield, key=lambda x: -rank(x))
    rows = []
    for i, pick in enumerate(ideal):
        p = pick.player
        rows.append({
            "slot": i + 1,
            "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
            "form": p.form, "fdr": _fdr(fb, p, gw),
            "playing": _has_fixture(fb, p, gw),
            "flagged": p.is_flagged,
            "current_slot": pick.position - 11,
            "moved": (pick.position - 11) != (i + 1),
        })
    return rows
