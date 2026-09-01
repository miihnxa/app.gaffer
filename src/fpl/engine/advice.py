"""Turn squad + fixtures + rules into the recommended-changes list.

Spec 2.1 (lineup checker) plus the rule set in spec section 6. Advice only —
the tool never makes a change.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from ..api.model import Bootstrap
from .fixtures import FixtureBook
from .squad import Squad

SEV_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Advice:
    severity: str        # critical | warning | info
    kind: str
    title: str
    detail: str
    players: list[str]

    def dict(self) -> dict:
        return asdict(self)


def build(cfg, bs: Bootstrap, sq: Squad, fb: FixtureBook, gw: int) -> list[Advice]:
    out: list[Advice] = []
    plan = cfg.plan
    rules = plan.get("rules", {})

    xi = sq.xi
    bench = sq.bench

    # --- flagged players in the XI --------------------------------
    for pick in xi:
        p = pick.player
        if not p.is_flagged:
            continue
        out.append(Advice(
            "critical" if p.effective_chance <= 25 else "warning",
            "flag",
            f"{p.name} is {p.status_text} in your XI",
            (p.news or "No news text from FPL.")
            + f" Chance to play: {p.effective_chance}%.",
            [p.name],
        ))

    # --- blank gameweeks ------------------------------------------
    for pick in xi:
        p = pick.player
        if not fb.for_team(p.raw["team"], gw):
            out.append(Advice(
                "critical", "blank",
                f"{p.name} has no fixture in GW{gw}",
                f"{p.team_short} blank this gameweek. He will score 0.",
                [p.name],
            ))

    # --- bench ordering: real starters should be ahead of flags ----
    flagged_bench = [b for b in bench if b.player.is_flagged]
    clean_bench = [b for b in bench if not b.player.is_flagged]
    for f in flagged_bench:
        later = [c for c in clean_bench if c.position > f.position]
        if later:
            out.append(Advice(
                "warning", "bench-order",
                f"{f.player.name} is benched ahead of {later[0].player.name}",
                (f"{f.player.name} is {f.player.status_text} and sits at bench "
                 f"{f.position - 11}, ahead of fit players. Your rule: actual "
                 f"starters ahead of flagged players."),
                [f.player.name, later[0].player.name],
            ))

    # --- bench player with a materially better fixture -------------
    for b in bench:
        if b.player.pos == "GKP" or b.player.is_flagged:
            continue
        bfx = fb.for_team(b.player.raw["team"], gw)
        if not bfx:
            continue
        bdiff = min(f.difficulty for f in bfx)
        for pick in xi:
            if pick.player.pos != b.player.pos or pick.player.is_flagged:
                continue
            xfx = fb.for_team(pick.player.raw["team"], gw)
            xdiff = min((f.difficulty for f in xfx), default=5)
            if bdiff <= xdiff - 2 and b.player.form > pick.player.form:
                out.append(Advice(
                    "info", "swap",
                    f"Consider {b.player.name} over {pick.player.name}",
                    (f"{b.player.name}: {bfx[0].label()} FDR {bdiff}, form "
                     f"{b.player.form}. {pick.player.name}: "
                     f"{xfx[0].label() if xfx else 'BLANK'} FDR {xdiff}, form "
                     f"{pick.player.form}."),
                    [b.player.name, pick.player.name],
                ))
                break

    # --- captain vs the plan ---------------------------------------
    planned = (plan.get("captains") or {}).get(gw)
    if planned and sq.captain and int(planned["id"]) != sq.captain.id:
        out.append(Advice(
            "info", "captain",
            f"Captain differs from the plan for GW{gw}",
            (f"Plan says {planned['name']}"
             + (f" — {planned['note']}" if planned.get("note") else "")
             + f". Currently captained: {sq.captain.name}."),
            [sq.captain.name, planned["name"]],
        ))

    # --- captain fitness -------------------------------------------
    if sq.captain and sq.captain.is_flagged:
        out.append(Advice(
            "critical", "captain-flag",
            f"Your captain {sq.captain.name} is {sq.captain.status_text}",
            f"{sq.captain.news or 'Flagged.'} Vice: "
            f"{sq.vice.name if sq.vice else 'none set'}.",
            [sq.captain.name],
        ))

    # --- never start a player facing your captain's team ------------
    if sq.captain:
        cap_team = sq.captain.raw["team"]
        cap_fx = fb.for_team(cap_team, gw)
        opponents = {f.opponent for f in cap_fx}
        for pick in xi:
            p = pick.player
            if p.id == sq.captain.id:
                continue
            if p.team_short in opponents:
                out.append(Advice(
                    "warning", "captain-clash",
                    f"{p.name} faces your captain's team",
                    (f"{p.team_short} play {sq.captain.team_short} in GW{gw}. "
                     f"Your rule: never start a player whose team faces your captain."),
                    [p.name, sq.captain.name],
                ))

    # --- your own players facing each other -------------------------
    # The plan calls this out for GW3: Gonzalo (FUL) vs Mitchell (CRY).
    # A goal for one kills the other's clean sheet.
    seen: set[tuple[int, int]] = set()
    for a in xi:
        for b in xi:
            if a.player.id >= b.player.id:
                continue
            ta, tb = a.player.raw["team"], b.player.raw["team"]
            if ta == tb:
                continue
            if any(f.opponent == b.player.team_short for f in fb.for_team(ta, gw)):
                key = tuple(sorted((a.player.id, b.player.id)))
                if key in seen:
                    continue
                seen.add(key)
                attacker = a if a.player.pos in ("MID", "FWD") else b
                defender = b if attacker is a else a
                out.append(Advice(
                    "info", "internal-clash",
                    f"{a.player.name} and {b.player.name} face each other",
                    (f"{a.player.team_short} v {b.player.team_short} in GW{gw}. "
                     f"A {attacker.player.name} goal kills "
                     f"{defender.player.name}'s clean sheet."),
                    [a.player.name, b.player.name],
                ))

    # --- squad legality --------------------------------------------
    defs = sum(1 for p in xi if p.player.pos == "DEF")
    if defs < int(rules.get("min_defenders", 3)):
        out.append(Advice("critical", "formation",
                          f"Only {defs} defenders in the XI",
                          "Minimum is 3. This lineup is not legal.", []))

    for club, n in sq.by_club().items():
        if n > int(rules.get("max_players_per_club", 3)):
            out.append(Advice("critical", "club-limit",
                              f"{n} players from {club}",
                              "Maximum is 3 per club.", []))

    # --- chip clock -------------------------------------------------
    out += _chip_advice(cfg, bs, sq, gw)

    out.sort(key=lambda a: SEV_ORDER.get(a.severity, 9))
    return out


def _chip_advice(cfg, bs: Bootstrap, sq: Squad, gw: int) -> list[Advice]:
    out = []
    chips = cfg.plan.get("chips", {})
    # Read the real expiry from the API rather than trusting the config.
    expiry = bs.chip_stop_event("wildcard") or cfg.plan.get("chip_deadline_gw", 19)
    left = expiry - gw

    for name, c in chips.items():
        planned_gw = c.get("planned_gw")
        if planned_gw is None:
            continue
        if planned_gw == gw:
            out.append(Advice(
                "warning", "chip",
                f"{name.upper()} is planned for this gameweek",
                c.get("note", ""), [],
            ))
        elif left <= 4 and planned_gw > gw:
            out.append(Advice(
                "critical", "chip-expiry",
                f"{name.upper()} unused with {left} gameweeks to the GW{expiry} expiry",
                "Chip set 1 expires at the GW"
                f"{expiry} deadline. Unused chips are lost — no rollover.",
                [],
            ))
    return out
