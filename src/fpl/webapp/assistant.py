"""The assistant — a second opinion on your squad.

Grounded deliberately hard: the model is given the actual squad, fixtures, form,
flags and rule-engine findings, and told to answer only from them. An FPL
assistant that invents a price or a fixture is worse than no assistant, because
it is wrong in a way that looks authoritative.

The API key is the user's own and never reaches the page — the browser talks to
this process, and this process talks to Anthropic.
"""
from __future__ import annotations

import json
import logging
from typing import Iterator

from .service import Service

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 8000

SYSTEM = """You are the assistant manager for a Fantasy Premier League team. The \
human is the manager; you are their right hand. You are direct, concise and \
willing to disagree with them.

GROUNDING — this matters more than anything else:
- Answer ONLY from the SQUAD DATA below. It is live, fetched seconds ago.
- Never invent a player, price, fixture, form figure or deadline. If something \
isn't in the data, say you don't have it.
- Prices are in millions. Form is FPL's own 30-day average. Fixture difficulty \
runs 1 (easiest) to 5 (hardest).
- The data covers this manager's squad plus any players named in the findings. \
You do not have the full player database, so don't rank "the best midfielder in \
the game" — say what you can see.

HOW TO ANSWER:
- Lead with the recommendation, then the reason. Two or three sentences for a \
simple question.
- Quote the numbers you're reasoning from — form, difficulty, price — so the \
manager can check you.
- When it's close, say it's close and name what would settle it.
- Disagree when the data says so. Do not flatter a bad idea.
- If a transfer would break one of the manager's own rules, say which rule.
- Use British football vocabulary. No emoji, no headings, no bullet lists \
unless comparing three or more options.

WHAT YOU CANNOT DO:
- You cannot make transfers, set a captain, or change the team. FPL has no API \
for that. Tell the manager what to do and they will do it themselves.
- You do not know anything that happened after the data below was fetched — no \
press conferences, no team news, no injuries beyond the flags shown."""


def _squad_lines(payload: dict) -> str:
    rows = []
    for group, label in ((payload["squad"]["xi"], "XI"), (payload["squad"]["bench"], "BENCH")):
        for p in group:
            fx = ", ".join(f"{f['opponent']} {'H' if f['home'] else 'A'} (difficulty {f['difficulty']})"
                           for f in p["fixtures_gw"]) or "NO FIXTURE — blank gameweek"
            marks = []
            if p["is_captain"]:
                marks.append("CAPTAIN")
            if p["is_vice"]:
                marks.append("vice")
            if p["status"] != "ok":
                marks.append(f"{p['status'].upper()}, {p['chance']}% to play"
                             + (f" — {p['news']}" if p["news"] else ""))
            rows.append(
                f"  [{label}] {p['name']} ({p['club']}, {p['pos']}) "
                f"£{p['price']}m, form {p['form']}, {p['points']} pts, "
                f"{p['minutes']} mins, owned {p['selected']}%, "
                f"next 5 difficulty {p['fdr5']} | GW fixture: {fx}"
                + (f" | {'; '.join(marks)}" if marks else "")
            )
    return "\n".join(rows)


def _context(svc: Service, payload: dict) -> str:
    sq, entry = payload["squad"], payload["entry"]
    season = svc.season()
    parts = [
        f"GAMEWEEK {season['next_gw']} — deadline {season['deadline_local']} "
        f"({season['countdown']} away, timezone {season['timezone']})",
        "",
        f"MANAGER: {entry['name']} — {entry['overall_points']} points overall, "
        f"world rank {entry['overall_rank']:,}" if entry.get("overall_rank") else "",
        f"Squad value £{sq['value']}m, bank £{sq['bank']}m, formation {sq['formation']}",
        f"Squad source: {sq['note']}",
        "",
        "SQUAD DATA:",
        _squad_lines(payload),
    ]
    if sq.get("swaps"):
        parts += ["", "TRANSFERS THE MANAGER HAS ALREADY MADE (not yet public on FPL):"]
        parts += [f"  {s['out']} out, {s['in']} in" for s in sq["swaps"]]

    if payload.get("advice"):
        parts += ["", "FINDINGS from the rule engine (already checked, trust these):"]
        parts += [f"  [{a['severity']}] {a['title']} — {a['detail']}" for a in payload["advice"]]

    reps = [(p["name"], p["replacements"]) for p in
            payload["squad"]["xi"] + payload["squad"]["bench"] if p.get("replacements")]
    if reps:
        parts += ["", "REPLACEMENTS that already pass the manager's rules "
                      "(higher form, fit, affordable, legal on 3-per-club):"]
        for name, rs in reps:
            for r in rs[:4]:
                parts.append(
                    f"  For {name}: {r['name']} ({r['club']}) £{r['price']}m, "
                    f"form {r['form']} (+{r['form_delta']} on {name}), "
                    f"costs £{r['cost']}m, next {r['fixture']} difficulty {r['fdr']}, "
                    f"next-5 difficulty {r['fdr5']}")

    if payload.get("leagues"):
        parts += ["", "MINI-LEAGUES: " + ", ".join(
            f"{l['name']} (rank {l['rank']})" for l in payload["leagues"][:4] if l.get("rank"))]

    rules = svc.cfg.plan.get("rules", {})
    if rules:
        parts += ["", "THE MANAGER'S OWN RULES:",
                  f"  No -4 hits before gameweek {rules.get('no_hits_before_gw', 6)}",
                  "  Never transfer in a player with lower current form than the one going out",
                  f"  Max {rules.get('max_players_per_club', 3)} players per club, "
                  f"min {rules.get('min_defenders', 3)} defenders"]
    return "\n".join(x for x in parts if x != "")


def available(api_key: str | None) -> bool:
    return bool(api_key)


def stream_reply(svc: Service, api_key: str, team_id: int,
                 history: list[dict], swaps: dict | None = None) -> Iterator[str]:
    """Yields server-sent events. Errors arrive as an `error` event, never as
    a broken stream, so the UI can always say what went wrong."""
    import anthropic

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        payload = svc.team_payload(team_id, swaps=swaps or {})
    except Exception as exc:  # noqa: BLE001
        yield sse("error", {"message": f"Couldn't read the squad: {exc}"})
        return

    client = anthropic.Anthropic(api_key=api_key)
    system = [
        {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": _context(svc, payload)},
    ]
    messages = [{"role": m["role"], "content": m["content"]}
                for m in history if m.get("content")][-20:]

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            thinking={"type": "adaptive"},
        ) as stream:
            for text in stream.text_stream:
                yield sse("delta", {"text": text})
            final = stream.get_final_message()
        if final.stop_reason == "refusal":
            yield sse("error", {"message": "The model declined to answer that one. "
                                           "Try rephrasing."})
        yield sse("done", {})
    except anthropic.AuthenticationError:
        yield sse("error", {"message": "That API key was rejected. Check it in Settings."})
    except anthropic.RateLimitError:
        yield sse("error", {"message": "Rate limited by the API. Wait a moment and try again."})
    except anthropic.APIStatusError as exc:
        log.warning("assistant API error: %s", exc)
        yield sse("error", {"message": f"The API returned an error ({exc.status_code})."})
    except anthropic.APIConnectionError:
        yield sse("error", {"message": "Couldn't reach the API. Check your connection."})
    except Exception as exc:  # noqa: BLE001
        log.exception("assistant failed")
        yield sse("error", {"message": f"Something went wrong: {exc}"})
