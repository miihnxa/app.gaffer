"""GW6 Wildcard squad builder.

Given a Shape from section 4 of the plan, build a full legal 15 that fits the
budget, respects 3-per-club, attacks the GW6-10 fixture swing, and — the job
the Wildcard exists for — puts four genuine starters on the bench so the GW8
Bench Boost is worth playing.

Advice only. It proposes a squad; you type it in.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..api.model import Bootstrap, Player
from .fixtures import FixtureBook

SQUAD_SHAPE = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
MIN_PRICE = {"GKP": 4.0, "DEF": 4.0, "MID": 4.5, "FWD": 4.5}
MAX_PER_CLUB = 3


def _fdr5(fb: FixtureBook, p: Player, gw: int, n: int = 5) -> float:
    return fb.difficulty_score(p.raw["team"], gw, n)


def score(p: Player, fb: FixtureBook, gw: int) -> float:
    """Form and fixtures, weighted. Deliberately simple — the spec rules out
    predictive modelling in v1, so this ranks on published numbers only."""
    ppg = float(p.raw.get("points_per_game") or 0)
    fixture_bonus = (5.0 - _fdr5(fb, p, gw)) * 1.2
    minutes = int(p.raw.get("minutes") or 0)
    starter = min(minutes / 270.0, 1.0)          # 3 full games = a nailed starter
    return round(p.form * 2.0 + ppg * 1.5 + fixture_bonus + starter * 2.0, 3)


def is_candidate(p: Player, min_minutes: int) -> bool:
    return (
        p.status == "a"
        and not p.is_flagged
        and p.raw.get("can_select", True)
        and int(p.raw.get("minutes") or 0) >= min_minutes
    )


@dataclass
class BuiltSquad:
    players: list[Player]
    shape_key: str
    budget: float
    gw: int
    locked: set[int] = field(default_factory=set)

    @property
    def cost(self) -> float:
        return round(sum(p.price for p in self.players), 1)

    @property
    def spare(self) -> float:
        return round(self.budget - self.cost, 1)

    def by_pos(self, pos: str) -> list[Player]:
        return [p for p in self.players if p.pos == pos]

    def clubs(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.players:
            out[p.team_short] = out.get(p.team_short, 0) + 1
        return out

    def legal(self) -> list[str]:
        errs = []
        for pos, n in SQUAD_SHAPE.items():
            got = len(self.by_pos(pos))
            if got != n:
                errs.append(f"{got} {pos}, need {n}")
        for club, n in self.clubs().items():
            if n > MAX_PER_CLUB:
                errs.append(f"{n} from {club}, max {MAX_PER_CLUB}")
        if self.cost > self.budget + 1e-9:
            errs.append(f"£{self.cost:.1f}m costs more than £{self.budget:.1f}m")
        return errs

    def split(self, fb: FixtureBook) -> tuple[list[Player], list[Player]]:
        """Best legal XI by score; the rest is the bench."""
        ranked = sorted(self.players,
                        key=lambda p: (p.id not in self.locked, -score(p, fb, self.gw)))
        gks = [p for p in ranked if p.pos == "GKP"]
        xi = [gks[0]]
        pool = [p for p in ranked if p.pos != "GKP"]
        for pos, need in (("DEF", 3), ("MID", 2), ("FWD", 1)):
            picks = [p for p in pool if p.pos == pos][:need]
            xi += picks
            pool = [p for p in pool if p not in picks]
        xi += pool[: 11 - len(xi)]
        bench = [p for p in self.players if p not in xi]
        bench.sort(key=lambda p: (p.pos == "GKP", -score(p, fb, self.gw)))
        return xi, bench

    def bench_readiness(self, fb: FixtureBook, games_played: int = 3) -> list[dict]:
        """Spec 2.5 — is this bench actually worth boosting in GW8?"""
        _, bench = self.split(fb)
        out = []
        played = max(1, games_played)
        for p in bench:
            minutes = int(p.raw.get("minutes") or 0)
            fx = fb.for_team(p.raw["team"], self.gw)
            # Share of available minutes so far — comparable early in the season,
            # when even a nailed starter has only played a couple of games.
            share = minutes / (90.0 * played)
            starts = share * 3
            verdict = ("nailed" if share >= 0.85 else
                       "rotation risk" if share >= 0.4 else "not a starter")
            out.append({
                "name": p.name, "club": p.team_short, "pos": p.pos,
                "price": p.price, "form": p.form, "minutes": minutes,
                "fixture": fx[0].label() if fx else "BLANK",
                "fdr": fx[0].difficulty if fx else 5,
                "verdict": verdict,
                "share": round(share, 2),
                "ok": share >= 0.4 and bool(fx),
            })
        return out


FORMATIONS = [(3, 4, 3), (3, 5, 2), (4, 4, 2), (4, 3, 3), (4, 5, 1), (5, 3, 2), (5, 4, 1)]


def bench_score(p: Player, fb: FixtureBook, gw: int, games: int) -> float:
    """A bench player's job on Bench Boost week is to play. Minutes first,
    fixture second, points third — the opposite weighting to a starter."""
    share = min(int(p.raw.get("minutes") or 0) / (90.0 * max(games, 1)), 1.0)
    fixture = (5.0 - _fdr5(fb, p, gw)) * 0.8
    return round(share * 10.0 + fixture + p.form * 0.6, 3)


def _fill(need: dict[str, int], pool: list[Player], budget: float,
          clubs: dict[str, int], key) -> tuple[list[Player], float]:
    """Greedy fill of `need` from `pool`, never spending so much that the
    remaining slots can no longer be filled."""
    picked: list[Player] = []
    remaining = dict(need)
    floors = {pos: sorted(p.price for p in pool if p.pos == pos) or [MIN_PRICE[pos]]
              for pos in need}

    def reserve(after: dict[str, int]) -> float:
        return sum(sum(floors[pos][:n]) for pos, n in after.items() if n > 0)

    for cand in sorted(pool, key=lambda p: -key(p)):
        if not any(remaining.values()):
            break
        if remaining.get(cand.pos, 0) <= 0:
            continue
        if clubs.get(cand.team_short, 0) >= MAX_PER_CLUB:
            continue
        after = dict(remaining)
        after[cand.pos] -= 1
        if cand.price + reserve(after) > budget + 1e-9:
            continue
        picked.append(cand)
        budget -= cand.price
        remaining = after
        clubs[cand.team_short] = clubs.get(cand.team_short, 0) + 1

    # Anything still short: take the cheapest legal option regardless of score.
    for pos, n in remaining.items():
        for _ in range(n):
            for cand in sorted(pool, key=lambda p: p.price):
                if cand in picked or cand.pos != pos:
                    continue
                if clubs.get(cand.team_short, 0) >= MAX_PER_CLUB:
                    continue
                if cand.price > budget + 1e-9:
                    continue
                picked.append(cand)
                budget -= cand.price
                clubs[cand.team_short] = clubs.get(cand.team_short, 0) + 1
                break
    return picked, budget


def build_squad(bs: Bootstrap, fb: FixtureBook, budget: float, gw: int, *,
                locked_ids: list[int] | None = None,
                bench_budget: float = 19.0,
                min_minutes: int = 90,
                games_played: int = 3,
                shape_key: str = "-") -> BuiltSquad:
    """Build a legal 15 under `budget`, keeping `locked_ids`.

    Two stages, because the two goals compete for the same money. The bench is
    bought FIRST, out of a ring-fenced budget: buy the XI first and the greedy
    spends every last pound on starters, leaving £4.0m fodder on the bench —
    which is exactly the position a Wildcard is meant to fix.
    """
    locked_ids = list(dict.fromkeys(locked_ids or []))
    locked = [bs.player(i) for i in locked_ids if bs.player(i)]

    pool = [p for p in bs.all_players()
            if is_candidate(p, min_minutes) and p.id not in {l.id for l in locked}]

    best: BuiltSquad | None = None
    best_total = -1.0

    for d, m, f in FORMATIONS:
        xi_need = {"GKP": 1, "DEF": d, "MID": m, "FWD": f}
        bench_need = {"GKP": 1, "DEF": 5 - d, "MID": 5 - m, "FWD": 3 - f}
        if any(v < 0 for v in bench_need.values()):
            continue

        clubs: dict[str, int] = {}
        squad: list[Player] = []
        xi_left = dict(xi_need)
        bench_left = dict(bench_need)

        ok = True
        locked_on_bench: list[Player] = []
        for p in locked:
            if clubs.get(p.team_short, 0) >= MAX_PER_CLUB:
                ok = False
                break
            if xi_left.get(p.pos, 0) > 0:
                xi_left[p.pos] -= 1
            elif p.pos == "GKP" and bench_left.get(p.pos, 0) > 0:
                # Two keepers, one XI slot — a locked keeper may sit.
                bench_left[p.pos] -= 1
                locked_on_bench.append(p)
            else:
                # You locked this player to start him. A formation that benches
                # him isn't a candidate.
                ok = False
                break
            squad.append(p)
            clubs[p.team_short] = clubs.get(p.team_short, 0) + 1
        if not ok:
            continue

        locked_spend = sum(p.price for p in squad)
        bench_pot = max(0.0, bench_budget - sum(p.price for p in locked_on_bench))

        bench_picks, _ = _fill(
            bench_left, pool, min(bench_pot, budget - locked_spend), clubs,
            key=lambda p: bench_score(p, fb, gw, games_played))
        spent = locked_spend + sum(p.price for p in bench_picks)

        xi_picks, _ = _fill(
            xi_left, [p for p in pool if p not in bench_picks],
            budget - spent, clubs, key=lambda p: score(p, fb, gw))

        squad = squad + bench_picks + xi_picks
        if len(squad) != 15:
            continue

        built = BuiltSquad(squad, shape_key, budget, gw, set(locked_ids))
        if built.legal():
            continue
        xi, bench = built.split(fb)
        total = (sum(score(p, fb, gw) for p in xi)
                 + sum(bench_score(p, fb, gw, games_played) for p in bench) * 0.5)
        if total > best_total:
            best_total, best = total, built

    if best is None:
        raise RuntimeError(
            f"could not build a legal squad at £{budget:.1f}m with a "
            f"£{bench_budget:.1f}m bench — try a lower bench budget")
    return best


def build(cfg, bs: Bootstrap, fb: FixtureBook, shape_key: str, budget: float,
          gw: int, min_minutes: int = 90, games_played: int = 3,
          bench_budget: float | None = None) -> BuiltSquad:
    """Build for one of the Wildcard Shapes defined in the season plan."""
    shapes = cfg.plan.get("wildcard_shapes", {})
    brief = cfg.plan.get("wildcard_brief", {})
    if shape_key not in shapes:
        raise KeyError(f"unknown shape {shape_key!r} — have {list(shapes)}")
    if bench_budget is None:
        bench_budget = float(brief.get("bench_budget_target", 19.0))

    locked_ids = (list(brief.get("keep_non_negotiable", []))
                  + list(shapes[shape_key].get("forwards", [])))
    return build_squad(bs, fb, budget, gw, locked_ids=locked_ids,
                       bench_budget=bench_budget, min_minutes=min_minutes,
                       games_played=games_played, shape_key=shape_key)
