"""Recommended team — the rules it must never break. Offline, no network."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fpl.api.model import Player
from fpl.engine import lineup
from fpl.engine.fixtures import FixtureBook
from fpl.engine.squad import Pick, Squad

POS = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}

# Starting eleven (4-4-2) then the bench, keeper first — ids are positions 1..15.
LAYOUT = (["GKP"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2 +
          ["GKP", "DEF", "MID", "FWD"])


class FakeBootstrap:
    def __init__(self, n_teams):
        self.teams = {i: {"id": i, "short_name": f"T{i}"} for i in range(1, n_teams + 1)}

    def team_short(self, tid):
        return self.teams[tid]["short_name"]


def build(overrides=None, difficulty=3):
    """Fifteen players, one per club. Clubs 1-16 play in pairs; club 17 blanks."""
    overrides = overrides or {}
    bs = FakeBootstrap(17)
    picks = []
    for i, pos in enumerate(LAYOUT):
        pid = i + 1
        o = {"form": "5.0", "ppg": "5.0", "minutes": 270, "status": "a",
             "chance": None, "team": pid, **overrides.get(pid, {})}
        player = Player({
            "id": pid, "web_name": f"P{pid}", "team": o["team"],
            "element_type": POS[pos], "now_cost": 50, "status": o["status"],
            "chance_of_playing_next_round": o["chance"], "form": o["form"],
            "points_per_game": o["ppg"], "minutes": o["minutes"], "news": "",
            "total_points": 10, "selected_by_percent": "5.0",
        }, f"T{o['team']}")
        picks.append(Pick(player=player, position=pid,
                          is_captain=pid == 1, is_vice_captain=pid == 2))
    fixtures = [{"event": 5, "team_h": h, "team_a": h + 1,
                 "team_h_difficulty": difficulty, "team_a_difficulty": difficulty,
                 "kickoff_time": None} for h in range(1, 16, 2)]
    return Squad(picks=picks, event=5, bank=0.0, value=100.0, source="api"), \
        FixtureBook(bs, fixtures)


def positions(r, ids):
    return [r["players"][str(i)]["pos"] for i in ids]


class RecommendedTeam(unittest.TestCase):
    def test_eleven_is_always_a_legal_formation(self):
        r = lineup.recommend(*build(), gw=5, games_played=3)
        self.assertEqual(len(r["xi"]), 11)
        self.assertEqual(len(r["bench"]), 4)
        pos = positions(r, r["xi"])
        self.assertEqual(pos.count("GKP"), 1)
        self.assertTrue(3 <= pos.count("DEF") <= 5)
        self.assertTrue(2 <= pos.count("MID") <= 5)
        self.assertTrue(1 <= pos.count("FWD") <= 3)

    def test_reserve_keeper_is_first_on_the_bench(self):
        r = lineup.recommend(*build(), gw=5, games_played=3)
        self.assertEqual(positions(r, r["bench"][:1]), ["GKP"])

    def test_injured_starter_is_benched_even_on_top_form(self):
        r = lineup.recommend(*build({5: {"status": "i", "chance": 0, "form": "9.0"}}),
                             gw=5, games_played=3)
        self.assertNotIn(5, r["xi"])
        self.assertTrue(any(c["off_id"] == 5 for c in r["changes"]))

    def test_player_with_no_fixture_does_not_start(self):
        r = lineup.recommend(*build({6: {"team": 17, "form": "9.0"}}), gw=5, games_played=3)
        self.assertNotIn(6, r["xi"])

    def test_better_bench_player_comes_on(self):
        r = lineup.recommend(*build({13: {"form": "9.0"}, 3: {"form": "1.0", "ppg": "1.0"}}),
                             gw=5, games_played=3)
        self.assertIn(13, r["xi"])
        self.assertNotIn(3, r["xi"])

    def test_player_who_rarely_plays_does_not_start_over_a_regular(self):
        # Same form, but P14 has played 20 minutes in three gameweeks.
        r = lineup.recommend(*build({14: {"minutes": 20}}), gw=5, games_played=3)
        self.assertNotIn(14, r["xi"])

    def test_captain_and_vice_are_the_two_highest_rated_starters(self):
        r = lineup.recommend(*build({10: {"form": "12.0"}, 7: {"form": "10.0"}}),
                             gw=5, games_played=3)
        self.assertEqual(r["captain"], 10)
        self.assertEqual(r["vice"], 7)

    def test_captain_is_never_benched(self):
        r = lineup.recommend(*build({15: {"form": "15.0"}}), gw=5, games_played=3)
        self.assertIn(r["captain"], r["xi"])
        self.assertIn(r["vice"], r["xi"])

    def test_a_team_that_already_matches_reports_no_changes(self):
        sq, fb = build()
        r = lineup.recommend(sq, fb, gw=5, games_played=3)
        by_id = {p.player.id: p for p in sq.picks}
        for slot, pid in enumerate(r["xi"] + r["bench"], start=1):
            by_id[pid].position = slot
        for p in sq.picks:
            p.is_captain = p.player.id == r["captain"]
            p.is_vice_captain = p.player.id == r["vice"]
        again = lineup.recommend(sq, fb, gw=5, games_played=3)
        self.assertTrue(again["matches_current"])
        self.assertEqual(again["changes"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
