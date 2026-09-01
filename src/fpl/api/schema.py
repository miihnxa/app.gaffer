"""Schema validation.

Build spec, section 1: "These are undocumented endpoints... Field shapes shift
between seasons. Write a schema validation step that runs first and fails
loudly."

This runs before any engine reads the payload. If the FPL API changes shape
mid-season we want a clear, actionable error rather than a wrong alert.
"""
from __future__ import annotations


class SchemaError(RuntimeError):
    """Raised when the FPL API no longer looks like we expect."""


# Fields every engine depends on. Losing any of these silently would produce
# wrong advice, which is worse than no advice.
BOOTSTRAP_TOP = ("events", "teams", "elements", "element_types", "chips")

ELEMENT_FIELDS = (
    "id", "web_name", "team", "element_type", "now_cost", "status",
    "chance_of_playing_next_round", "form", "news", "total_points",
    "selected_by_percent", "cost_change_event",
)

EVENT_FIELDS = ("id", "name", "deadline_time", "finished", "is_current", "is_next")

TEAM_FIELDS = ("id", "name", "short_name")

FIXTURE_FIELDS = (
    "event", "team_h", "team_a", "team_h_difficulty", "team_a_difficulty",
    "kickoff_time", "finished",
)

PICK_FIELDS = ("element", "position", "multiplier", "is_captain", "is_vice_captain")


def _missing(obj: dict, fields: tuple[str, ...]) -> list[str]:
    return [f for f in fields if f not in obj]


def _check(sample: dict, fields: tuple[str, ...], where: str) -> None:
    missing = _missing(sample, fields)
    if missing:
        raise SchemaError(
            f"{where}: FPL API is missing expected field(s) {missing}. "
            f"The endpoint shape has changed — update src/fpl/api/schema.py "
            f"and the engines that read these fields before trusting any alert."
        )


def validate_bootstrap(data: dict) -> None:
    if not isinstance(data, dict):
        raise SchemaError(f"bootstrap-static: expected an object, got {type(data).__name__}")

    missing = _missing(data, BOOTSTRAP_TOP)
    if missing:
        raise SchemaError(f"bootstrap-static: missing top-level key(s) {missing}")

    for key in ("events", "teams", "elements"):
        if not data[key]:
            raise SchemaError(f"bootstrap-static: '{key}' is empty")

    _check(data["elements"][0], ELEMENT_FIELDS, "bootstrap-static.elements[0]")
    _check(data["events"][0], EVENT_FIELDS, "bootstrap-static.events[0]")
    _check(data["teams"][0], TEAM_FIELDS, "bootstrap-static.teams[0]")

    # The spec calls this out by name: the events array previously exposed
    # top-level current_event/next_event integers and now uses per-event
    # is_current/is_next booleans. Confirm exactly one current-ish event.
    if sum(1 for e in data["events"] if e.get("is_current")) > 1:
        raise SchemaError("bootstrap-static: more than one event flagged is_current")
    if sum(1 for e in data["events"] if e.get("is_next")) > 1:
        raise SchemaError("bootstrap-static: more than one event flagged is_next")

    statuses = {e.get("status") for e in data["elements"]}
    unknown = statuses - {"a", "d", "i", "s", "u", "n"}
    if unknown:
        raise SchemaError(
            f"bootstrap-static: unrecognised player status code(s) {sorted(unknown)}. "
            f"Known: a=available d=doubtful i=injured s=suspended u=unavailable n=not-in-squad"
        )


def validate_fixtures(data: list) -> None:
    if not isinstance(data, list):
        raise SchemaError(f"fixtures: expected a list, got {type(data).__name__}")
    if data:
        _check(data[0], FIXTURE_FIELDS, "fixtures[0]")


def validate_picks(data: dict) -> None:
    if not isinstance(data, dict) or "picks" not in data:
        raise SchemaError("entry picks: missing 'picks'")
    if data["picks"]:
        _check(data["picks"][0], PICK_FIELDS, "entry picks.picks[0]")
    if len(data["picks"]) != 15:
        raise SchemaError(f"entry picks: expected 15 picks, got {len(data['picks'])}")


def validate_entry(data: dict) -> None:
    for f in ("id", "name", "summary_overall_points"):
        if f not in data:
            raise SchemaError(f"entry: missing '{f}'")
