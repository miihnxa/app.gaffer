"""Fixture lookups + the rolling difficulty scores from spec 2.2."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..api.model import Bootstrap


@dataclass
class Fixture:
    gw: int | None
    opponent: str
    home: bool
    difficulty: int
    kickoff: datetime | None

    def label(self) -> str:
        return f"{self.opponent} ({'H' if self.home else 'A'})"


class FixtureBook:
    """All fixtures, indexed by team."""

    def __init__(self, bs: Bootstrap, fixtures: list[dict]):
        self.bs = bs
        self.by_team: dict[int, list[Fixture]] = {t: [] for t in bs.teams}
        for f in fixtures:
            if f.get("event") is None:
                continue  # postponed / not yet scheduled
            ko = f.get("kickoff_time")
            ko_dt = (datetime.fromisoformat(ko.replace("Z", "+00:00"))
                     if ko else None)
            self.by_team[f["team_h"]].append(Fixture(
                f["event"], bs.team_short(f["team_a"]), True,
                f["team_h_difficulty"], ko_dt))
            self.by_team[f["team_a"]].append(Fixture(
                f["event"], bs.team_short(f["team_h"]), False,
                f["team_a_difficulty"], ko_dt))
        for team in self.by_team:
            self.by_team[team].sort(key=lambda x: (x.gw or 99))

    def for_team(self, team_id: int, gw: int) -> list[Fixture]:
        """A list — a team can have zero (blank) or two (double) in a GW."""
        return [f for f in self.by_team[team_id] if f.gw == gw]

    def next_n(self, team_id: int, from_gw: int, n: int = 5) -> list[Fixture]:
        return [f for f in self.by_team[team_id]
                if f.gw is not None and from_gw <= f.gw < from_gw + n]

    def difficulty_score(self, team_id: int, from_gw: int, n: int = 5) -> float:
        """Mean FDR over n gameweeks. Lower is better. Blanks score 5."""
        total, count = 0.0, 0
        for gw in range(from_gw, from_gw + n):
            fx = self.for_team(team_id, gw)
            if not fx:
                total += 5.0
                count += 1
            else:
                total += sum(f.difficulty for f in fx) / len(fx)
                count += 1
        return round(total / count, 2) if count else 5.0

    def ticker(self, from_gw: int, n: int = 5) -> list[tuple[str, float]]:
        rows = [(self.bs.team_short(t), self.difficulty_score(t, from_gw, n))
                for t in self.by_team]
        return sorted(rows, key=lambda r: r[1])
