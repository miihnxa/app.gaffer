"""Offline tests — no network. Run: ./run-tests"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fpl.api import schema
from fpl.api.model import Bootstrap, Player
from fpl.engine import form, deadlines
from fpl.engine.status import StatusChange


def mk(pid=1, name="X", team=1, et=4, cost=60, status="a", chance=None,
       frm="3.0", news="", pts=10):
    return Player({
        "id": pid, "web_name": name, "team": team, "element_type": et,
        "now_cost": cost, "status": status, "chance_of_playing_next_round": chance,
        "form": frm, "news": news, "total_points": pts, "selected_by_percent": "5.0",
        "cost_change_event": 0, "minutes": 270, "price_change_percent": "10.0",
    }, "TST")


class FormGuard(unittest.TestCase):
    def test_blocks_lower_form(self):
        """The Igor Jesus case: form 1.5 replacing form 2.0."""
        v = form.check_transfer(mk(1, "Brobbey", frm="2.0"),
                                mk(2, "Igor Jesus", frm="1.5"))
        self.assertTrue(v.blocked)
        self.assertIn("BELOW", v.reasons[0])

    def test_allows_higher_form(self):
        v = form.check_transfer(mk(1, "Brobbey", frm="2.0"),
                                mk(2, "Gonzalo", frm="4.0"))
        self.assertFalse(v.blocked)

    def test_override_downgrades_to_note(self):
        v = form.check_transfer(mk(1, "A", frm="5.0"), mk(2, "B", frm="1.0"),
                                override=True)
        self.assertFalse(v.blocked)
        self.assertTrue(any("OVERRIDDEN" in n for n in v.notes))

    def test_blocks_flagged_incoming(self):
        v = form.check_transfer(mk(1, "A", frm="1.0"),
                                mk(2, "B", frm="9.0", status="i", chance=0))
        self.assertTrue(v.blocked)

    def test_blocks_unaffordable(self):
        v = form.check_transfer(mk(1, "A", cost=60, frm="1.0"),
                                mk(2, "B", cost=90, frm="9.0"), bank=1.0)
        self.assertTrue(v.blocked)
        self.assertIn("bank", v.reasons[0])

    def test_blocks_hit_before_gw6(self):
        v = form.check_transfer(mk(1, "A", frm="1.0"), mk(2, "B", frm="9.0"),
                                gw=4, free_transfers=0, no_hits_before_gw=6)
        self.assertTrue(v.blocked)

    def test_allows_hit_from_gw6(self):
        v = form.check_transfer(mk(1, "A", frm="1.0"), mk(2, "B", frm="9.0"),
                                gw=6, free_transfers=0, no_hits_before_gw=6)
        self.assertFalse(v.blocked)

    def test_blocks_fourth_from_a_club(self):
        out_p, in_p = mk(1, "A", frm="1.0"), mk(2, "B", frm="9.0")
        v = form.check_transfer(out_p, in_p, squad_clubs={"TST": 3})
        # both are TST here, so the count is unchanged — must not block
        self.assertFalse(v.blocked)


class Fitness(unittest.TestCase):
    def test_available_with_no_chance_is_fit(self):
        self.assertFalse(mk(status="a", chance=None).is_flagged)

    def test_injured_with_no_chance_is_treated_as_zero(self):
        p = mk(status="i", chance=None)
        self.assertTrue(p.is_flagged)
        self.assertEqual(p.effective_chance, 0)

    def test_doubtful_75_is_flagged(self):
        self.assertTrue(mk(status="d", chance=75).is_flagged)


class StatusDiff(unittest.TestCase):
    def test_worsening(self):
        c = StatusChange(mk(), True, "a", "i", None, 0)
        self.assertTrue(c.worsened)

    def test_recovery(self):
        c = StatusChange(mk(), True, "i", "a", 0, 100)
        self.assertTrue(c.recovered)

    def test_chance_drop_alone_counts(self):
        c = StatusChange(mk(), True, "d", "d", 75, 25)
        self.assertTrue(c.worsened)


class Windows(unittest.TestCase):
    def _info(self, minutes):
        from datetime import datetime, timedelta, timezone
        return deadlines.DeadlineInfo(
            3, "GW3", datetime.now(timezone.utc) + timedelta(minutes=minutes))

    def test_fires_inside_window(self):
        self.assertEqual(deadlines.due_reminders(self._info(40), [1440, 180, 45]), [45])

    def test_silent_outside_window(self):
        self.assertEqual(deadlines.due_reminders(self._info(600), [1440, 180, 45]), [])

    def test_slack_covers_the_polling_gap(self):
        """A reminder must not slip between two hourly runs."""
        self.assertEqual(deadlines.due_reminders(self._info(130), [1440, 180, 45]), [180])


class Schema(unittest.TestCase):
    def _ok(self):
        return {
            "events": [{"id": 1, "name": "GW1", "deadline_time": "2026-08-14T17:30:00Z",
                        "finished": True, "is_current": True, "is_next": False}],
            "teams": [{"id": 1, "name": "Test", "short_name": "TST"}],
            "elements": [mk().raw],
            "element_types": [{"id": 4}], "chips": [],
        }

    def test_accepts_current_shape(self):
        schema.validate_bootstrap(self._ok())

    def test_rejects_missing_field(self):
        d = self._ok(); del d["elements"][0]["form"]
        with self.assertRaises(schema.SchemaError):
            schema.validate_bootstrap(d)

    def test_rejects_missing_top_key(self):
        d = self._ok(); del d["events"]
        with self.assertRaises(schema.SchemaError):
            schema.validate_bootstrap(d)

    def test_rejects_unknown_status_code(self):
        d = self._ok(); d["elements"][0]["status"] = "z"
        with self.assertRaises(schema.SchemaError):
            schema.validate_bootstrap(d)

    def test_rejects_two_current_events(self):
        d = self._ok()
        d["events"].append(dict(d["events"][0], id=2))
        with self.assertRaises(schema.SchemaError):
            schema.validate_bootstrap(d)

    def test_rejects_wrong_pick_count(self):
        with self.assertRaises(schema.SchemaError):
            schema.validate_picks({"picks": [
                {"element": 1, "position": 1, "multiplier": 1,
                 "is_captain": False, "is_vice_captain": False}]})


if __name__ == "__main__":
    unittest.main(verbosity=2)


class BudgetShapes(unittest.TestCase):
    """Wildcard budget arithmetic — the Isak vs Bench Boost tension."""

    def test_shape_c_blocked_while_haaland_is_fit(self):
        from fpl.engine.budget import ShapeCost
        s = ShapeCost("C", "Isak in, Haaland out", "", [mk(cost=90), mk(cost=76)],
                      6.0, 100.0, 19.0,
                      blocked_reason="Haaland is fit")
        self.assertFalse(s.affordable)

    def test_outfield_budget_is_what_is_left(self):
        from fpl.engine.budget import ShapeCost
        s = ShapeCost("A", "", "", [mk(cost=155), mk(cost=90)], 5.5, 100.0, 19.0)
        self.assertEqual(s.forward_spend, 30.0)
        self.assertEqual(s.outfield_budget(), 51.0)


class BenchReadiness(unittest.TestCase):
    """Minutes must be judged against games played, not a fixed 3."""

    def _built(self, minutes):
        from fpl.engine.wildcard import BuiltSquad
        p = mk(1, "B")
        p.raw["minutes"] = minutes
        return BuiltSquad([p], "A", 100.0, 6)

    def test_full_minutes_after_two_games_is_nailed(self):
        b = self._built(180)
        share = 180 / (90.0 * 2)
        self.assertGreaterEqual(share, 0.85)

    def test_zero_minutes_is_not_a_starter(self):
        share = 0 / (90.0 * 2)
        self.assertLess(share, 0.4)
