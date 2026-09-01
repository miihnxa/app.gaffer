"""Suggest replacements for a player you own.

Every candidate is run through the same guard as `fpl transfer`, so nothing is
suggested that your own rules would block.
"""
from __future__ import annotations

from ..api.model import Bootstrap, Player
from .fixtures import FixtureBook
from .form import check_transfer
from .wildcard import is_candidate, score


def suggest(bs: Bootstrap, fb: FixtureBook, out_player: Player, *,
            owned_ids: set[int], bank: float, gw: int, clubs: dict[str, int],
            free_transfers: int = 1, no_hits_before_gw: int = 6,
            limit: int = 5, min_minutes: int = 90) -> list[dict]:
    budget = out_player.price + bank
    pool = [
        p for p in bs.all_players()
        if p.pos == out_player.pos
        and p.id not in owned_ids
        and p.price <= budget + 1e-9
        and is_candidate(p, min_minutes)
        and p.form > out_player.form          # the guard, applied up front
    ]
    pool.sort(key=lambda p: -score(p, fb, gw))

    out = []
    for cand in pool:
        v = check_transfer(
            out_player, cand, bank=bank, gw=gw,
            no_hits_before_gw=no_hits_before_gw, free_transfers=free_transfers,
            squad_clubs=clubs,
        )
        if v.blocked:
            continue
        fx = fb.for_team(cand.raw["team"], gw)
        out.append({
            "id": cand.id, "name": cand.name, "club": cand.team_short,
            "pos": cand.pos, "price": cand.price, "form": cand.form,
            "points": cand.total_points, "selected": cand.selected_by,
            "cost": round(cand.price - out_player.price, 1),
            "form_delta": round(cand.form - out_player.form, 1),
            "fdr5": fb.difficulty_score(cand.raw["team"], gw, 5),
            "fixture": (f"{fx[0].opponent} ({'H' if fx[0].home else 'A'})"
                        if fx else "BLANK"),
            "fdr": fx[0].difficulty if fx else 5,
            "notes": v.notes,
        })
        if len(out) >= limit:
            break
    return out
