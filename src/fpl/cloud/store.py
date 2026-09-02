"""Accounts and sessions.

SQLite locally; set DATABASE_URL to a Postgres URL and it uses that instead, so
a free managed Postgres (Neon, Supabase) survives a redeploy on hosts with an
ephemeral filesystem.

Deliberately small. We hold an email address, a saved FPL team id, and session
metadata — nothing else. See docs/PRIVACY.md.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("GAFFER_DB", "data/gaffer.sqlite3"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
_lock = threading.Lock()

CODE_TTL_MINUTES = 15
CODE_MAX_ATTEMPTS = 5
CODE_COOLDOWN_SECONDS = 60

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
  id          TEXT PRIMARY KEY,
  email       TEXT UNIQUE NOT NULL,
  created_at  TEXT NOT NULL,
  last_seen   TEXT,
  team_id     INTEGER,
  team_name   TEXT
);
CREATE TABLE IF NOT EXISTS login_codes (
  email       TEXT PRIMARY KEY,
  code_hash   TEXT NOT NULL,
  expires_at  TEXT NOT NULL,
  attempts    INTEGER NOT NULL DEFAULT 0,
  sent_at     TEXT NOT NULL
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
  id          TEXT PRIMARY KEY,
  email       TEXT UNIQUE NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL,
  last_seen   TIMESTAMPTZ,
  team_id     BIGINT,
  team_name   TEXT
);
CREATE TABLE IF NOT EXISTS login_codes (
  email       TEXT PRIMARY KEY,
  code_hash   TEXT NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL,
  attempts    INTEGER NOT NULL DEFAULT 0,
  sent_at     TIMESTAMPTZ NOT NULL
);
"""


@dataclass
class User:
    id: str
    email: str
    team_id: int | None
    team_name: str | None


def _pg():
    import psycopg
    return psycopg.connect(DATABASE_URL, autocommit=True)


@contextmanager
def db():
    if DATABASE_URL:
        conn = _pg()
        try:
            yield conn, "%s"
        finally:
            conn.close()
        return
    with _lock:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn, "?"
            conn.commit()
        finally:
            conn.close()


def _one(conn, sql, args=()):
    cur = conn.execute(sql, args) if not DATABASE_URL else conn.cursor()
    if DATABASE_URL:
        cur.execute(sql, args)
    row = cur.fetchone()
    if row is None:
        return None
    if DATABASE_URL:
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    return dict(row)


def _exec(conn, sql, args=()):
    if DATABASE_URL:
        conn.cursor().execute(sql, args)
    else:
        conn.execute(sql, args)


def init() -> None:
    with db() as (conn, _):
        if DATABASE_URL:
            for stmt in filter(None, (s.strip() for s in SCHEMA_PG.split(";"))):
                conn.cursor().execute(stmt)
        else:
            conn.executescript(SCHEMA_SQLITE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime):
    return dt if DATABASE_URL else dt.isoformat()


def _dt(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(v)


# --- login codes -------------------------------------------------
def _hash_code(email: str, code: str) -> str:
    """Salted with the server secret so a database copy alone can't be used to
    replay codes."""
    key = os.environ.get("GAFFER_SECRET", "").encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(email: str) -> tuple[str | None, int]:
    """Returns (code, 0) or (None, seconds_to_wait) if one was just sent."""
    email = email.strip().lower()
    with db() as (conn, P):
        row = _one(conn, f"SELECT sent_at FROM login_codes WHERE email={P}", (email,))
        if row:
            waited = (_now() - _dt(row["sent_at"])).total_seconds()
            if waited < CODE_COOLDOWN_SECONDS:
                return None, int(CODE_COOLDOWN_SECONDS - waited)
        code = f"{secrets.randbelow(1000000):06d}"
        args = (email, _hash_code(email, code),
                _iso(_now() + timedelta(minutes=CODE_TTL_MINUTES)), _iso(_now()))
        if DATABASE_URL:
            _exec(conn,
                  "INSERT INTO login_codes (email,code_hash,expires_at,attempts,sent_at) "
                  "VALUES (%s,%s,%s,0,%s) ON CONFLICT (email) DO UPDATE SET "
                  "code_hash=EXCLUDED.code_hash, expires_at=EXCLUDED.expires_at, "
                  "attempts=0, sent_at=EXCLUDED.sent_at", args)
        else:
            _exec(conn,
                  "INSERT INTO login_codes (email,code_hash,expires_at,attempts,sent_at) "
                  "VALUES (?,?,?,0,?) ON CONFLICT(email) DO UPDATE SET "
                  "code_hash=excluded.code_hash, expires_at=excluded.expires_at, "
                  "attempts=0, sent_at=excluded.sent_at", args)
        return code, 0


def verify_code(email: str, code: str) -> User | None:
    """Single use. Wrong codes burn an attempt; five kills the code."""
    email = email.strip().lower()
    with db() as (conn, P):
        row = _one(conn, f"SELECT * FROM login_codes WHERE email={P}", (email,))
        if row is None:
            return None
        if _dt(row["expires_at"]) < _now() or row["attempts"] >= CODE_MAX_ATTEMPTS:
            _exec(conn, f"DELETE FROM login_codes WHERE email={P}", (email,))
            return None
        if not hmac.compare_digest(row["code_hash"], _hash_code(email, code.strip())):
            _exec(conn, f"UPDATE login_codes SET attempts=attempts+1 WHERE email={P}",
                  (email,))
            return None
        _exec(conn, f"DELETE FROM login_codes WHERE email={P}", (email,))
    return get_or_create_user(email)


# --- users -------------------------------------------------------
def get_or_create_user(email: str) -> User:
    email = email.strip().lower()
    with db() as (conn, P):
        row = _one(conn, f"SELECT * FROM users WHERE email={P}", (email,))
        if row is None:
            uid = secrets.token_urlsafe(12)
            _exec(conn,
                  f"INSERT INTO users (id,email,created_at,last_seen) VALUES ({P},{P},{P},{P})",
                  (uid, email, _iso(_now()), _iso(_now())))
            row = _one(conn, f"SELECT * FROM users WHERE id={P}", (uid,))
        else:
            _exec(conn, f"UPDATE users SET last_seen={P} WHERE id={P}",
                  (_iso(_now()), row["id"]))
    return User(id=row["id"], email=row["email"],
                team_id=row["team_id"], team_name=row["team_name"])


def get_user(user_id: str) -> User | None:
    with db() as (conn, P):
        row = _one(conn, f"SELECT * FROM users WHERE id={P}", (user_id,))
    if row is None:
        return None
    return User(id=row["id"], email=row["email"],
                team_id=row["team_id"], team_name=row["team_name"])


def set_team(user_id: str, team_id: int | None, team_name: str | None = None) -> None:
    with db() as (conn, P):
        _exec(conn, f"UPDATE users SET team_id={P}, team_name={P} WHERE id={P}",
              (team_id, team_name, user_id))


def delete_user(user_id: str) -> None:
    """Everything we hold about them, gone. Backs the privacy policy's promise."""
    with db() as (conn, P):
        row = _one(conn, f"SELECT email FROM users WHERE id={P}", (user_id,))
        if row:
            _exec(conn, f"DELETE FROM login_codes WHERE email={P}", (row["email"],))
        _exec(conn, f"DELETE FROM users WHERE id={P}", (user_id,))
