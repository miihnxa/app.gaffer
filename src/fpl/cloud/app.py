"""Gaffer Cloud — the public API.

Everything is free. No accounts required: sign-in exists only so the app can
remember your team id across devices, and every endpoint works signed out.

Read-only against the public FPL API. Never signs in to anyone's FPL account
and never changes a team.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, g, jsonify, make_response, request, send_from_directory

from ..webapp.service import TeamNotFound
from . import auth, cache, limits, store

log = logging.getLogger(__name__)
WEB = Path(__file__).parent / "web"

# Kept as an abuse ceiling, not a paywall — a normal session is a handful of
# lookups. Anonymous callers are limited by IP in limits.py instead.
DAILY_LOOKUP_CEILING = 400


def base_url() -> str:
    return os.environ.get("GAFFER_BASE_URL", request.host_url.rstrip("/"))


def stateless() -> bool:
    """Serverless hosts give you an ephemeral filesystem, so SQLite accounts
    would silently vanish between requests. Everything here is free and an
    account only ever remembered a team id — the browser does that better.
    In stateless mode there is no database and no sign-in at all."""
    return os.environ.get("GAFFER_STATELESS", "").lower() in ("1", "true", "yes")


def create_app() -> Flask:
    flat = stateless()
    if not flat:
        store.init()
    app = Flask(__name__, static_folder=None)
    app.config["GAFFER_STATELESS"] = flat
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    # --- CORS, so a Lovable/Base44 frontend on another origin can call this ---
    allowed = [o.strip() for o in
               os.environ.get("GAFFER_CORS_ORIGINS", "").split(",") if o.strip()]

    @app.after_request
    def edge_cache(resp):
        # Every response is the same for every caller, so a CDN can absorb the
        # traffic. 300s matches the FPL API's own max-age.
        if request.path.startswith("/api/") and resp.status_code == 200 \
                and request.path not in ("/api/me", "/api/config"):
            resp.headers.setdefault(
                "Cache-Control", "public, max-age=60, s-maxage=300, "
                                 "stale-while-revalidate=600")
        return resp

    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin", "")
        if origin and origin in allowed:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @app.before_request
    def gate():
        if request.method == "OPTIONS":
            return make_response("", 204)
        if request.path.startswith("/api/"):
            user = None if flat else auth.current_user()
            ok, retry = limits.check(user)
            if not ok:
                return limits.too_many(retry)

    @app.errorhandler(TeamNotFound)
    def _nf(exc):
        return jsonify({"error": str(exc), "code": "team_not_found"}), 404

    @app.errorhandler(500)
    def _boom(exc):
        log.exception("unhandled")
        return jsonify({"error": "Something broke on our side.",
                        "code": "server_error"}), 500

    # ================= accounts =================
    if flat:
        @app.get("/api/me")
        def me_flat():
            return jsonify({"signed_in": False, "stateless": True})

        @app.get("/api/config")
        def config_flat():
            # No server-side memory: the client keeps the last team in
            # localStorage and passes it back itself.
            return jsonify({"default_team_id": None, "default_league_id": None,
                            "timezone": "Europe/London", "recents": [],
                            "stateless": True})
    else:
        @app.post("/api/auth/request")
        def auth_request():
            email = (request.json or {}).get("email", "").strip().lower()
            if "@" not in email or len(email) > 200:
                return jsonify({"error": "Enter a valid email address."}), 400
            store.get_or_create_user(email)
            token = store.new_login_token(email)
            auth.send_magic_link(email, f"{base_url()}/api/auth/callback?token={token}")
            return jsonify({"ok": True,
                            "message": "Check your email for a sign-in link."})

        @app.get("/api/auth/callback")
        def auth_callback():
            email = store.consume_login_token(request.args.get("token", ""))
            if not email:
                return jsonify({"error": "That link has expired or was already used.",
                                "code": "bad_token"}), 400
            user = store.get_or_create_user(email)
            resp = make_response(jsonify({"ok": True}))
            resp.headers["Location"] = f"{base_url()}/app"
            resp.status_code = 302
            resp.set_cookie("gaffer_session", auth.issue(user),
                            max_age=auth.SESSION_DAYS * 86400, httponly=True,
                            samesite="Lax", secure=base_url().startswith("https"))
            return resp

        @app.post("/api/auth/logout")
        def logout():
            resp = make_response(jsonify({"ok": True}))
            resp.delete_cookie("gaffer_session")
            return resp

        @app.get("/api/me")
        @auth.optional_user
        def me():
            u = g.user
            if u is None:
                return jsonify({"signed_in": False})
            return jsonify({"signed_in": True, "email": u.email,
                            "team_id": u.team_id})

        @app.get("/api/config")
        @auth.optional_user
        def client_config():
            u = g.user
            return jsonify({"default_team_id": u.team_id if u else None,
                            "default_league_id": None,
                            "timezone": "Europe/London", "recents": []})

    # ================= free =================
    @app.get("/api/config")
    @auth.optional_user
    def client_config():
        u = g.user
        return jsonify({"default_team_id": u.team_id if u else None,
                        "default_league_id": None,
                        "timezone": "Europe/London", "recents": []})

    @app.get("/api/season")
    def season():
        return jsonify(cache.service().season())

    @app.get("/api/team/<int:team_id>")
    @auth.optional_user
    def team(team_id: int):
        user = None if flat else g.user
        if user is not None:
            calls = store.bump_usage(user.id)
            if calls > DAILY_LOOKUP_CEILING:
                return jsonify({
                    "error": "That's a lot of lookups in one day. Try again "
                             "tomorrow, or get in touch if you need more.",
                    "code": "rate_limited"}), 429
            store.set_team(user.id, team_id)
        payload = cache.service().team_payload(team_id, with_replacements=True)
        return jsonify(payload)

    @app.get("/api/league/<int:league_id>")
    def league(league_id: int):
        return jsonify(cache.service().league(
            league_id, request.args.get("team", type=int)))

    @app.get("/api/player/<int:player_id>")
    def player(player_id: int):
        return jsonify(cache.service().player(player_id))

    @app.get("/api/search")
    def search():
        return jsonify(cache.service().search(request.args.get("q", "")))

    @app.get("/api/ticker")
    def ticker():
        return jsonify(cache.service().ticker(request.args.get("n", 5, type=int)))

    # ================= pro =================
    @app.get("/api/team/<int:team_id>/rebuild")
    def rebuild(team_id: int):
        locked = [int(x) for x in request.args.getlist("lock") if x.isdigit()]
        return jsonify(cache.service().rebuild(
            team_id, locked_ids=locked,
            bench_budget=float(request.args.get("bench", 19.0)),
            budget=request.args.get("budget", type=float)))

    # ================= pages =================
    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True})

    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/app")
    def application():
        return send_from_directory(WEB, "app.html")

    @app.get("/<path:name>")
    def page(name: str):
        target = WEB / name
        if target.is_file():
            return send_from_directory(WEB, name)
        html = WEB / f"{name}.html"
        if html.is_file():
            return send_from_directory(WEB, f"{name}.html")
        return jsonify({"error": "Not found"}), 404

    return app


app = create_app() if os.environ.get("GAFFER_EAGER") else None
