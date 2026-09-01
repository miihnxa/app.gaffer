"""Gaffer Cloud — the public API.

Free tier   : squad, fixtures, flags, basic checks, league standings
Pro tier    : squad rebuilder, transfer suggestions, rival diffing, alerts

Read-only against the public FPL API. Never signs in to anyone's FPL account
and never changes a team.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, g, jsonify, make_response, request, send_from_directory

from ..webapp.service import TeamNotFound
from . import auth, billing, cache, limits, store

log = logging.getLogger(__name__)
WEB = Path(__file__).parent / "web"

FREE_TEAM_LOOKUPS_PER_DAY = 25


def base_url() -> str:
    return os.environ.get("GAFFER_BASE_URL", request.host_url.rstrip("/"))


def create_app() -> Flask:
    store.init()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    # --- CORS, so a Lovable/Base44 frontend on another origin can call this ---
    allowed = [o.strip() for o in
               os.environ.get("GAFFER_CORS_ORIGINS", "").split(",") if o.strip()]

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
            user = auth.current_user()
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

    # ================= auth =================
    @app.post("/api/auth/request")
    def auth_request():
        email = (request.json or {}).get("email", "").strip().lower()
        if "@" not in email or len(email) > 200:
            return jsonify({"error": "Enter a valid email address."}), 400
        store.get_or_create_user(email)
        token = store.new_login_token(email)
        auth.send_magic_link(email, f"{base_url()}/api/auth/callback?token={token}")
        # Always the same reply, so this can't be used to test who has an account.
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
            return jsonify({"signed_in": False, "plan": "anon"})
        return jsonify({"signed_in": True, "email": u.email, "plan": u.plan,
                        "pro": u.is_pro, "status": u.status,
                        "team_id": u.team_id,
                        "billing": billing.configured()})

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
        user = g.user
        if user is not None:
            calls = store.bump_usage(user.id)
            if not user.is_pro and calls > FREE_TEAM_LOOKUPS_PER_DAY:
                return jsonify({
                    "error": f"Free accounts get {FREE_TEAM_LOOKUPS_PER_DAY} team "
                             f"lookups a day. Pro is unlimited.",
                    "code": "upgrade_required"}), 402
            store.set_team(user.id, team_id)
        svc = cache.service()
        # Replacement suggestions are the paid feature — don't compute them for
        # free accounts, it's the expensive part of the request too.
        payload = svc.team_payload(team_id,
                                   with_replacements=bool(user and user.is_pro))
        payload["pro"] = bool(user and user.is_pro)
        return jsonify(payload)

    @app.get("/api/league/<int:league_id>")
    @auth.optional_user
    def league(league_id: int):
        return jsonify(cache.service().league(
            league_id, request.args.get("team", type=int)))

    @app.get("/api/search")
    def search():
        return jsonify(cache.service().search(request.args.get("q", "")))

    @app.get("/api/ticker")
    def ticker():
        return jsonify(cache.service().ticker(request.args.get("n", 5, type=int)))

    # ================= pro =================
    @app.get("/api/team/<int:team_id>/rebuild")
    @auth.pro_required
    def rebuild(team_id: int):
        locked = [int(x) for x in request.args.getlist("lock") if x.isdigit()]
        return jsonify(cache.service().rebuild(
            team_id, locked_ids=locked,
            bench_budget=float(request.args.get("bench", 19.0)),
            budget=request.args.get("budget", type=float)))

    # ================= billing =================
    @app.post("/api/billing/checkout")
    @auth.login_required
    def checkout():
        if not billing.configured():
            return jsonify({"error": "Billing isn't switched on yet."}), 503
        cadence = (request.json or {}).get("cadence", "monthly")
        return jsonify({"url": billing.checkout_url(g.user, cadence, base_url())})

    @app.post("/api/billing/portal")
    @auth.login_required
    def portal():
        if not billing.configured():
            return jsonify({"error": "Billing isn't switched on yet."}), 503
        return jsonify({"url": billing.portal_url(g.user, base_url())})

    @app.post("/api/billing/webhook")
    def webhook():
        try:
            kind = billing.handle_webhook(
                request.get_data(), request.headers.get("Stripe-Signature", ""))
        except Exception as exc:  # noqa: BLE001 — Stripe retries on non-2xx
            log.warning("stripe webhook rejected: %s", exc)
            return jsonify({"error": "invalid"}), 400
        return jsonify({"received": kind})

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
