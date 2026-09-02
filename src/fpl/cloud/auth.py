"""Sessions and code delivery. No passwords exist, so none can leak."""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

import jwt
from flask import g, jsonify, request

from . import store

log = logging.getLogger(__name__)
JWT_ALG = "HS256"
SESSION_DAYS = 90          # a desktop app shouldn't ask you to sign in weekly


def secret() -> str:
    s = os.environ.get("GAFFER_SECRET", "")
    if s and len(s.encode()) < 32:
        raise RuntimeError(
            f"GAFFER_SECRET is only {len(s.encode())} bytes. Use at least 32 — "
            f"`python -c \"import secrets;print(secrets.token_urlsafe(48))\"`."
        )
    if not s:
        raise RuntimeError(
            "GAFFER_SECRET is not set. Generate one with "
            "`python -c \"import secrets;print(secrets.token_urlsafe(48))\"` "
            "and set it in the environment before starting."
        )
    return s


def issue(user: store.User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user.id, "iat": now,
                       "exp": now + timedelta(days=SESSION_DAYS)},
                      secret(), algorithm=JWT_ALG)


def read(token: str) -> store.User | None:
    try:
        claims = jwt.decode(token, secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    return store.get_user(claims.get("sub", ""))


def current_user() -> store.User | None:
    hdr = request.headers.get("Authorization", "")
    token = hdr[7:].strip() if hdr.startswith("Bearer ") else request.cookies.get("gaffer_session")
    return read(token) if token else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if user is None:
            return jsonify({"error": "Sign in to continue.", "code": "auth_required"}), 401
        g.user = user
        return fn(*a, **kw)
    return wrapper


def optional_user(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        g.user = current_user()
        return fn(*a, **kw)
    return wrapper


def send_code(email: str, code: str) -> None:
    host = os.environ.get("SMTP_HOST")
    body = (
        f"Your Gaffer sign-in code is:\n\n    {code}\n\n"
        f"Type it into the app. It expires in {store.CODE_TTL_MINUTES} minutes and "
        f"works once.\n\nIf you didn't ask for this, ignore it — nothing has changed, "
        f"and nobody can sign in without this code."
    )
    if not host:
        # Dev only. In production this log would be a set of working codes.
        log.warning("SMTP not configured; code for %s is %s", email, code)
        print(f"\n[dev] sign-in code for {email}: {code}\n")
        return
    msg = EmailMessage()
    msg["Subject"] = f"{code} is your Gaffer sign-in code"
    msg["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    msg["To"] = email
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=20) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
