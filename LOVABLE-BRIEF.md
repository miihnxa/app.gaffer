# Building the Gaffer frontend in Lovable / Base44

Paste **Prompt 1** to start. Then use the follow-ups one at a time — these tools
degrade badly when you ask for everything at once.

Before you start, you need the API deployed and its URL (see `LAUNCH.md`), and
`GAFFER_CORS_ORIGINS` set to your Lovable preview domain, or every request will
be blocked by the browser.

Real response samples are in `samples/`. **Attach `samples/team.trimmed.json`
to Prompt 2** — giving the model the true shape is the single biggest quality
lever you have.

---

## Prompt 1 — the product and the look

> Build a web app called **Gaffer**. It reads a Fantasy Premier League
> manager's public team and tells them what to fix before the deadline.
>
> **Do not build a backend.** All data comes from an existing REST API at
> `https://API_URL_HERE`. No auth is needed — every endpoint is public and
> read-only.
>
> **Visual direction.** This is a football matchday product, not a SaaS
> dashboard. Take the vernacular from a printed matchday programme and a
> stadium scoreboard:
>
> - **Palette:** deep aubergine near-black ground (`#140419`), raised surfaces
>   in `#210830`, hairlines `#3E1B4F`. One accent only: a bright pitch green
>   `#2CE08C`, used for emphasis and never as a large fill. Semantic colours
>   are separate from the accent — amber `#F2B34E` for doubt, red `#FF7089`
>   for injury. Text `#F6EFF9`, secondary `#C3AECD`, tertiary `#8E779A`.
> - **Type:** `Barlow Condensed` 600/700 for headings, uppercase with tight
>   leading — that condensed face is the scoreboard reference and it carries
>   the personality. `IBM Plex Sans` for body. `IBM Plex Mono` with
>   `font-variant-numeric: tabular-nums` for every number: prices, form,
>   points. Numbers must line up in columns.
> - **Restraint:** no gradients except the pitch itself, no glassmorphism, no
>   rounded-everything, no emoji as section markers, no purple-to-blue hero.
>   Cards get a 1px hairline border and a 12px radius, not a heavy shadow.
>
> **First screen:** a single centred input asking for an FPL team ID, with a
> one-line explainer of where to find it ("the number in the URL of your Points
> page"), and a worked example ID of `1234567`. Nothing else. Once a team is
> loaded, that becomes a small control in a top bar.
>
> Dark theme only. Fully responsive — the pitch has to work on a phone, since
> people check this on the way to work.

## Prompt 2 — the squad screen

> Add the main screen. `GET /api/team/{id}` returns the attached JSON.
>
> Lay the starting XI out **on a football pitch**, the way the official FPL site
> does: goalkeeper at the top, then defenders, midfielders, forwards, each line
> centred and evenly spaced. The pitch is a green gradient (`#1E6B43` to
> `#123F2A`) with faint horizontal mow stripes and a thin white 20%-opacity
> boundary line. Bench sits below a dashed divider.
>
> Each player is a small card showing: name, next fixture as `OPP H/A`, price,
> and form. A 3px bar along the top of the card is green when `status` is
> `"ok"`, amber when `severity` is `"warning"`, red when `"critical"`. Captain
> gets a `C` disc top-right, vice a `V`. Anyone flagged gets a red `!` disc
> top-left.
>
> The fixture difficulty number (`fixtures_gw[].difficulty`, 1–5) is a small
> coloured tag: 1–2 green `#12805A`, 3 grey `#7C7391`, 4 orange `#C1503A`,
> 5 dark red `#8E1B32`.
>
> Beside the pitch, a panel titled **"What to look at"** listing `advice[]`.
> Each item has a coloured severity stripe down its left edge, an uppercase
> severity pill, the `title` in semibold, and `detail` beneath in secondary
> text. When `advice` is empty, say so warmly — "Nothing to change. The squad
> is legal, nobody in the XI is flagged, and the bench order is sound." — not
> an empty state illustration.
>
> **Important:** `squad.note` explains which gameweek the data is from. When
> `squad.stale` is true, show that note as an amber banner above the pitch. Do
> not hide it — it's the difference between the user trusting the app and not.

## Prompt 3 — player detail

> Clicking any player opens a right-hand drawer (bottom sheet on mobile):
>
> - Name, club, position, price, form, total points, minutes, selected %.
> - **Next five fixtures** as a row of chips, each with its difficulty tag.
> - If flagged: a red panel with the `news` text and `chance` to play.
> - **Replacements** — the `replacements[]` array, as a table: player, club,
>   price, cost of the switch (`cost`, red when positive), form gained
>   (`form_delta`, green), their form, next fixture, and 5-gameweek difficulty.
>   Above it, one line: "Higher form, fit, affordable, and legal on the
>   three-per-club rule."
> - If `replacements` is empty, say plainly that nothing in that position
>   clears the rules on the available budget. Do not show an empty table.

## Prompt 4 — the rebuilder

> A second screen, "Rebuild". It calls
> `GET /api/team/{id}/rebuild?lock={playerId}&lock={playerId}&bench=19`.
>
> Above the results: the current squad as a row of toggle chips — clicking one
> locks that player into the rebuild, and locked chips turn green. A slider sets
> the bench budget from £16m to £30m, showing the value live. Then a "Build
> squad" button.
>
> Results render on the same pitch component, with a lock icon on locked
> players. Above it, one line: formation, `cost` spent, `spare` left, and
> `bench_ready` out of 4 — colour that green at 4, amber below.
>
> Below, a small table of `bench_detail`: name, minutes and share played,
> next fixture, and verdict. Then two lines listing `kept` and `out`.
>
> Explain the idea in one sentence near the controls: "It buys the bench first,
> so a Bench Boost is actually worth playing."

## Prompt 5 — leagues and search

> Two more screens.
>
> **Leagues:** `GET /api/league/{id}?team={teamId}`. `team.leagues[]` gives the
> user's leagues to choose from. Render standings: rank, team, manager,
> gameweek points, total, and movement (`moved`, green ▲ / red ▼ / em dash).
> The row where `is_me` is true is highlighted with a green tint. Clicking any
> row loads that manager's squad — that's the best feature in the app, make it
> obviously clickable.
>
> **Players:** `GET /api/search?q=` with a 250ms debounce. Table of name, club,
> position, price, form, points, selected %, 5-gameweek difficulty, and status.

---

## Rules to hold Lovable to

Paste this whenever it drifts:

> - Never invent data. Every number on screen comes from the API response.
> - Never imply the app can make a transfer or change a lineup. It advises only.
> - Never ask the user for an FPL password. Team ID only.
> - Keep all numeric columns in a monospaced face with tabular numerals.
> - The accent green is for emphasis only. Injury red and doubt amber are
>   semantic and must not be restyled to match the accent.

---

## What the API gives you

| Endpoint | Use |
|---|---|
| `GET /api/season` | Next gameweek, deadline, countdown |
| `GET /api/team/{id}` | Squad, fixtures, flags, advice, leagues |
| `GET /api/team/{id}/rebuild` | `lock` (repeatable), `bench`, `budget` |
| `GET /api/league/{id}?team={id}` | Standings with movement |
| `GET /api/search?q=` | Player search |
| `GET /api/ticker?n=5` | Fixture difficulty by club |

Full reference in `API.md`. Samples in `samples/`.

---

## An honest note on the split

The design is worth outsourcing — these tools produce genuinely good-looking
frontends faster than hand-writing CSS.

The *analysis* is not. The transfer guard, the rebuilder that buys the bench
first, the fixture maths and the rules are 3,500 lines with 27 tests, and they
are the reason the app is worth using. Keep them in the API. If Lovable offers
to "add the logic" for you, decline — you'll get a plausible-looking
recommendation engine with no rules behind it, which is exactly the thing this
project was built to avoid.
