"""Job: mini-league standings + rival squad diffing."""
from __future__ import annotations

from ..engine import league
from ..notify import Alert
from .context import Context


def run(ctx: Context, diff: bool = True) -> int:
    lid = ctx.cfg.league_id
    if not lid:
        if ctx.dispatcher.dry_run:
            print("No league_id set. Run: ./fpl setup --team-id <id>")
        return 0
    tid = ctx.cfg.require_team_id()

    name, rivals = league.standings(ctx.client, int(lid))
    for a in league.movement_alerts(name, rivals, tid):
        ctx.dispatcher.send(a)

    if ctx.dispatcher.dry_run:
        me = league.find_me(rivals, tid)
        print(f"\n{name}")
        for r in rivals[:10]:
            mark = "→" if me and r.entry == me.entry else " "
            move = f" ({r.moved:+d})" if r.moved else ""
            print(f" {mark} {r.rank:>2}. {r.name:<24}{r.manager:<22}"
                  f"{r.total:>5} pts  GW {r.gw_points:>3}{move}")

    if not diff:
        return 0

    cur = ctx.bs.current_event()
    if not cur:
        return 0
    me = league.find_me(rivals, tid)
    if not me:
        return 0
    my_ids = {p.id for p in ctx.owned}
    for r in rivals:
        if r.entry == me.entry:
            continue
        d = league.diff_against(ctx.client, ctx.bs, my_ids, ctx.squad.captain,
                                me, r, cur["id"])
        if d and ctx.dispatcher.dry_run:
            print()
            print(league.render_diff(d))
    return 0
