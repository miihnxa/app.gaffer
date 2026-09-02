"""Gaffer account service.

Identity only. The desktop app fetches FPL data itself — this holds an email
address and the team id you saved, so your setup follows you between machines.

Free to use. Read-only against the public FPL API; never signs in to anyone's
FPL account and never changes a team.
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


# Legal pages must never ship a placeholder contact address, and must never
# carry a personal one. Set GAFFER_CONTACT_EMAIL; the app refuses to serve them
# unset rather than publishing something wrong.
CONTACT_EMAIL = os.environ.get("GAFFER_CONTACT_EMAIL", "").strip()
LEGAL_PAGES = ("privacy.html", "terms.html", "licence.html")


def _render_legal(name: str) -> tuple[str, int]:
    body = (WEB / name).read_text()
    if not CONTACT_EMAIL:
        log.error("GAFFER_CONTACT_EMAIL is not set — refusing to serve %s", name)
        return ("<h1>Not configured</h1><p>This page needs a contact address before "
                "it can be published. Set GAFFER_CONTACT_EMAIL.</p>"), 503
    return body.replace("{{CONTACT_EMAIL}}", CONTACT_EMAIL), 200


def base_url() -> str:
    return os.environ.get("GAFFER_BASE_URL", request.host_url.rstrip("/"))


def create_app() -> Flask:
    store.init()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    allowed = [o.strip() for o in
               os.environ.get("GAFFER_CORS_ORIGINS", "").split(",") if o.strip()]

    @app.after_request
    def edge_cache(resp):
        # Public FPL responses are identical for everyone, so a CDN can hold
        # them. Anything account-shaped must never be cached.
        private = request.path.startswith(("/api/me", "/api/auth", "/api/config"))
        if request.path.startswith("/api/") and resp.status_code == 200 and not private:
            resp.headers.setdefault(
                "Cache-Control",
                "public, max-age=60, s-maxage=300, stale-while-revalidate=600")
        elif private:
            resp.headers["Cache-Control"] = "no-store"
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
            ok, retry = limits.check(auth.current_user())
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

    # ===================== auth =====================
    @app.post("/api/auth/request")
    def auth_request():
        email = ((request.json or {}).get("email") or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1] or len(email) > 200:
            return jsonify({"error": "Enter a valid email address.",
                            "code": "bad_email"}), 400
        code, wait = store.issue_code(email)
        if code is None:
            return jsonify({"error": f"A code was just sent. Try again in {wait}s.",
                            "code": "cooldown", "retry_after": wait}), 429
        try:
            auth.send_code(email, code)
        except Exception:  # noqa: BLE001
            log.exception("could not send sign-in code")
            return jsonify({"error": "We couldn't send that email. Try again shortly.",
                            "code": "send_failed"}), 502
        # Identical whether or not the address has an account, so this can't be
        # used to find out who does.
        return jsonify({"ok": True, "message": "Check your email for a 6-digit code."})

    @app.post("/api/auth/verify")
    def auth_verify():
        body = request.json or {}
        email = (body.get("email") or "").strip().lower()
        code = str(body.get("code") or "").strip()
        if not email or not code:
            return jsonify({"error": "Enter the code from your email.",
                            "code": "bad_request"}), 400
        user = store.verify_code(email, code)
        if user is None:
            return jsonify({"error": "That code is wrong or has expired. "
                                     "Request a new one.", "code": "bad_code"}), 401
        return jsonify({"token": auth.issue(user),
                        "user": {"email": user.email, "team_id": user.team_id,
                                 "team_name": user.team_name}})

    @app.post("/api/auth/logout")
    def logout():
        resp = make_response(jsonify({"ok": True}))
        resp.delete_cookie("gaffer_session")
        return resp

    # ===================== account =====================
    @app.get("/api/me")
    @auth.optional_user
    def me():
        u = g.user
        if u is None:
            return jsonify({"signed_in": False})
        return jsonify({"signed_in": True, "email": u.email,
                        "team_id": u.team_id, "team_name": u.team_name})

    @app.post("/api/me/team")
    @auth.login_required
    def save_team():
        tid = (request.json or {}).get("team_id")
        if tid in (None, ""):
            store.set_team(g.user.id, None, None)
            return jsonify({"ok": True, "team_id": None})
        try:
            tid = int(tid)
        except (TypeError, ValueError):
            return jsonify({"error": "Team ID must be a number.",
                            "code": "bad_team"}), 400
        entry = cache.service().entry(tid)      # raises TeamNotFound if unreal
        store.set_team(g.user.id, tid, entry["name"])
        return jsonify({"ok": True, "team_id": tid, "team_name": entry["name"]})

    @app.post("/api/me/delete")
    @auth.login_required
    def delete_me():
        store.delete_user(g.user.id)
        return jsonify({"ok": True})

    # ===================== public FPL =====================
    @app.get("/api/season")
    def season():
        return jsonify(cache.service().season())

    @app.get("/api/team/<int:team_id>")
    def team(team_id: int):
        return jsonify(cache.service().team_payload(team_id, with_replacements=True))

    @app.get("/api/team/<int:team_id>/rebuild")
    def rebuild(team_id: int):
        locked = [int(x) for x in request.args.getlist("lock") if x.isdigit()]
        return jsonify(cache.service().rebuild(
            team_id, locked_ids=locked,
            bench_budget=float(request.args.get("bench", 19.0)),
            budget=request.args.get("budget", type=float)))

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

    # ===================== pages =====================
    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True})

    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/<path:name>")
    def page(name: str):
        target = f"{name}.html" if not name.endswith(".html") else name
        if target in LEGAL_PAGES:
            body, status = _render_legal(target)
            resp = make_response(body, status)
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
        if (WEB / name).is_file():
            return send_from_directory(WEB, name)
        if (WEB / target).is_file():
            return send_from_directory(WEB, target)
        return jsonify({"error": "Not found"}), 404

    return app
