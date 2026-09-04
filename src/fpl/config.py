"""Config loading and paths."""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

def _frozen() -> bool:
    """True inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundled_dir() -> Path:
    """Read-only resources shipped with the app."""
    if _frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def user_dir() -> Path:
    """Everything the app writes.

    An installed app is read-only (and on macOS, writing inside a signed bundle
    breaks the signature), so config, caches and logs live wherever the platform
    keeps per-user application data.
    """
    if not _frozen():
        return Path(__file__).resolve().parents[2]
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Gaffer"
    if sys.platform == "win32":
        # %APPDATA% roams with the user profile; fall back if it is unset.
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Gaffer"
    # Linux and the rest: the XDG default.
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "Gaffer"


ROOT = bundled_dir()
CONFIG_DIR = user_dir() / "config"
DEFAULTS_DIR = bundled_dir() / "defaults"
DATA_DIR = user_dir() / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
LOG_DIR = user_dir() / "logs"


def seed_user_config() -> None:
    """First run: copy the shipped defaults into the user's directory.

    Only ever copies what is missing, so a user's edits are never overwritten
    by an app update.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("settings.yaml", "watchlist.yaml", "season-plan.yaml"):
        target = CONFIG_DIR / name
        if target.exists():
            continue
        for candidate in (DEFAULTS_DIR / name, DEFAULTS_DIR / f"{name[:-5]}.example.yaml",
                          DEFAULTS_DIR / "settings.example.yaml"):
            if candidate.exists() and (candidate.name == name
                                       or name == "settings.yaml"):
                shutil.copyfile(candidate, target)
                break


class ConfigError(RuntimeError):
    pass


def _load(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        path = DEFAULTS_DIR / name
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class Config:
    settings: dict[str, Any] = field(default_factory=dict)
    watchlist: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        cfg = cls(
            settings=_load("settings.yaml"),
            watchlist=_load("watchlist.yaml"),
            plan=_load("season-plan.yaml"),
        )
        seed_user_config()
        cfg._apply_env()
        for d in (DATA_DIR, SNAPSHOT_DIR, LOG_DIR):
            d.mkdir(parents=True, exist_ok=True)
        return cfg

    def _apply_env(self) -> None:
        """Environment wins over the file, so CI can inject secrets without
        committing them. Set in GitHub Actions as repository secrets."""
        entry = self.settings.setdefault("entry", {})
        if v := os.environ.get("FPL_TEAM_ID"):
            entry["team_id"] = int(v)
        if v := os.environ.get("FPL_LEAGUE_ID"):
            entry["league_id"] = int(v)
        if v := os.environ.get("FPL_NTFY_TOPIC"):
            self.settings.setdefault("notify", {}).setdefault("ntfy", {})["topic"] = v
        if v := os.environ.get("FPL_NOTIFIER"):
            self.settings.setdefault("notify", {})["provider"] = v
        if v := os.environ.get("FPL_TIMEZONE"):
            self.settings["timezone"] = v

    # --- accessors -------------------------------------------------
    @property
    def team_id(self) -> int | None:
        return (self.settings.get("entry") or {}).get("team_id")

    @property
    def league_id(self) -> int | None:
        return (self.settings.get("entry") or {}).get("league_id")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.settings.get("timezone", "UTC"))

    @property
    def api(self) -> dict[str, Any]:
        return self.settings.get("api", {})

    @property
    def alerts(self) -> dict[str, Any]:
        return self.settings.get("alerts", {})

    def watchlist_ids(self) -> list[int]:
        return [int(p["id"]) for p in self.watchlist.get("watchlist", [])]

    def pending_squad(self) -> dict:
        """The upcoming-deadline squad, recorded by hand. See season-plan.yaml."""
        return self.plan.get("pending_squad", {}) or {}

    def fallback_squad_ids(self) -> list[int]:
        """Squad from the plan — used until team_id is configured."""
        squad = self.pending_squad()
        ids = [int(p["id"]) for p in squad.get("starting_xi", [])]
        ids += [int(p["id"]) for p in squad.get("bench", [])]
        return ids

    def require_team_id(self) -> int:
        if not self.team_id:
            raise ConfigError(
                "team_id is not set. Find it in the URL of your Gameweek History "
                "page (fantasy.premierleague.com/entry/<TEAM_ID>/history), then run:\n"
                "    ./fpl setup --team-id <id>"
            )
        return int(self.team_id)

    def set_entry(self, key: str, value: Any) -> None:
        """Persist a value under `entry:` back to settings.yaml."""
        path = CONFIG_DIR / "settings.yaml"
        if not path.exists():
            seed_user_config()
        text = path.read_text()
        import re

        pattern = re.compile(rf"^(\s*{key}:).*$", re.MULTILINE)
        if not pattern.search(text):
            raise ConfigError(f"could not find '{key}:' in settings.yaml")
        replacement = rf"\g<1> {value}"
        path.write_text(pattern.sub(replacement, text, count=1))
        self.settings.setdefault("entry", {})[key] = value


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
