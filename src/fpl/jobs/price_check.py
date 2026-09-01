"""Job: price + form check. Runs daily 02:00 UK, after the ~01:30 price run."""
from __future__ import annotations

from ..engine import form, prices
from .context import Context


def run(ctx: Context) -> int:
    # Force a fresh pull — a 30-minute cache would hide the overnight change.
    ctx.bs = type(ctx.bs)(ctx.client.bootstrap(force=True))

    changes = prices.check(ctx.owned, ctx.watched)
    for alert in prices.to_alerts(changes):
        ctx.dispatcher.send(alert)

    owned_ids = {p.id for p in ctx.owned}
    soon = prices.imminent(ctx.owned + ctx.watched, owned_ids)
    for alert in prices.imminent_alerts(soon, owned_ids):
        ctx.dispatcher.send(alert)

    for alert in form.collapse_alerts(ctx.owned):
        ctx.dispatcher.send(alert)

    if ctx.dispatcher.dry_run:
        print(form.form_table(ctx.owned, "OWNED — by form"))
        print()
        print(form.form_table(ctx.watched, "WATCHLIST — by form"))
    return len(changes)
