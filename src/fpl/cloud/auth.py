"""Magic-link auth. No passwords stored, ever."""
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
SESSION_DAYS = 30


def secret() -> str:
    s = os.environ.get("GAFFER_SECRET", "")
    if s and len(s.encode()) < 32:
        # Below 32 bytes an HS256 key is weaker than the hash it feeds.
        raise RuntimeError(
            f"GAFFER_SECRET is only {len(s.encode())} bytes. Use at least 32 — "
            f"`python -c \"import secrets;print(secrets.token_urlsafe(48))\"`."
        )
    if not s:
        # Refuse to run a public service on a guessable signing key.
        raise RuntimeError(
            "GAFFER_SECRET is not set. Generate one with "
            "`python -c \"import secrets;print(secrets.token_urlsafe(48))\"` "
            "and set it in the environment before starting."
        )
    return s


def issue(user: store.User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user.id, "email": user.email,
         "iat": now, "exp": now + timedelta(days=SESSION_DAYS)},
        secret(), algorithm=JWT_ALG,
    )


def read(token: str) -> store.User | None:
    try:
        claims = jwt.decode(token, secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    return store.get_user(claims.get("sub", ""))


def _bearer() -> str | None:
    hdr = request.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip()
    return request.cookies.get("gaffer_session")


def current_user() -> store.User | None:
    tok = _bearer()
    return read(tok) if tok else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if user is None:
            return jsonify({"error": "Sign in to continue.",
                            "code": "auth_required"}), 401
        g.user = user
        return fn(*a, **kw)
    return wrapper


def optional_user(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        g.user = current_user()
        return fn(*a, **kw)
    return wrapper


# --- delivery -----------------------------------------------------
def send_magic_link(email: str, link: str) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        # Dev fallback: print it. Never do this in production — the log becomes
        # a set of working login links.
        log.warning("SMTP not configured; magic link for %s: %s", email, link)
        print(f"\n[dev] magic link for {email}:\n  {link}\n")
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Gaffer sign-in link"
    msg["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    msg["To"] = email
    msg.set_content(
        f"Tap to sign in to Gaffer:\n\n{link}\n\n"
        f"The link works once and expires in 20 minutes.\n"
        f"If you didn't ask for this, ignore it — nothing has changed."
    )
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=20) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
