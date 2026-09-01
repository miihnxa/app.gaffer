"""Job: deadline reminders. Runs hourly; the windows decide when to fire."""
from __future__ import annotations

from ..engine import deadlines
from .context import Context


def run(ctx: Context, force_window: int | None = None) -> int:
    info = deadlines.next_deadline(ctx.bs)
    if info is None:
        return 0

    windows = ctx.cfg.settings.get("deadlines", {}).get(
        "reminders_minutes_before", [1440, 180, 45])
    due = [force_window] if force_window else deadlines.due_reminders(info, windows)

    squad = ctx.squad
    flagged = [p.player.name for p in squad.xi if p.player.is_flagged]
    planned = (ctx.cfg.plan.get("captains", {}) or {}).get(info.gw, {})
    chip = next((name for name, c in (ctx.cfg.plan.get("chips") or {}).items()
                 if c.get("planned_gw") == info.gw), None)

    ft = "?"
    if squad.source == "api":
        ft = _free_transfers(ctx, info.gw)

    for w in due:
        ctx.dispatcher.send(deadlines.to_alert(
            info, w, ctx.cfg.tz,
            free_transfers=ft,
            captain=(squad.captain.name if squad.captain else "?")
                    + (f"  (plan: {planned.get('name')})" if planned else ""),
            flagged=flagged, chip=chip,
        ))

    if ctx.dispatcher.dry_run and not due:
        print(f"GW{info.gw} deadline {info.local(ctx.cfg.tz):%a %d %b %H:%M} "
              f"— {info.countdown()} away. No reminder window is open "
              f"(windows: {windows} minutes).")
    return len(due)


def _free_transfers(ctx: Context, gw: int) -> int | str:
    """Derive free transfers from history. FPL banks up to 5."""
    try:
        hist = ctx.client.history(ctx.cfg.require_team_id())
        transfers = ctx.client.transfers(ctx.cfg.require_team_id())
    except Exception:  # noqa: BLE001
        return "?"
    made = {}
    for t in transfers:
        made[t["event"]] = made.get(t["event"], 0) + 1
    ft = 1
    for row in hist.get("current", []):
        ev = row["event"]
        if ev >= gw:
            continue
        used = made.get(ev, 0)
        if row.get("event_transfers_cost", 0) > 0:
            ft = 1
        else:
            ft = max(1, min(5, ft - used + 1))
    return ft
