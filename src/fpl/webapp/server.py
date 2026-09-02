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

    @app.get("/api/config")
    def config():
        # Deliberately no team id. The app must not open on whoever's id
        # happens to be in settings.yaml — each person enters their own, and
        # the client remembers it locally.
        return jsonify({"timezone": svc.cfg.tz.key})

    @app.get("/api/team/<int:team_id>")
    def team(team_id: int):
        return jsonify(svc.team_payload(team_id))

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
