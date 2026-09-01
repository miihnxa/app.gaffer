"""fpl — command line entry point.

This tool advises. It never acts: no automated transfers, no lineup changes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api.client import FPLClient
from .api.model import Bootstrap
from .config import Config, ConfigError
from .engine import deadlines, fixtures, form, squad as squad_engine
from .jobs import (context, deadline_check, league_check, live_check,
                   price_check, status_check)
from .notify import Alert, build_notifier


def cmd_setup(args) -> int:
    cfg = Config.load()
    client = FPLClient(cfg)
    bs = Bootstrap(client.bootstrap())
    print(f"✓ bootstrap-static OK — {len(bs.all_players())} players, "
          f"{len(bs.events)} gameweeks, schema validated")

    team_id = args.team_id or cfg.team_id
    if not team_id:
        print("\nNo team_id yet. Find it in the URL of your Gameweek History page:")
        print("  https://fantasy.premierleague.com/entry/<TEAM_ID>/history")
        print("Then run:  ./fpl setup --team-id <id>")
        return 1

    entry = client.entry(int(team_id))
    print(f"\n✓ Team {team_id}: \"{entry['name']}\" — "
          f"{entry['player_first_name']} {entry['player_last_name']}")
    print(f"  Overall: {entry['summary_overall_points']} pts, "
          f"rank {entry.get('summary_overall_rank')}")
    print(f"  Squad value £{entry['last_deadline_value']/10:.1f}m, "
          f"bank £{entry['last_deadline_bank']/10:.1f}m")

    if args.team_id:
        cfg.set_entry("team_id", int(args.team_id))
        print(f"  saved team_id to config/settings.yaml")

    leagues = entry.get("leagues", {}).get("classic", [])
    target = (cfg.settings.get("entry") or {}).get("league_name", "")
    print(f"\n  Classic leagues:")
    match = None
    for lg in leagues:
        mark = " "
        if target and target.lower() in lg["name"].lower():
            match, mark = lg, "→"
        print(f"   {mark} {lg['id']:>10}  {lg['name']}  (rank {lg.get('entry_rank')})")
    if match:
        cfg.set_entry("league_id", match["id"])
        print(f"\n  ✓ matched \"{match['name']}\" — saved league_id {match['id']}")
    else:
        print(f"\n  No league matched \"{target}\". Set league_id by hand in settings.yaml.")
    return 0


def cmd_squad(args) -> int:
    ctx = context.build(dry_run=True, verbose=args.verbose)
    sq = ctx.squad
    bs = ctx.bs
    fb = fixtures.FixtureBook(bs, ctx.client.fixtures())
    nxt = bs.next_event()
    gw = nxt["id"] if nxt else sq.event

    print(f"\n\033[1mSquad — GW{sq.event} ({sq.source})\033[0m")
    note = squad_engine.staleness_note(sq, gw)
    if sq.stale or sq.source != "api":
        print(f"\033[93m⚠ {note}\033[0m")
    print(f"Value £{sq.total_value:.1f}m · bank £{sq.bank:.1f}m · {sq.formation()}")
    if sq.chip:
        print(f"Active chip: {sq.chip}")
    print()
    hdr = f"  {'':2} {'Player':<15}{'Club':<5}{'Pos':<5}{'Price':>7}{'Form':>6}{'Pts':>5}  {'GW%d' % gw:<12}Status"
    print(hdr); print("  " + "─" * (len(hdr) - 2))

    def row(pick):
        p = pick.player
        fx = fb.for_team(p.raw["team"], gw)
        fxs = ", ".join(f"{f.label()} {f.difficulty}" for f in fx) or "BLANK"
        badge = "(C)" if pick.is_captain else "(V)" if pick.is_vice_captain else "  "
        flag = f"⚠️ {p.status_text}" if p.is_flagged else "ok"
        print(f"  {badge:2} {p.name:<15}{p.team_short:<5}{p.pos:<5}"
              f"{'£%.1f' % p.price:>7}{p.form:>6}{p.total_points:>5}  {fxs:<12}{flag}")

    for pick in sq.xi:
        row(pick)
    print(f"  {'':2} {'── bench ──':<15}")
    for pick in sq.bench:
        row(pick)

    clubs = {k: v for k, v in sq.by_club().items() if v >= 3}
    if clubs:
        print(f"\n  At the 3-per-club limit: {clubs}")
    print(f"\n  5GW fixture ticker (best first): "
          f"{', '.join(f'{t} {s}' for t, s in fb.ticker(gw, 5)[:8])}")
    return 0


def cmd_transfer(args) -> int:
    ctx = context.build(dry_run=True, verbose=args.verbose)
    bs, sq = ctx.bs, ctx.squad
    out_p = _resolve_player(bs, args.out)
    in_p = _resolve_player(bs, args.into)
    if out_p is None or in_p is None:
        return 1
    nxt = bs.next_event()
    v = form.check_transfer(
        out_p, in_p, bank=sq.bank, gw=nxt["id"] if nxt else None,
        no_hits_before_gw=int((ctx.cfg.plan.get("rules") or {}).get("no_hits_before_gw", 6)),
        free_transfers=args.free_transfers, squad_clubs=sq.by_club(),
        override=args.override,
    )
    print()
    print(v.render())
    print()
    return 1 if v.blocked else 0


def _resolve_player(bs: Bootstrap, token: str):
    """Accept an id or a name. Names are ambiguous — make the user choose."""
    if token.isdigit():
        p = bs.player(int(token))
        if p is None:
            print(f"No player with id {token}")
        return p
    matches = [p for p in bs.all_players() if token.lower() in p.name.lower()]
    if not matches:
        print(f"No player matching {token!r}")
        return None
    if len(matches) > 1:
        print(f"{token!r} is ambiguous — use the id:")
        for p in matches:
            print(f"   {p.id:>4}  {p.label()}  form {p.form}")
        return None
    return matches[0]


def cmd_check(args) -> int:
    ctx = context.build(dry_run=args.dry_run, verbose=args.verbose,
                        notifier=args.notifier)
    n = 0
    if args.job in ("status", "all"):
        n += status_check.run(ctx)
    if args.job in ("prices", "all"):
        n += price_check.run(ctx)
    if args.job in ("deadline", "all"):
        n += deadline_check.run(ctx, force_window=args.force_window)
    if args.job in ("league", "all"):
        n += league_check.run(ctx)
    if args.job == "live":
        n += live_check.run(ctx, force=args.force_live)
    print(f"\n{ctx.dispatcher.sent} alert(s) sent, "
          f"{ctx.dispatcher.suppressed} suppressed as duplicates.")
    return 0


def cmd_test_notify(args) -> int:
    cfg = Config.load()
    n = build_notifier(cfg, args.notifier)
    n.send(Alert(
        title="FPL Assistant is wired up",
        body="If you're reading this on your phone, notifications work.\n"
             "Highbury Reserves — GW3.",
        priority="high", tags=["soccer"],
    ))
    print(f"✓ sent via {n.name}")
    return 0


def cmd_wildcard(args) -> int:
    from .engine import wildcard as wc
    ctx = context.build(dry_run=True, verbose=args.verbose)
    bs, sq = ctx.bs, ctx.squad
    fb = fixtures.FixtureBook(bs, ctx.client.fixtures())
    gw = args.gw or (ctx.cfg.plan.get("chips", {}).get("wildcard", {}) or {}).get("planned_gw", 6)
    budget = args.budget if args.budget else round(sq.total_value + sq.bank, 1)

    keys = [args.shape] if args.shape else list(ctx.cfg.plan.get("wildcard_shapes", {}))
    for key in keys:
        cur_ev0 = bs.current_event()
        built = wc.build(ctx.cfg, bs, fb, key, budget, gw,
                         games_played=cur_ev0['id'] if cur_ev0 else 3,
                         bench_budget=args.bench_budget)
        shape = ctx.cfg.plan["wildcard_shapes"][key]
        xi, bench = built.split(fb)
        print(f"\n\033[1mShape {key} — {shape.get('label', key)}\033[0m")
        print(f"Budget £{budget:.1f}m · squad £{built.cost:.1f}m · "
              f"spare £{built.spare:.1f}m · GW{gw}")
        errs = built.legal()
        print("ILLEGAL: " + "; ".join(errs) if errs else "Legal squad ✓")
        print()
        for group, label in ((xi, "STARTING XI"), (bench, "BENCH")):
            print(f"  {label}")
            for p in group:
                fx = fb.for_team(p.raw["team"], gw)
                fxs = ", ".join(f"{f.label()} {f.difficulty}" for f in fx) or "BLANK"
                lock = "🔒" if p.id in built.locked else "  "
                print(f"   {lock} {p.name:<15}{p.team_short:<5}{p.pos:<5}"
                      f"{'£%.1f' % p.price:>7}{p.form:>6} fm  {fxs}")
        print(f"\n  Clubs: {built.clubs()}")
        cur_ev = bs.current_event()
        ready = built.bench_readiness(fb, cur_ev['id'] if cur_ev else 3)
        ok = sum(1 for r in ready if r["ok"])
        print(f"\n  Bench Boost readiness: {ok}/4 bench players are startable")
        for r in ready:
            print(f"    {'✓' if r['ok'] else '✗'} {r['name']:<15}{r['club']:<5}"
                  f"{r['minutes']:>4} min ({int(r['share']*100):>3}%)  {r['fixture']:<12}{r['verdict']}")
    return 0


def cmd_app(args) -> int:
    """Launch the desktop app (or just the server, with --server-only)."""
    import subprocess
    root = Path(__file__).resolve().parents[2]
    if args.server_only:
        from .webapp import create_app, free_port
        port = args.port or free_port()
        print(f"Gaffer server on http://127.0.0.1:{port}/  (ctrl-c to stop)")
        create_app().run(host="127.0.0.1", port=port, threaded=True)
        return 0
    return subprocess.call([str(root / ".venv/bin/python"), str(root / "desktop.py")])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fpl", description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="validate API + team_id, discover league_id")
    s.add_argument("--team-id", type=int)
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("squad", help="print the squad with fixtures and form")
    s.set_defaults(func=cmd_squad)

    s = sub.add_parser("transfer", help="run a proposed transfer past your rules")
    s.add_argument("--out", required=True, help="player id or name going out")
    s.add_argument("--in", dest="into", required=True, help="player id or name coming in")
    s.add_argument("--free-transfers", type=int, default=1)
    s.add_argument("--override", action="store_true",
                   help="proceed despite the lower-form guard")
    s.set_defaults(func=cmd_transfer)

    s = sub.add_parser("check", help="run a monitoring job")
    s.add_argument("job", choices=["status", "prices", "deadline", "league",
                                   "live", "all"])
    s.add_argument("--dry-run", action="store_true", help="print instead of notifying")
    s.add_argument("--notifier", choices=["ntfy", "console", "email"])
    s.add_argument("--force-live", action="store_true",
                   help="poll live points even with no fixture in play")
    s.add_argument("--force-window", type=int,
                   help="force a deadline reminder for this T-minus window")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("test-notify", help="send one test notification")
    s.add_argument("--notifier", choices=["ntfy", "console", "email"])
    s.set_defaults(func=cmd_test_notify)

    s = sub.add_parser("wildcard", help="build a GW6 Wildcard squad for a Shape")
    s.add_argument("--shape", choices=["A", "B", "C"], help="default: all three")
    s.add_argument("--gw", type=int)
    s.add_argument("--budget", type=float, help="override available budget")
    s.add_argument("--bench-budget", type=float, help="ring-fenced bench spend (default: plan target)")
    s.set_defaults(func=cmd_wildcard)

    s = sub.add_parser("app", help="open the Gaffer desktop app")
    s.add_argument("--server-only", action="store_true",
                   help="run the local server without the native window")
    s.add_argument("--port", type=int)
    s.set_defaults(func=cmd_app)

    s = sub.add_parser("pitch", help="build the interactive pitch view (HTML)")
    s.add_argument("-o", "--output", default=None)
    from .report import cmd_pitch
    s.set_defaults(func=cmd_pitch)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"\nConfig error: {exc}\n", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
