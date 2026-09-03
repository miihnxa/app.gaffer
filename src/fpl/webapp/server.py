"""Local HTTP server for the desktop app.

Binds to 127.0.0.1 only — nothing here is exposed to the network. All data is
read-only public FPL data; the app never signs in and never makes a change to
anyone's team.
"""
from __future__ import annotations

import logging
import socket
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from ..config import DATA_DIR
from . import account, prefs
from .service import Service, TeamNotFound

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
def free_port(preferred: int = 8730) -> int:
    for port in range(preferred, preferred + 40):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def create_app(service: Service | None = None) -> Flask:
    svc = service or Service()
    app = Flask(__name__, static_folder=None)

    @app.errorhandler(TeamNotFound)
    def _not_found(exc):
        return jsonify({"error": str(exc)}), 404

    @app.errorhandler(Exception)
    def _boom(exc):
        log.exception("request failed")
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

    # --- static ---------------------------------------------------
    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/<path:name>")
    def asset(name):
        return send_from_directory(STATIC, name)

    # --- api ------------------------------------------------------
    @app.get("/api/season")
    def season():
        return jsonify(svc.season())

    # --- account (proxied to the hosted service; token never reaches the page) ---
    @app.post("/api/account/request")
    def acct_request():
        status, body = account.request_code((request.json or {}).get("email", ""))
        return jsonify(body), status

    @app.post("/api/account/verify")
    def acct_verify():
        b = request.json or {}
        status, body = account.verify_code(b.get("email", ""), b.get("code", ""))
        return jsonify(body), status

    @app.get("/api/account/me")
    def acct_me():
        status, body = account.me()
        return jsonify(body), status

    @app.post("/api/account/team")
    def acct_team():
        status, body = account.save_team((request.json or {}).get("team_id"))
        return jsonify(body), status

    @app.post("/api/account/logout")
    def acct_logout():
        status, body = account.logout()
        return jsonify(body), status

    @app.post("/api/account/delete")
    def acct_delete():
        status, body = account.delete_account()
        return jsonify(body), status

    # --- preferences, persisted on disk (not in the window's storage) ---
    @app.get("/api/prefs")
    def get_prefs():
        return jsonify(prefs.all())

    @app.post("/api/prefs")
    def set_prefs():
        return jsonify(prefs.update(request.json or {}))

    @app.get("/api/swaps")
    def get_swaps():
        return jsonify(prefs.get_swaps(request.args.get("team", type=int) or 0,
                                       request.args.get("gw", type=int) or 0))

    @app.post("/api/swaps")
    def post_swap():
        b = request.json or {}
        return jsonify(prefs.set_swap(int(b["team"]), int(b["gw"]),
                                      int(b["out"]), int(b["in"])))

    @app.post("/api/swaps/clear")
    def clear_swap():
        b = request.json or {}
        out = b.get("out")
        return jsonify(prefs.clear_swap(int(b["team"]), int(b["gw"]),
                                        int(out) if out is not None else None))

    @app.get("/api/config")
    def config():
        # Deliberately no team id. The app must not open on whoever's id
        # happens to be in settings.yaml — each person enters their own, and
        # the client remembers it locally.
        return jsonify({"timezone": svc.cfg.tz.key,
                        "accounts": account.enabled()})

    @app.get("/api/team/<int:team_id>")
    def team(team_id: int):
        # swap=<out_id>:<in_id>, repeatable — transfers made since the last
        # published gameweek, which the public API cannot see.
        swaps: dict[int, int] = {}
        for raw in request.args.getlist("swap"):
            out, _, inc = raw.partition(":")
            if out.isdigit() and inc.isdigit():
                swaps[int(out)] = int(inc)
        return jsonify(svc.team_payload(team_id, swaps=swaps))

    @app.get("/api/team/<int:team_id>/rebuild")
    def rebuild(team_id: int):
        locked = [int(x) for x in request.args.getlist("lock") if x.isdigit()]
        bench = float(request.args.get("bench", 19.0))
        budget = request.args.get("budget", type=float)
        return jsonify(svc.rebuild(team_id, locked_ids=locked,
                                   bench_budget=bench, budget=budget))

    @app.get("/api/league/<int:league_id>")
    def league(league_id: int):
        return jsonify(svc.league(league_id, request.args.get("team", type=int)))

    @app.get("/api/ticker")
    def ticker():
        return jsonify(svc.ticker(request.args.get("n", 5, type=int)))

    @app.get("/api/player/<int:player_id>")
    def player(player_id: int):
        return jsonify(svc.player(player_id))

    @app.get("/api/search")
    def search():
        return jsonify(svc.search(request.args.get("q", "")))

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    return app
