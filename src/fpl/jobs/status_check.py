"""Job: injury/status watch. Runs every 2h, 08:00-22:00."""
from __future__ import annotations

from ..engine import status
from ..notify import Alert
from .context import Context


def run(ctx: Context) -> int:
    changes, flagged = status.check(ctx.owned, ctx.watched)
    for alert in status.to_alerts(changes):
        ctx.dispatcher.send(alert)

    # Spec section 6 — abandon-plan triggers.
    xi_ids = {p.player.id for p in ctx.squad.xi}
    xi_flagged = [p for p in flagged if p.id in xi_ids]
    haaland = ctx.bs.player(411)

    if haaland and haaland.is_flagged:
        ctx.dispatcher.send(Alert(
            title="🚨 HAALAND FLAGGED — plan trigger",
            body=(f"{haaland.label()} — {haaland.status_text}"
                  f"{', ' + str(haaland.effective_chance) + '% to play' if haaland.effective_chance < 100 else ''}\n"
                  f"{haaland.news}\n\n"
                  "This breaks the captaincy AND the GW7 Triple Captain at once.\n"
                  "It is an abandon-plan trigger on its own — see Wildcard Shape C."),
            priority="urgent", tags=["rotating_light"],
            dedupe_key=f"haaland-flag:{haaland.status}:{haaland.chance}",
        ))

    if len(xi_flagged) >= 2:
        ctx.dispatcher.send(Alert(
            title=f"🚨 {len(xi_flagged)} starting XI players flagged",
            body=("Abandon-plan trigger met (2+ XI flagged in one week):\n"
                  + "\n".join(f"  • {p.label()} — {p.status_text}: {p.news or 'no news'}"
                              for p in xi_flagged)
                  + "\n\nIf a second trigger is also true, pull the Wildcard forward."),
            priority="urgent", tags=["rotating_light"],
            dedupe_key="xi-flagged:" + ",".join(sorted(str(p.id) for p in xi_flagged)),
        ))

    if not changes and ctx.dispatcher.dry_run:
        print(f"No status changes since last snapshot. "
              f"Currently flagged in squad: "
              f"{', '.join(p.name for p in flagged) or 'none'}")
    return len(changes)
