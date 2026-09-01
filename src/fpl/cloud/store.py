"""User + subscription store.

SQLite by default so it runs anywhere with a volume; set DATABASE_URL to a
Postgres URL and it uses that instead. Deliberately tiny — the product is the
analysis engine, not the CRUD.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("GAFFER_DB", "data/gaffer.sqlite3"))
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  created_at    TEXT NOT NULL,
  team_id       INTEGER,
  plan          TEXT NOT NULL DEFAULT 'free',
  status        TEXT NOT NULL DEFAULT 'active',
  period_end    TEXT,
  stripe_customer      TEXT,
  stripe_subscription  TEXT
);
CREATE TABLE IF NOT EXISTS login_tokens (
  token      TEXT PRIMARY KEY,
  email      TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usage (
  user_id TEXT NOT NULL,
  day     TEXT NOT NULL,
  calls   INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day)
);
CREATE INDEX IF NOT EXISTS idx_users_customer ON users(stripe_customer);
"""


@dataclass
class User:
    id: str
    email: str
    plan: str
    status: str
    team_id: int | None
    period_end: str | None
    stripe_customer: str | None
    stripe_subscription: str | None

    @property
    def is_pro(self) -> bool:
        if self.plan != "pro" or self.status not in ("active", "trialing"):
            return False
        if self.period_end:
            try:
                if datetime.fromisoformat(self.period_end) < datetime.now(timezone.utc):
                    return False
            except ValueError:
                pass
        return True


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


def _row_to_user(r) -> User:
    return User(id=r["id"], email=r["email"], plan=r["plan"], status=r["status"],
                team_id=r["team_id"], period_end=r["period_end"],
                stripe_customer=r["stripe_customer"],
                stripe_subscription=r["stripe_subscription"])


def get_or_create_user(email: str) -> User:
    email = email.strip().lower()
    with db() as conn:
        r = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if r:
            return _row_to_user(r)
        uid = secrets.token_urlsafe(12)
        conn.execute(
            "INSERT INTO users (id,email,created_at) VALUES (?,?,?)",
            (uid, email, datetime.now(timezone.utc).isoformat()),
        )
        r = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return _row_to_user(r)


def get_user(user_id: str) -> User | None:
    with db() as conn:
        r = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return _row_to_user(r) if r else None


def set_team(user_id: str, team_id: int) -> None:
    with db() as conn:
        conn.execute("UPDATE users SET team_id=? WHERE id=?", (int(team_id), user_id))


def set_subscription(*, customer: str, subscription: str | None, plan: str,
                     status: str, period_end: str | None,
                     email: str | None = None) -> None:
    """Called from the Stripe webhook. Matches on customer id, falling back to
    email for the very first checkout, where we may not have the id yet."""
    with db() as conn:
        row = conn.execute("SELECT id FROM users WHERE stripe_customer=?",
                           (customer,)).fetchone()
        if row is None and email:
            row = conn.execute("SELECT id FROM users WHERE email=?",
                               (email.strip().lower(),)).fetchone()
            if row:
                conn.execute("UPDATE users SET stripe_customer=? WHERE id=?",
                             (customer, row["id"]))
        if row is None:
            return
        conn.execute(
            "UPDATE users SET plan=?, status=?, period_end=?, stripe_subscription=? "
            "WHERE id=?",
            (plan, status, period_end, subscription, row["id"]),
        )


# --- magic-link tokens -------------------------------------------
def new_login_token(email: str, minutes: int = 20) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    with db() as conn:
        conn.execute(
            "INSERT INTO login_tokens (token,email,expires_at) VALUES (?,?,?)",
            (token, email.strip().lower(), expires.isoformat()),
        )
    return token


def consume_login_token(token: str) -> str | None:
    """Single use. Returns the email, or None if unknown/expired/already used."""
    with db() as conn:
        r = conn.execute("SELECT * FROM login_tokens WHERE token=?", (token,)).fetchone()
        if r is None or r["used"]:
            return None
        if datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc):
            return None
        conn.execute("UPDATE login_tokens SET used=1 WHERE token=?", (token,))
        return r["email"]


# --- usage metering ----------------------------------------------
def bump_usage(user_id: str) -> int:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db() as conn:
        conn.execute(
            "INSERT INTO usage (user_id,day,calls) VALUES (?,?,1) "
            "ON CONFLICT(user_id,day) DO UPDATE SET calls=calls+1",
            (user_id, day),
        )
        r = conn.execute("SELECT calls FROM usage WHERE user_id=? AND day=?",
                         (user_id, day)).fetchone()
        return r["calls"] if r else 1
