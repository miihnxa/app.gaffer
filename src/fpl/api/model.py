"""Thin typed views over bootstrap-static."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

STATUS_TEXT = {
    "a": "available",
    "d": "doubtful",
    "i": "injured",
    "s": "suspended",
    "u": "unavailable",
    "n": "not in squad",
}
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


@dataclass
class Player:
    raw: dict
    team_short: str

    @property
    def id(self) -> int: return int(self.raw["id"])
    @property
    def name(self) -> str: return self.raw["web_name"]
    @property
    def pos(self) -> str: return POS.get(self.raw["element_type"], "?")
    @property
    def price(self) -> float: return self.raw["now_cost"] / 10.0
    @property
    def status(self) -> str: return self.raw["status"]
    @property
    def status_text(self) -> str: return STATUS_TEXT.get(self.status, self.status)
    @property
    def form(self) -> float: return float(self.raw.get("form") or 0.0)
    @property
    def news(self) -> str: return (self.raw.get("news") or "").strip()
    @property
    def total_points(self) -> int: return int(self.raw.get("total_points") or 0)
    @property
    def selected_by(self) -> float: return float(self.raw.get("selected_by_percent") or 0)

    @property
    def chance(self) -> int | None:
        v = self.raw.get("chance_of_playing_next_round")
        return None if v is None else int(v)

    @property
    def effective_chance(self) -> int:
        """None means 'no doubt recorded' for available players, but for a
        non-available status it means unknown — treat that as 0."""
        c = self.chance
        if c is not None:
            return c
        return 100 if self.status == "a" else 0

    @property
    def is_flagged(self) -> bool:
        return self.status != "a" or self.effective_chance < 100

    @property
    def price_rise_percent(self) -> float:
        """Progress toward the next price change (this season's API exposes it
        directly, so we don't have to infer it from transfer counts)."""
        return float(self.raw.get("price_change_percent") or 0.0)

    def label(self) -> str:
        return f"{self.name} ({self.team_short}, {self.pos}, £{self.price:.1f}m)"


class Bootstrap:
    def __init__(self, data: dict):
        self.data = data
        self.teams = {t["id"]: t for t in data["teams"]}
        self._players = {
            int(e["id"]): Player(e, self.teams[e["team"]]["short_name"])
            for e in data["elements"]
        }

    def player(self, pid: int) -> Player | None:
        return self._players.get(int(pid))

    def players(self, ids) -> list[Player]:
        out = []
        for pid in ids:
            p = self.player(pid)
            if p is None:
                raise KeyError(f"player id {pid} not found in bootstrap-static")
            out.append(p)
        return out

    def all_players(self) -> list[Player]:
        return list(self._players.values())

    def team_short(self, tid: int) -> str:
        return self.teams[tid]["short_name"]

    # --- events ----------------------------------------------------
    @property
    def events(self) -> list[dict]:
        return self.data["events"]

    def event(self, gw: int) -> dict | None:
        return next((e for e in self.events if e["id"] == gw), None)

    def current_event(self) -> dict | None:
        return next((e for e in self.events if e.get("is_current")), None)

    def next_event(self) -> dict | None:
        return next((e for e in self.events if e.get("is_next")), None)

    @staticmethod
    def deadline(event: dict) -> datetime:
        return datetime.fromisoformat(
            event["deadline_time"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)

    def chip_stop_event(self, chip: str, first_half: bool = True) -> int | None:
        """Read the real chip expiry from the API instead of hardcoding GW19."""
        matches = [
            c for c in self.data.get("chips", [])
            if c.get("name") == chip and (c.get("start_event", 99) < 20) == first_half
        ]
        return matches[0].get("stop_event") if matches else None
