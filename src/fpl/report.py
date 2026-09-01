"""Builds the interactive pitch view — the squad laid out like the official
FPL site, with budget, fixtures and recommended changes on the same page.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .api.client import FPLClient
from .api.model import Bootstrap, Player
from .config import Config, ROOT
from .engine import advice as advice_engine
from .engine import budget as budget_engine
from .engine import deadlines, fixtures as fx_engine
from .engine import league as league_engine
from .engine import replacements as rep_engine
from .engine import squad as squad_engine
from .engine import wildcard as wc_engine

TEMPLATE = Path(__file__).parent / "templates" / "pitch.html"
DEFAULT_OUT = ROOT / "data" / "pitch.html"


def _fx(f) -> dict:
    return {"gw": f.gw, "opponent": f.opponent, "home": f.home,
            "difficulty": f.difficulty}


def _player_payload(pick, fb: fx_engine.FixtureBook, gw: int,
                    reps: list | None = None) -> dict:
    p: Player = pick.player
    tid = p.raw["team"]
    if p.is_flagged:
        status = p.status_text
        severity = "critical" if p.effective_chance <= 25 else "warning"
    else:
        status, severity = "ok", "ok"
    return {
        "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
        "price": p.price, "form": p.form, "points": p.total_points,
        "selected": p.selected_by, "price_pct": round(p.price_rise_percent),
        "status": status, "severity": severity, "news": p.news,
        "chance": p.effective_chance,
        "position": pick.position, "benched": pick.on_bench,
        "is_captain": pick.is_captain, "is_vice": pick.is_vice_captain,
        "fixtures_gw": [_fx(f) for f in fb.for_team(tid, gw)],
        "fixtures_next": [_fx(f) for f in fb.next_n(tid, gw, 5)],
        "fdr5": fb.difficulty_score(tid, gw, 5),
        "replacements": reps or [],
    }


def _wc_player(p, fb: fx_engine.FixtureBook, gw: int, built) -> dict:
    tid = p.raw["team"]
    return {
        "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
        "price": p.price, "form": p.form, "points": p.total_points,
        "selected": p.selected_by, "price_pct": round(p.price_rise_percent),
        "status": "ok", "severity": "ok", "news": "", "chance": 100,
        "position": 0, "benched": False, "is_captain": False, "is_vice": False,
        "locked": p.id in built.locked,
        "fixtures_gw": [_fx(f) for f in fb.for_team(tid, gw)],
        "fixtures_next": [_fx(f) for f in fb.next_n(tid, gw, 5)],
        "fdr5": fb.difficulty_score(tid, gw, 5),
        "replacements": [],
    }


def build_payload(cfg: Config, client: FPLClient, bs: Bootstrap) -> dict:
    sq = squad_engine.resolve(cfg, client, bs)
    fb = fx_engine.FixtureBook(bs, client.fixtures())
    nxt = bs.next_event()
    gw = nxt["id"] if nxt else sq.event
    dl = deadlines.next_deadline(bs)

    advice = advice_engine.build(cfg, bs, sq, fb, gw)

    # Transfer planner: for every player you own, the replacements that pass
    # your own rules. Computed here so the page stays a static file.
    owned_ids = {p.id for p in sq.players}
    clubs = sq.by_club()
    no_hits = int((cfg.plan.get("rules") or {}).get("no_hits_before_gw", 6))
    reps = {
        pick.player.id: rep_engine.suggest(
            bs, fb, pick.player, owned_ids=owned_ids, bank=sq.bank, gw=gw,
            clubs=clubs, no_hits_before_gw=no_hits)
        for pick in sq.picks
    }

    # The GW6 Wildcard squads, one per Shape, so you can flip between them.
    cur_ev = bs.current_event()
    games = cur_ev["id"] if cur_ev else 3
    wc_gw = (cfg.plan.get("chips", {}).get("wildcard", {}) or {}).get("planned_gw", 6)
    wildcards = {}
    for key in cfg.plan.get("wildcard_shapes", {}):
        try:
            built = wc_engine.build(cfg, bs, fb, key, round(sq.total_value + sq.bank, 1),
                                    wc_gw, games_played=games)
        except (RuntimeError, KeyError):
            continue
        b_xi, b_bench = built.split(fb)
        ready = built.bench_readiness(fb, games)
        wildcards[key] = {
            "label": cfg.plan["wildcard_shapes"][key].get("label", key),
            "note": cfg.plan["wildcard_shapes"][key].get("note", ""),
            "cost": built.cost, "spare": built.spare, "gw": wc_gw,
            "xi": [_wc_player(p, fb, wc_gw, built) for p in b_xi],
            "bench": [_wc_player(p, fb, wc_gw, built) for p in b_bench],
            "bench_ready": sum(1 for r in ready if r["ok"]),
            "bench_detail": ready,
            "kept": [p.name for p in built.players if p.id in owned_ids],
        }
    shapes = budget_engine.evaluate(cfg, bs, sq)

    available = round(sq.total_value + sq.bank, 1)
    bench_current = round(sum(p.player.price for p in sq.bench), 1)
    isak, gonzalo = bs.player(379), bs.player(569)
    isak_gap = round(isak.price - gonzalo.price, 1) if isak and gonzalo else 3.0

    # Mini-league table, when a league is configured.
    table, me_row = [], None
    if cfg.league_id and cfg.team_id:
        try:
            lname, rivals = league_engine.standings(client, int(cfg.league_id))
            me_row = league_engine.find_me(rivals, int(cfg.team_id))
            table = [{
                "rank": r.rank, "name": r.name, "manager": r.manager,
                "total": r.total, "gw": r.gw_points, "moved": r.moved,
                "me": bool(me_row and r.entry == me_row.entry),
                "gap": (me_row.total - r.total) if me_row else 0,
            } for r in rivals]
        except Exception:  # noqa: BLE001 — the page is still useful without it
            table = []

    expiry = bs.chip_stop_event("wildcard") or cfg.plan.get("chip_deadline_gw", 19)
    chip_names = {"wildcard": "Wildcard", "3xc": "Triple Captain",
                  "bboost": "Bench Boost", "freehit": "Free Hit"}

    stats = [
        {"k": "Squad value", "v": f"£{sq.total_value:.1f}m"},
        {"k": "Bank", "v": f"£{sq.bank:.1f}m"},
        {"k": "Formation", "v": sq.formation()},
        {"k": "Flagged", "v": str(sum(1 for p in sq.players if p.is_flagged))},
        {"k": "To act on", "v": str(len(advice))},
    ]

    return {
        "generated": datetime.now(cfg.tz).strftime("%d %b %Y, %H:%M %Z"),
        "team": {
            "name": cfg.settings.get("entry", {}).get("team_name", "Highbury Reserves"),
            "league": cfg.settings.get("entry", {}).get("league_name", ""),
            "stats": stats,
        },
        "gw": {
            "next": gw,
            "deadline_local": dl.local(cfg.tz).strftime("%a %d %b, %H:%M") if dl else "—",
            "countdown": dl.countdown() if dl else "—",
        },
        "squad": {
            "source": {"api": "live FPL API",
                       "pending-recorded": "recorded by hand for the upcoming deadline",
                       "plan-fallback": "season plan (team_id not set)"}.get(sq.source, sq.source),
            "source_note": squad_engine.staleness_note(sq, gw),
            "formation": sq.formation(),
            "value": sq.total_value, "bank": sq.bank,
            "xi": [_player_payload(p, fb, gw, reps.get(p.player.id)) for p in sq.xi],
            "bench": [_player_payload(p, fb, gw, reps.get(p.player.id)) for p in sq.bench],
        },
        "advice": [a.dict() for a in advice],
        "budget": {
            "wildcard_gw": (cfg.plan.get("chips", {}).get("wildcard", {}) or {}).get("planned_gw", 6),
            "value": sq.total_value, "bank": sq.bank, "available": available,
            "bench_current": bench_current,
            "bench_target": float((cfg.plan.get("wildcard_brief") or {}).get("bench_budget_target", 19.0)),
            "isak_gap": isak_gap,
            "shapes": [{
                "key": s.key, "label": s.label, "note": s.note,
                "forwards": " + ".join(f"{p.name} £{p.price:.1f}m" for p in s.forwards)
                            + f" + £{s.third_forward_budget:.1f}m",
                "spend": s.forward_spend,
                "spend_pct": round(100 * s.forward_spend / max(available, 1), 1),
                "outfield": s.outfield_budget(),
                "per_player": round(s.outfield_budget() / 8, 1),
                "affordable": s.affordable,
                "blocked": s.blocked_reason,
            } for s in shapes],
        },
        "wildcards": wildcards,
        "league": {
            "name": cfg.settings.get("entry", {}).get("league_name", ""),
            "rows": table,
            "my_rank": me_row.rank if me_row else None,
            "leader_gap": (table[0]["total"] - me_row.total) if (table and me_row) else 0,
        },
        "chips": {
            "expiry": expiry,
            "gws_left": max(0, expiry - gw),
            "items": [{
                "name": chip_names.get(k, k),
                "gw": c.get("planned_gw"),
                "note": c.get("note", "")[:60],
                "used": False,
            } for k, c in (cfg.plan.get("chips") or {}).items()],
        },
    }


def render(payload: dict) -> str:
    html = TEMPLATE.read_text()
    return html.replace("/*__DATA__*/{}", json.dumps(payload, ensure_ascii=False))


def cmd_pitch(args) -> int:
    cfg = Config.load()
    client = FPLClient(cfg)
    bs = Bootstrap(client.bootstrap())
    payload = build_payload(cfg, client, bs)
    out = Path(args.output) if args.output else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(payload), encoding="utf-8")
    print(f"✓ pitch view written to {out}")
    print(f"  GW{payload['gw']['next']} · {len(payload['advice'])} recommendation(s) · "
          f"source: {payload['squad']['source']}")
    return 0
