"""Job: live gameweek tracker. Only polls while fixtures are actually running."""
from __future__ import annotations

from ..engine import fixtures as fx_engine
from ..engine import live
from ..notify import Alert
from .context import Context


def run(ctx: Context, force: bool = False) -> int:
    cur = ctx.bs.current_event()
    if not cur:
        return 0
    gw = cur["id"]
    fb = fx_engine.FixtureBook(ctx.bs, ctx.client.fixtures())

    if not force and not live.fixtures_in_play(ctx.bs, fb, gw):
        if ctx.dispatcher.dry_run:
            print(f"No GW{gw} fixture in play. Nothing to poll.")
        return 0

    rows, total = live.snapshot(ctx.client, ctx.bs, ctx.squad, gw)
    if ctx.dispatcher.dry_run:
        print(live.render(rows, total, gw))

    # One notification per scoring event, deduped on the running count so a
    # second goal from the same player still fires.
    sent = 0
    for r in rows:
        if r.benched:
            continue
        for key, (icon, label) in live.WATCHED.items():
            n = int(r.stats.get(key, 0) or 0)
            if not n:
                continue
            ctx.dispatcher.send(Alert(
                title=f"{icon} {r.player.name} — {label}"
                      + (f" x{n}" if n > 1 else ""),
                body=(f"{r.player.label()}\n"
                      f"{r.contributed} pts this gameweek"
                      + (" (captain)" if r.multiplier > 1 else "")
                      + f"\n\nGW{gw} running total: {total}"),
                priority="default", tags=["soccer"],
                dedupe_key=f"live:{gw}:{r.player.id}:{key}:{n}",
            ))
            sent += 1
    return sent
