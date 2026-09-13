"""The recommended team — starting eleven, bench order and armbands.

"What to look at" lists problems. This answers the question behind them: from
the fifteen players you own, which eleven should start, in what bench order, and
who wears the armband?

Players are ranked on a transparent rating built only from published FPL
numbers — form, points per game, minutes, fixture difficulty, home advantage and
fitness. It orders your players against each other; it is not a points
prediction, and the page says so.
"""
from __future__ import annotations

from ..api.model import Player
from .fixtures import FixtureBook
from .squad import Squad

# How much easier or harder a fixture makes a player's week.
FIXTURE_WEIGHT = {1: 1.25, 2: 1.15, 3: 1.0, 4: 0.85, 5: 0.72}
HOME_BUMP = 1.05

# FPL's legal shapes: exactly one keeper, then these bounds, ten outfielders.
FORMATIONS = [(d, m, f)
              for d in range(3, 6) for m in range(2, 6) for f in range(1, 4)
              if d + m + f == 10]

POS_ORDER = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}


def rate(p: Player, fb: FixtureBook, gw: int, games_played: int) -> tuple[float, str]:
    """A player's rating for this gameweek, and the fixture it's based on."""
    fixtures = fb.for_team(p.raw["team"], gw)
    if not fixtures:
        return 0.0, "no fixture"

    # A flagged player with no stated chance is treated as out, not as fine.
    availability = p.effective_chance / 100.0
    if availability <= 0:
        return 0.0, _fixture_text(fixtures)

    form = p.form
    ppg = float(p.raw.get("points_per_game") or 0)
    base = 0.6 * form + 0.4 * ppg

    # Share of the minutes available so far: a nailed starter is 1.0, a
    # squad player who rarely starts drags toward 0.35.
    minutes = int(p.raw.get("minutes") or 0)
    share = min(minutes / (90.0 * max(games_played, 1)), 1.0)
    minutes_factor = 0.35 + 0.65 * share

    # A double gameweek adds both fixtures; a single one uses its own weight.
    fixture_factor = sum(FIXTURE_WEIGHT.get(f.difficulty, 1.0) *
                         (HOME_BUMP if f.home else 1.0) for f in fixtures)

    return round(base * availability * minutes_factor * fixture_factor, 2), \
        _fixture_text(fixtures)


def _fixture_text(fixtures) -> str:
    return ", ".join(f"{f.opponent} {'at home' if f.home else 'away'} "
                     f"(difficulty {f.difficulty})" for f in fixtures)


def recommend(sq: Squad, fb: FixtureBook, gw: int, games_played: int) -> dict:
    players = [pick.player for pick in sq.picks]
    rating: dict[int, float] = {}
    fixture: dict[int, str] = {}
    for p in players:
        rating[p.id], fixture[p.id] = rate(p, fb, gw, games_played)

    def ranked(pos: str) -> list[Player]:
        return sorted((p for p in players if p.pos == pos),
                      key=lambda p: (-rating[p.id], -p.form, p.price))

    gks, defs, mids, fwds = ranked("GKP"), ranked("DEF"), ranked("MID"), ranked("FWD")

    best_shape, best_total = None, -1.0
    for d, m, f in FORMATIONS:
        if len(defs) < d or len(mids) < m or len(fwds) < f or not gks:
            continue
        total = (sum(rating[p.id] for p in defs[:d]) +
                 sum(rating[p.id] for p in mids[:m]) +
                 sum(rating[p.id] for p in fwds[:f]))
        # Ties go to the more attacking shape: forwards and midfielders earn
        # more for a goal than defenders do.
        if total > best_total + 1e-9:
            best_shape, best_total = (d, m, f), total

    d, m, f = best_shape
    xi = [gks[0]] + defs[:d] + mids[:m] + fwds[:f]
    xi_ids = {p.id for p in xi}

    # FPL's bench always starts with the reserve keeper; the outfield order
    # decides who comes on first when a starter doesn't play.
    reserve_gk = gks[1:]
    outfield_bench = sorted((p for p in players if p.id not in xi_ids and p.pos != "GKP"),
                            key=lambda p: -rating[p.id])
    bench = reserve_gk + outfield_bench

    by_rating = sorted(xi, key=lambda p: -rating[p.id])
    captain, vice = by_rating[0], by_rating[1]
    options = [{
        "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
        "rating": rating[p.id], "form": p.form, "fixture": fixture[p.id],
    } for p in by_rating[:3]]
    close = (rating[captain.id] > 0 and
             (rating[captain.id] - rating[vice.id]) / rating[captain.id] < 0.10)

    current_xi = {pick.player.id for pick in sq.xi}
    current_bench = [pick.player.id for pick in sq.bench]
    cur_captain = next((p.player.id for p in sq.picks if p.is_captain), None)
    cur_vice = next((p.player.id for p in sq.picks if p.is_vice_captain), None)

    coming_on = [p for p in xi if p.id not in current_xi]
    going_off = [pick.player for pick in sq.xi if pick.player.id not in xi_ids]
    changes = []
    unpaired = list(going_off)
    for on in sorted(coming_on, key=lambda p: -rating[p.id]):
        off = next((o for o in unpaired if o.pos == on.pos), None) or \
            (unpaired[0] if unpaired else None)
        if off is None:
            continue
        unpaired.remove(off)
        changes.append({
            "on_id": on.id, "on": on.name, "on_club": on.team_short,
            "on_rating": rating[on.id], "on_fixture": fixture[on.id], "on_form": on.form,
            "off_id": off.id, "off": off.name, "off_club": off.team_short,
            "off_rating": rating[off.id], "off_fixture": fixture[off.id], "off_form": off.form,
            "why": _why(on, off, rating, fixture),
        })

    def summary(p: Player) -> dict:
        return {"id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
                "rating": rating[p.id], "form": p.form, "fixture": fixture[p.id],
                "flagged": p.is_flagged, "chance": p.effective_chance}

    return {
        "formation": f"{d}-{m}-{f}",
        "xi": [p.id for p in sorted(xi, key=lambda p: (POS_ORDER[p.pos], -rating[p.id]))],
        "bench": [p.id for p in bench],
        "captain": captain.id,
        "vice": vice.id,
        "captain_options": options,
        "captain_close_call": close,
        "players": {str(p.id): summary(p) for p in players},
        "changes": changes,
        "armband_changed": (cur_captain, cur_vice) != (captain.id, vice.id),
        "bench_reordered": current_bench != [p.id for p in bench],
        "matches_current": (not changes and (cur_captain, cur_vice) == (captain.id, vice.id)
                            and current_bench == [p.id for p in bench]),
    }


def _why(on: Player, off: Player, rating: dict, fixture: dict) -> list[str]:
    reasons = []
    if rating[off.id] == 0 and off.is_flagged:
        reasons.append(f"{off.name} is {off.status_text}"
                       + (f" ({off.effective_chance}% to play)" if off.effective_chance else ""))
    elif fixture[off.id] == "no fixture":
        reasons.append(f"{off.name} has no fixture this gameweek")
    elif off.is_flagged:
        reasons.append(f"{off.name} is only {off.effective_chance}% to play")
    if on.form > off.form:
        reasons.append(f"form {on.form} against {off.form}")
    reasons.append(f"{on.name}: {fixture[on.id]}")
    reasons.append(f"{off.name}: {fixture[off.id]}")
    return reasons
