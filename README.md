# FPL Active Manager Assistant

Watches the *Highbury Reserves* squad and pushes notifications so no deadline,
price change or injury gets missed.

**It advises. It does not act.** No automated transfers, no automated lineup
changes — FPL has no write API, and driving the site with stored session
cookies is fragile and a credential risk. Every output is a notification you
read and act on yourself.

## Setup

```bash
./fpl setup --team-id <YOUR_TEAM_ID>
```

Your team id is in the URL of your Gameweek History page:
`fantasy.premierleague.com/entry/<TEAM_ID>/history`. Setup validates the API,
confirms the team, and auto-discovers the mini-league id from your league list.

Then pick a private ntfy topic in `config/settings.yaml` (anyone who knows the
topic can read your alerts), install the ntfy app on your iPhone, subscribe to
that topic, and check it end to end:

```bash
./fpl test-notify
```

## Gaffer — the Mac app

A native Mac window over a local server. Build it once:

```bash
./build-mac-app.sh
```

That writes `~/Applications/Gaffer.app` — open it from Spotlight, Launchpad or
the Dock like any other app. `./fpl app` launches the same thing from a shell,
and `./fpl app --server-only` runs just the server if you prefer a browser.

**It works for any manager, not just you.** Enter any FPL team ID and it loads
that squad from public data. Four views:

| View | What it does |
|---|---|
| **Squad** | The XI on a pitch, fixtures with difficulty, flagged players, and what to look at before the deadline. Click a player for form, next five fixtures, and the replacements that clear the rules. |
| **Rebuild** | Lock the players you want to keep, set a bench budget, and it builds a legal 15 — buying the bench *first*, so a Bench Boost is worth playing. |
| **Leagues** | Any of your classic leagues. Click a rival to open their squad. |
| **Players** | Search every player in the game. |

Your own team additionally gets the season plan applied — captaincy plan, chip
schedule, Wildcard shapes. Other managers get the generic rules only, since
your plan would be meaningless advice for their team.

The app binds to `127.0.0.1` only, is never exposed to the network, never signs
in, and never changes anyone's team.

**The bundle wraps this folder's venv** rather than freezing a binary — nothing
to re-sign, and it always runs current code. The trade-off is that moving or
deleting this folder breaks the app; re-run `./build-mac-app.sh` after a move.

## Commands

| Command | What it does |
|---|---|
| `./fpl app` | Open the Gaffer desktop app |
| `./fpl setup --team-id N` | Validate API + team, save team_id, find league_id |
| `./fpl squad` | Squad table with fixtures, FDR, form and flags |
| `./fpl pitch` | Build the interactive pitch view (`data/pitch.html`) |
| `./fpl transfer --out X --in Y` | Run a proposed transfer past your rules |
| `./fpl wildcard [--shape A]` | Build a Wildcard squad for a Shape |
| `./fpl check league` | Mini-league standings + rival squad diffs |
| `./fpl check live` | Live points during matches |
| `./fpl check status` | Injury / status watch |
| `./fpl check prices` | Price moves + form table |
| `./fpl check deadline` | Deadline reminders |
| `./fpl check league` | Mini-league standings + rival squad diffs |
| `./fpl check live --force-live` | Live gameweek points and scoring events |
| `./fpl wildcard [--shape A]` | Build a GW6 Wildcard squad per Shape |
| `./fpl check all` | Status, prices, deadline and league |
| `./run-tests` | Offline test suite (no network) |

Add `--dry-run` to any `check` to print instead of notifying.

### The transfer guard

The rule this tool exists for — never transfer in a player with lower current
form than the one going out:

```bash
./fpl transfer --out Brobbey --in "Igor Jesus"
```

```
OUT  Brobbey (SUN, FWD, £6.0m)          form 2.0
IN   Igor Jesus (NFO, FWD, £6.0m)       form 1.5

Form change: -0.5   Cost: £+0.0m

BLOCKED:
  ✗ Igor Jesus form 1.5 is BELOW Brobbey form 2.0 — you'd be paying a
    transfer to move backwards
```

Names are resolved against the live API and **ambiguous names are refused**,
not guessed — there are two Hughes, two Palmers and two Thomases this season.
Pass the numeric id when prompted. `--override` proceeds anyway and records the
override as a note.

## The GW6 Wildcard builder

```bash
./fpl wildcard --shape A
```

Builds a full legal 15 for a Shape from your plan. The bench is bought **first**,
out of a ring-fenced budget (`wildcard_brief.bench_budget_target`, £19.0m).
Buying the XI first makes the greedy spend every last pound on starters and
leave £4.0m fodder on the bench — which is the exact position the Wildcard is
supposed to fix. Locked players (`keep_non_negotiable` plus the Shape's
forwards) are guaranteed a starting place; only a locked keeper may sit, since
the squad carries two and only one can play.

Every squad reports Bench Boost readiness: the share of available minutes each
bench player has actually played, judged against games played so far rather
than a fixed number, so it reads correctly in August.

## Running in the cloud

`.github/workflows/fpl-monitor.yml` runs the checks on GitHub's scheduler, so
nothing depends on this laptop being awake. Push the repo to GitHub and add
three repository secrets:

| Secret | Value |
|---|---|
| `FPL_TEAM_ID` | `1234567` |
| `FPL_LEAGUE_ID` | `987654` |
| `FPL_NTFY_TOPIC` | your private ntfy topic |

Environment variables override `settings.yaml`, so secrets never get committed.
State (`data/`) is carried between runs with the Actions cache — without it
every run looks like a cold start and never alerts.

GitHub's cron is best-effort and can fire several minutes late. The deadline
windows carry enough slack to absorb that, and every alert is deduped, so a
late or repeated run is harmless.

## Scheduling locally

`crontab.example` has the full schedule. Install it with:

```bash
crontab crontab.example
```

| Job | When | Why |
|---|---|---|
| Status | every 2h, 08:00–22:00 | injuries and flags |
| Prices + form | daily 02:00 UK | prices process ~01:30 UK |
| Deadline | hourly | the T-24h / T-3h / T-45m windows decide when to fire |

**Where this runs matters.** Cron on a sleeping laptop misses the 02:00 price
check every night. Either keep the machine awake, or run it on something
always-on.

## Layout

```
config/     settings, watchlist, season plan (chips, shapes, rules, pending squad)
src/fpl/
  api/      client + schema validation that fails loudly
  engine/   status, form, prices, deadlines, fixtures, budget, advice
  notify/   swappable notifier — ntfy, console, email
  jobs/     one entry point per cron job
  webapp/   local server + Gaffer app UI
data/       snapshots for diffing, cache, generated pitch view
tests/      offline rule tests
```

## Notes on the API

The endpoints are undocumented and unofficial — they're what the official site
consumes internally, and they change between seasons. `src/fpl/api/schema.py`
runs before anything reads a payload and fails loudly with the field that
moved. If a job starts erroring after a season rollover, look there first.

`bootstrap-static` is cached 30 minutes. The price job forces a fresh pull,
since a cached copy would hide the overnight change.


## A limitation worth knowing

**The public API cannot see your team for an upcoming deadline.**
`entry/{id}/event/{gw}/picks/` 404s until that gameweek starts, and
`entry/{id}/transfers/` stays empty until then — so a transfer you have already
made is invisible to the tool. Only the auth-gated `my-team/{id}` shows a
pending squad, and this tool deliberately avoids auth.

For your own team, record the upcoming squad under `pending_squad` in
`config/season-plan.yaml` and the tool will use it. **Update it whenever you
make a transfer**, or you will be looking at a stale team. Everything else —
prices, form, fixtures, flags — is always live.

Both the CLI and the app tell you which of the three sources a squad came from.
