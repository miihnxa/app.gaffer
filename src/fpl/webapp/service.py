"""Analysis for ANY FPL manager, by team id.

The CLI is built around one configured team and a personal season plan. This
layer takes a team id at request time and uses only public data, so the app
works for any manager in the game.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..api.client import FPLClient, FPLError
from ..api.model import Bootstrap, Player
from ..config import Config
from ..engine import advice as advice_engine
from ..engine import deadlines, league as league_engine
from ..engine import fixtures as fx_engine
from ..engine import subs as subs_engine
from ..engine import replacements as rep_engine
from ..engine import wildcard as wc_engine
from ..engine.squad import Pick, Squad, _pending, staleness_note


class TeamNotFound(Exception):
    pass


class Service:
    """Holds the shared client so bootstrap/fixtures are fetched once."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config.load()
        self.client = FPLClient(self.cfg)
        self._bs: Bootstrap | None = None
        self._fb: fx_engine.FixtureBook | None = None
        self._fetched: datetime | None = None

    # --- shared data ------------------------------------------------
    def _refresh(self) -> None:
        stale = (self._fetched is None
                 or (datetime.now(timezone.utc) - self._fetched).total_seconds() > 900)
        if stale or self._bs is None:
            self._bs = Bootstrap(self.client.bootstrap())
            self._fb = fx_engine.FixtureBook(self._bs, self.client.fixtures())
            self._fetched = datetime.now(timezone.utc)

    @property
    def bs(self) -> Bootstrap:
        self._refresh()
        return self._bs

    @property
    def fb(self) -> fx_engine.FixtureBook:
        self._refresh()
        return self._fb

    @property
    def next_gw(self) -> int:
        nxt = self.bs.next_event()
        cur = self.bs.current_event()
        return (nxt or cur or {"id": 1})["id"]

    @property
    def games_played(self) -> int:
        cur = self.bs.current_event()
        return cur["id"] if cur else 1

    # --- payloads ---------------------------------------------------
    def season(self) -> dict:
        dl = deadlines.next_deadline(self.bs)
        tz = self.cfg.tz
        return {
            "next_gw": self.next_gw,
            "current_gw": self.games_played,
            "deadline_utc": dl.deadline_utc.isoformat() if dl else None,
            "deadline_local": dl.local(tz).strftime("%a %d %b, %H:%M") if dl else "—",
            "timezone": tz.key,
            "countdown": dl.countdown() if dl else "—",
            "chip_expiry": self.bs.chip_stop_event("wildcard"),
            "total_players": self.bs.data.get("total_players"),
        }

    def entry(self, team_id: int) -> dict:
        try:
            return self.client.entry(int(team_id))
        except FPLError as exc:
            raise TeamNotFound(
                f"No FPL team with id {team_id}. The id is the number in the URL "
                f"of your Points or Gameweek History page."
            ) from exc

    def is_owner(self, team_id: int) -> bool:
        """True for the team this install is configured for — only that team
        gets the personal season plan applied to it."""
        return bool(self.cfg.team_id) and int(team_id) == int(self.cfg.team_id)

    def _plan_cfg(self, team_id: int) -> Config:
        """Other managers get the generic rules, not your captaincy plan or
        chip schedule — those would be meaningless advice for their team."""
        if self.is_owner(team_id):
            return self.cfg
        generic = Config(settings=self.cfg.settings, watchlist={},
                         plan={"rules": self.cfg.plan.get("rules", {})})
        return generic

    def squad(self, team_id: int) -> Squad:
        entry = self.entry(team_id)
        gw = self.games_played
        data = self.client.picks(int(team_id), gw)
        eh = data.get("entry_history", {})
        picks = [
            Pick(player=self.bs.player(p["element"]), position=p["position"],
                 is_captain=p["is_captain"], is_vice_captain=p["is_vice_captain"],
                 multiplier=p["multiplier"])
            for p in data["picks"]
        ]
        sq = Squad(
            picks=picks, event=gw,
            bank=eh.get("bank", 0) / 10.0, value=eh.get("value", 0) / 10.0,
            source="api", chip=data.get("active_chip"),
            stale=self.next_gw != gw,
        )
        # Picks for the upcoming gameweek are not public. For your own team we
        # have a hand-recorded pending squad; for anyone else's, we can't.
        if sq.stale and self.is_owner(team_id):
            pending = _pending(self.cfg, self.bs, self.next_gw, live_bank=sq.bank)
            if pending is not None:
                return pending
        return sq

    def team_payload(self, team_id: int, *, with_replacements: bool = True,
                     swaps: dict[int, int] | None = None) -> dict:
        entry = self.entry(team_id)
        sq = self.squad(team_id)
        applied = self._apply_swaps(sq, swaps or {})
        gw = self.next_gw
        fb, bs = self.fb, self.bs

        adv = advice_engine.build(self._plan_cfg(team_id), bs, sq, fb, gw)
        owned_ids = {p.id for p in sq.players}
        clubs = sq.by_club()

        reps: dict[int, list] = {}
        if with_replacements:
            reps = {
                pick.player.id: rep_engine.suggest(
                    bs, fb, pick.player, owned_ids=owned_ids, bank=sq.bank,
                    gw=gw, clubs=clubs, no_hits_before_gw=0)
                for pick in sq.picks
            }

        leagues = [
            {"id": l["id"], "name": l["name"], "rank": l.get("entry_rank"),
             "last_rank": l.get("entry_last_rank"), "size": l.get("rank_count")}
            for l in entry.get("leagues", {}).get("classic", [])
        ]

        return {
            "entry": {
                "id": entry["id"], "name": entry["name"],
                "manager": f"{entry['player_first_name']} {entry['player_last_name']}",
                "region": entry.get("player_region_name"),
                "overall_points": entry["summary_overall_points"],
                "overall_rank": entry.get("summary_overall_rank"),
                "gw_points": entry.get("summary_event_points"),
                "value": entry["last_deadline_value"] / 10.0,
                "bank": entry["last_deadline_bank"] / 10.0,
                "transfers": entry.get("last_deadline_total_transfers", 0),
                "started_event": entry.get("started_event"),
            },
            "squad": {
                "gw": sq.event, "formation": sq.formation(),
                "value": sq.total_value, "bank": sq.bank,
                "stale": sq.stale, "chip": sq.chip,
                "note": staleness_note(sq, gw, bool(applied)),
                "source": sq.source,
                "is_owner": self.is_owner(team_id),
                "swaps": applied,
                "clubs": clubs,
                "xi": [self._player(p, gw, reps.get(p.player.id)) for p in sq.xi],
                "bench": [self._player(p, gw, reps.get(p.player.id)) for p in sq.bench],
            },
            "advice": [a.dict() for a in adv],
            "subs": [x.dict() for x in subs_engine.suggest(sq, fb, gw)],
            "bench_order": subs_engine.bench_order(sq, fb, gw),
            "leagues": leagues,
        }

    def _apply_swaps(self, sq: Squad, swaps: dict[int, int]) -> list[dict]:
        """Amend the squad with transfers the public API cannot see yet.

        Applied before anything is derived, so advice, legality checks, clash
        detection and replacement suggestions all reason about the squad the
        manager actually has — not the one FPL last published.
        """
        applied: list[dict] = []
        by_id = {p.player.id: p for p in sq.picks}
        for out_id, in_id in swaps.items():
            pick = by_id.get(int(out_id))
            incoming = self.bs.player(int(in_id))
            if pick is None or incoming is None:
                continue
            if incoming.id in by_id:
                continue                      # already in the squad
            if incoming.pos != pick.player.pos:
                continue                      # FPL only allows like-for-like
            applied.append({"out": pick.player.name, "out_id": pick.player.id,
                            "in": incoming.name, "in_id": incoming.id,
                            "pos": incoming.pos})
            pick.player = incoming
            by_id[incoming.id] = pick
        return applied

    def _player(self, pick: Pick, gw: int, reps: list | None) -> dict:
        p: Player = pick.player
        tid = p.raw["team"]
        flagged = p.is_flagged
        return {
            "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
            "price": p.price, "form": p.form, "points": p.total_points,
            "selected": p.selected_by, "price_pct": round(p.price_rise_percent),
            "minutes": int(p.raw.get("minutes") or 0),
            "ppg": float(p.raw.get("points_per_game") or 0),
            "status": p.status_text if flagged else "ok",
            "severity": ("critical" if flagged and p.effective_chance <= 25
                         else "warning" if flagged else "ok"),
            "news": p.news, "chance": p.effective_chance,
            "position": pick.position, "benched": pick.on_bench,
            "is_captain": pick.is_captain, "is_vice": pick.is_vice_captain,
            "fixtures_gw": [self._fx(f) for f in self.fb.for_team(tid, gw)],
            "fixtures_next": [self._fx(f) for f in self.fb.next_n(tid, gw, 5)],
            "fdr5": self.fb.difficulty_score(tid, gw, 5),
            "replacements": reps or [],
        }

    @staticmethod
    def _fx(f) -> dict:
        return {"gw": f.gw, "opponent": f.opponent, "home": f.home,
                "difficulty": f.difficulty}

    # --- extras -----------------------------------------------------
    def rebuild(self, team_id: int, *, locked_ids: list[int] | None = None,
                bench_budget: float = 19.0, budget: float | None = None) -> dict:
        sq = self.squad(team_id)
        gw = self.next_gw
        total = budget if budget is not None else round(sq.total_value + sq.bank, 1)
        built = wc_engine.build_squad(
            self.bs, self.fb, total, gw, locked_ids=locked_ids or [],
            bench_budget=bench_budget, games_played=self.games_played)
        xi, bench = built.split(self.fb)
        ready = built.bench_readiness(self.fb, self.games_played)
        owned = {p.id for p in sq.players}
        return {
            "gw": gw, "budget": total, "cost": built.cost, "spare": built.spare,
            "formation": f"{sum(1 for p in xi if p.pos=='DEF')}-"
                         f"{sum(1 for p in xi if p.pos=='MID')}-"
                         f"{sum(1 for p in xi if p.pos=='FWD')}",
            "bench_ready": sum(1 for r in ready if r["ok"]),
            "bench_detail": ready,
            "xi": [self._wc(p, gw, built, owned) for p in xi],
            "bench": [self._wc(p, gw, built, owned) for p in bench],
            "kept": sorted(p.name for p in built.players if p.id in owned),
            "out": sorted(p.name for p in sq.players
                          if p.id not in {b.id for b in built.players}),
        }

    def _wc(self, p: Player, gw: int, built, owned: set[int]) -> dict:
        tid = p.raw["team"]
        return {
            "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
            "price": p.price, "form": p.form, "points": p.total_points,
            "selected": p.selected_by, "price_pct": round(p.price_rise_percent),
            "minutes": int(p.raw.get("minutes") or 0),
            "ppg": float(p.raw.get("points_per_game") or 0),
            "status": "ok", "severity": "ok", "news": "", "chance": 100,
            "position": 0, "benched": False,
            "is_captain": False, "is_vice": False,
            "locked": p.id in built.locked, "owned": p.id in owned,
            "fixtures_gw": [self._fx(f) for f in self.fb.for_team(tid, gw)],
            "fixtures_next": [self._fx(f) for f in self.fb.next_n(tid, gw, 5)],
            "fdr5": self.fb.difficulty_score(tid, gw, 5),
            "replacements": [],
        }

    def league(self, league_id: int, team_id: int | None = None) -> dict:
        name, rivals = league_engine.standings(self.client, int(league_id))
        me = league_engine.find_me(rivals, team_id) if team_id else None
        return {
            "id": league_id, "name": name,
            "me": me.entry if me else None,
            "rows": [{"entry": r.entry, "name": r.name, "manager": r.manager,
                      "rank": r.rank, "last_rank": r.last_rank, "total": r.total,
                      "gw": r.gw_points, "moved": r.moved,
                      "is_me": bool(me and r.entry == me.entry)}
                     for r in rivals],
        }

    def ticker(self, n: int = 5) -> list[dict]:
        gw = self.next_gw
        return [{"club": c, "fdr": s,
                 "fixtures": [self._fx(f) for f in self.fb.next_n(
                     next(t for t, v in self.bs.teams.items()
                          if v["short_name"] == c), gw, n)]}
                for c, s in self.fb.ticker(gw, n)]

    def player(self, player_id: int) -> dict:
        """Per-gameweek history for the drawer's form bars."""
        data = self.client.element_summary(int(player_id))
        p = self.bs.player(int(player_id))
        return {
            "id": int(player_id),
            "name": p.name if p else str(player_id),
            "history": [
                {"event": h.get("round"), "points": h.get("total_points", 0),
                 "minutes": h.get("minutes", 0), "opponent": h.get("opponent_team")}
                for h in data.get("history", [])
            ],
        }

    def search(self, q: str, limit: int = 20) -> list[dict]:
        q = (q or "").strip().lower()
        if len(q) < 2:
            return []
        gw = self.next_gw
        hits = [p for p in self.bs.all_players() if q in p.name.lower()]
        hits.sort(key=lambda p: -p.total_points)
        return [{
            "id": p.id, "name": p.name, "club": p.team_short, "pos": p.pos,
            "price": p.price, "form": p.form, "points": p.total_points,
            "selected": p.selected_by, "status": p.status_text,
            "flagged": p.is_flagged,
            "fdr5": self.fb.difficulty_score(p.raw["team"], gw, 5),
        } for p in hits[:limit]]
