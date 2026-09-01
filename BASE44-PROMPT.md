# Base44 / Lovable — copy-paste prompts

Replace `API_URL_HERE` with your deployed API URL everywhere before pasting.
Paste **one prompt at a time**, waiting for each to finish. Pasting all five at
once is the single most common way to get a mediocre result out of these tools.

Attach `samples/team.trimmed.json` when you paste PROMPT 2.

---

## PROMPT 1 — foundation

```
Build a web app called Gaffer. It reads a Fantasy Premier League manager's
public team and tells them what to fix before the deadline.

DO NOT build a backend, database, or auth. All data comes from an existing
REST API at API_URL_HERE. Every endpoint is public, read-only, and needs no
API key. Use plain fetch().

VISUAL DIRECTION
This is a football matchday product, not a SaaS dashboard. The reference is a
printed matchday programme and a stadium scoreboard.

Colours — dark theme only:
  ground / page background  #140419   (deep aubergine, near black)
  raised surface            #210830
  secondary surface         #2A0F3A
  hairline borders          #3E1B4F
  primary text              #F6EFF9
  secondary text            #C3AECD
  tertiary text             #8E779A
  accent (one only)         #2CE08C   bright pitch green
  warning / doubt           #F2B34E
  critical / injured        #FF7089
  pitch gradient            #1E6B43 to #123F2A

The accent is for emphasis only — never a large fill, never a gradient hero.
Warning amber and critical red are semantic and must never be restyled to
match the accent.

Typography — load from Google Fonts:
  Headings: Barlow Condensed, weight 600/700, UPPERCASE, tight line-height
            (0.95). This condensed face carries the personality — use it big.
  Body:     IBM Plex Sans, 400/500/600
  Numbers:  IBM Plex Mono with font-variant-numeric: tabular-nums.
            EVERY number uses it — prices, form, points, ranks — so columns
            of digits line up exactly.

Do NOT use: gradients other than the pitch, glassmorphism, blurred glows,
emoji as section markers, drop shadows heavier than a 1px hairline border,
rounded-full on everything, or a purple-to-blue hero. Cards are a 1px
#3E1B4F border with a 12px radius on #210830. Restraint is the brief.

FIRST SCREEN
A single centred input asking for an FPL team ID. Above it the app name in
Barlow Condensed. Below the input, one line of help: "The number in the URL of
your Points page on the FPL site." Offer 1234567 as a clickable example.
Nothing else on this screen.

Once a team loads, that input becomes a small control in a top bar showing the
team name, manager name and team ID, and the screen switches to the squad view.

Fully responsive. Most people will open this on a phone the morning of a
deadline, so the phone layout is not an afterthought.
```

---

## PROMPT 2 — the squad screen (attach `samples/team.trimmed.json`)

```
Add the main squad screen. GET API_URL_HERE/api/team/{teamId} returns the
attached JSON. Build against that exact shape.

THE PITCH
Lay the starting XI out on a football pitch, like the official FPL site:
goalkeeper top, then defenders, midfielders, forwards. Each line centred and
evenly spaced. squad.xi is already ordered; group by the "pos" field
(GKP, DEF, MID, FWD).

The pitch is a vertical gradient #1E6B43 to #123F2A, with faint horizontal mow
stripes (alternating 4% white / 3% black bands) and a 2px white-at-20% inset
boundary line. squad.bench sits below a dashed divider labelled BENCH.

PLAYER CARDS
Each player is a small card (about 92px wide) on #210830 showing:
  - name (semibold, truncate with ellipsis)
  - next fixture: fixtures_gw[0].opponent + " H" or " A" from the "home" bool
  - price as £X.Xm, and form
A 3px bar across the top of the card, coloured by "severity":
  "ok" -> #2CE08C, "warning" -> #F2B34E, "critical" -> #FF7089
Badges: is_captain -> a "C" disc top-right; is_vice -> "V"; status not "ok" ->
a red "!" disc top-LEFT.

FIXTURE DIFFICULTY
fixtures_gw[].difficulty is 1-5. Render as a small rounded tag:
  1-2 -> #12805A, 3 -> #7C7391, 4 -> #C1503A, 5 -> #8E1B32, white text.
If fixtures_gw is empty the team has no fixture: show "BLANK" in #FF7089.

THE ADVICE PANEL
Beside the pitch (below it on mobile), a card titled "What to look at" listing
advice[]. Each item: a 4px severity-coloured stripe down the left edge, an
uppercase severity pill, "title" in semibold, "detail" beneath in secondary
text. Sort critical first, then warning, then info.

When advice[] is empty, show this exact sentence instead of an empty state
graphic: "Nothing to change. The squad is legal, nobody in the XI is flagged,
and the bench order is sound."

THE STALENESS BANNER — IMPORTANT
squad.note explains which gameweek the data is from. When squad.stale is true,
show squad.note as an amber banner (#F2B34E text on a dark amber tint) directly
above the pitch. Never hide or collapse it. The public FPL data cannot show a
squad before its gameweek starts, and a user who doesn't know that will think
the app is broken or, worse, trust a stale lineup.

FULL SQUAD TABLE
Below the pitch, a table of all 15: player, club, position, price, form, points,
selected %, next fixture with its difficulty tag, 5-gameweek difficulty (fdr5),
and status. Bench rows are dimmed and prefixed "BEN". All numeric columns
right-aligned in IBM Plex Mono. The table scrolls horizontally inside its own
container — the page body must never scroll sideways.
```

---

## PROMPT 3 — player detail

```
Clicking any player card or table row opens a detail panel: a right-hand drawer
on desktop (max 560px), a bottom sheet on mobile. Close on Escape, on a
backdrop click, and via a visible Close button.

Contents:
  - Eyebrow: club, position, and "bench" if benched
  - Name as a large Barlow Condensed heading
  - A grid of stat tiles: price, form, points, points per game (ppg), minutes,
    selected %. Each tile is a bordered box, label small and uppercase in
    tertiary text, value in IBM Plex Mono.
  - "Next five" — fixtures_next[] as a row of chips: "GW{gw} {opponent} (H/A)"
    plus the difficulty tag.
  - If status is not "ok": a panel tinted with #FF7089 showing the "news" text
    and "{chance}% chance to play".
  - REPLACEMENTS: the replacements[] array as a table with columns
    player, club, price, cost, form gained, form, next fixture, 5GW difficulty.
    Map: "cost" is the price difference — show with a + sign and colour it
    #FF7089 when positive. "form_delta" is the form gained — always positive
    here, colour it #2CE08C with a + sign.
    Caption above the table: "Higher form, fit, affordable, and legal on the
    three-per-club rule."

  If replacements[] is empty, do NOT render an empty table. Show this instead:
  "Nothing in this position clears the rules on the available budget — every
  candidate is either lower form, flagged, unaffordable, or would break the
  three-per-club limit."
```

---

## PROMPT 4 — the rebuilder

```
Add a second screen called "Rebuild", reachable from a left sidebar nav
(Squad, Rebuild, Leagues, Players).

It calls:
GET API_URL_HERE/api/team/{teamId}/rebuild?lock={id}&lock={id}&bench=19
"lock" repeats once per locked player. "bench" is a float.

CONTROLS, above the results:
  - The current 15 as toggle chips showing name and price. Clicking one locks
    that player into the rebuild; locked chips get a #2CE08C border and text.
  - A slider for bench budget, 16 to 30, step 0.5, showing the live value as
    "£19.0m".
  - A "Build squad" button.
  - One line of explanation beside the controls: "It buys the bench first, so a
    Bench Boost is actually worth playing."

RESULTS:
Reuse the exact pitch component from the squad screen. Locked players get a
small green lock badge. Above the pitch, one summary line: the formation, then
"£{cost}m spent, £{spare}m spare", then "Bench Boost ready {bench_ready}/4" —
coloured #2CE08C when bench_ready is 4, #F2B34E below that.

Below, a table of bench_detail[]: name and club, minutes with the share played
as a percentage, next fixture with difficulty tag, and verdict. Colour the
verdict green when "ok" is true, red when false.

Then two lines: "Keeps" listing kept[], and "Sells" listing out[].

While the request runs, show a loading state — this call takes a second or two
because it is solving a real constraint problem, not returning a cached list.
```

---

## PROMPT 5 — leagues and player search

```
Two more screens on the same sidebar nav.

LEAGUES
The team response includes leagues[] — the manager's classic leagues, each with
id, name and rank. Show them as a selectable list; picking one calls
GET API_URL_HERE/api/league/{leagueId}?team={teamId}

Render standings as a table: rank, team name, manager, gameweek points, total
points, and movement. Movement comes from "moved": positive is a green "▲n",
negative a red "▼n", zero an em dash.

The row where is_me is true gets a subtle #2CE08C tint and semibold text.

Every row is clickable and loads that manager's squad in the Squad screen.
Make that obviously clickable — a cursor change, a hover state, and a caption
under the table reading "Click any rival to open their squad." It is the best
feature in the app and it is invisible unless you signal it.

PLAYERS
A search box calling GET API_URL_HERE/api/search?q={query}, debounced 250ms,
minimum 2 characters. Results as a table: name, club, position, price, form,
points, selected %, 5GW difficulty, status. Flagged players show their status
in #FF7089; fit players show an em dash.
```

---

## Correction prompt — paste this whenever it drifts

```
Corrections, keep all of these true:
- Never invent or placeholder data. Every value on screen comes from the API
  response. If a field is missing, show an em dash, not a made-up number.
- Never imply the app can make a transfer or change a lineup. It advises only.
- Never ask for an FPL password, email, or login. Team ID only.
- All numeric columns use IBM Plex Mono with tabular-nums and are right-aligned.
- #2CE08C is emphasis only. #F2B34E means doubt and #FF7089 means injured —
  these are semantic and must not be restyled.
- The staleness banner from squad.note must stay visible when squad.stale is
  true.
- Wide tables scroll inside their own container. The page body never scrolls
  horizontally.
```

---

## Endpoint reference

| Endpoint | Returns |
|---|---|
| `GET /api/season` | `next_gw`, `deadline_local`, `countdown`, `chip_expiry` |
| `GET /api/team/{id}` | `entry`, `squad` (xi/bench), `advice`, `leagues` |
| `GET /api/team/{id}/rebuild` | `xi`, `bench`, `cost`, `spare`, `bench_ready`, `bench_detail`, `kept`, `out` |
| `GET /api/league/{id}?team={id}` | `name`, `rows[]` with `rank`, `total`, `moved`, `is_me` |
| `GET /api/search?q=` | Player list |
| `GET /api/ticker?n=5` | Fixture difficulty by club |

Errors are `{"error": "...", "code": "..."}`. Handle 404 (`team_not_found`) by
telling the user the ID wasn't found and where to get the right one, and 429
(`rate_limited`) by asking them to wait a moment.

Before any of this works, set `GAFFER_CORS_ORIGINS` on the API to your Base44
or Lovable preview domain — otherwise the browser blocks every request and the
app will look broken for reasons the tool cannot diagnose.
