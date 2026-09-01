# Gaffer 2.0 — build spec

Companion to `Gaffer.dc.html` (the interactive redesign). Desktop only, local app, no auth.
Brand: primary mark is `brand/gaffer-mark-inverse.svg` (dark tile, lime glyph, on `#F4F1EA`);
the lime-tile variant is for dark surfaces inside the app.
Read the prototype for exact spacing/colour; read this for data, endpoints and structure.

---

## 1. Design tokens

```
--bg          #0E1116   app ground
--rail        #0A0D11   left navigation
--panel       #11161C   cards, tables
--panel-2     #161D25   player cards, inputs on panel
--panel-3     #1B222B   pressed / active nav, secondary buttons
--line        #1C232C   hairline
--line-strong #242C36   card border
--text        #E9EEF4
--muted       #8B97A6
--faint       #5D6875
--ghost       #4C5665
--accent      #C8FF3D   lime — live values, captain, positive delta ONLY
--accent-ink  #0E1116   text on accent
--good        #C8FF3D
--warn        #FFB020
--crit        #FF5C7A
```

FDR scale (background / foreground):
```
2  #1F5F45 / #8BEFC0     3  #2A323C / #B7C2CE
4  #4A2A1E / #FF9A5C     5  #4A1E2A / #FF7D96
```

Type: **Sora** 400/500/600/700 (UI + display), **IBM Plex Mono** 400/500/600 (every number,
price, ID, countdown, fixture code). Body 13px/1.5. Titles 32px, -0.03em. Section labels
11px, uppercase, 0.16em tracking, `--muted`.

Radii: 7px controls, 9–10px inner cards, 12px panels. Borders 1px. No shadows except the
detail drawer (`-30px 0 60px rgba(0,0,0,.45)`).

Accent discipline: lime appears at most three times per screen. Everything else is grey.

---

## 2. Screens

| Route | Screen | Notes |
|---|---|---|
| `/` (no entry saved) | **Entry** | Two-pane. Left: statement + trust notes. Right: entry ID field, load button. |
| `/squad` | **Squad** | Pitch as a tactical grid (not a green pitch), insight stack, mini-league top 4. |
| `/transfers` | **Transfer planner** | Left: squad list, click sets OUT. Right: out→in header, verdict banner, candidate table. |
| `/rebuild` | **Rebuild** | Bench-budget slider drives the build. Keep-chips lock players. Bench Boost readiness table. |
| `/fixtures` | **Fixture ticker** | Only clubs you own. GW3–8 grid + difficulty average. |
| `/league` | **Mini-league** | Full table + standing summary + differential note. |
| `/settings` | **Settings** | Entry ID, team name, five behaviour toggles, cache state. |
| overlay | **Player detail** | Right drawer, 470px. Opens from any player card. Stats grid, next five, last-five form bars, replacement table. |

Persistent chrome: 216px rail (logo, six nav items, deadline block) + 24px page header
(kicker / title / four KPI figures: points, gap to leader, squad value, bank).

---

## 3. Data model

```ts
type Position = 'GK' | 'DEF' | 'MID' | 'FWD';

interface Club   { id: number; name: string; short: string; strength: number }
interface Fixture{ id: number; event: number; teamH: number; teamA: number;
                   difficultyH: number; difficultyA: number; kickoff: string }

interface Player {
  id: number; firstName: string; webName: string;
  clubId: number; position: Position;
  price: number;           // now_cost / 10
  form: number;            // string in API — parseFloat
  totalPoints: number; pointsPerGame: number; minutes: number;
  selectedByPercent: number;
  status: 'a'|'d'|'i'|'s'|'u'; chanceOfPlaying: number | null;
  history: { event: number; points: number; minutes: number }[];
}

interface Pick   { playerId: number; slot: number /*1-15*/; isCaptain: boolean;
                   isVice: boolean; multiplier: number }

interface Squad  { event: number; source: 'api' | 'manual'; picks: Pick[];
                   bank: number; value: number; freeTransfers: number; chip: string | null }

interface Entry  { id: number; teamName: string; managerName: string; region: string;
                   overallPoints: number; overallRank: number; leagues: League[] }

interface League { id: number; name: string; standings: {
                     rank: number; entryId: number; entryName: string;
                     playerName: string; eventTotal: number; total: number }[] }

interface Insight{ id: string; kind: 'injury'|'clash'|'price'|'hit'|'info';
                   severity: 'crit'|'warn'|'info'; event: number;
                   title: string; body: string; playerIds: number[] }
```

---

## 4. API (public FPL, no auth)

| Purpose | Endpoint | Cache |
|---|---|---|
| Players, clubs, events | `GET /api/bootstrap-static/` | 15 min (5 min on deadline day) |
| Fixtures | `GET /api/fixtures/` | 1 h |
| Entry meta | `GET /api/entry/{id}/` | 1 h |
| Entry history | `GET /api/entry/{id}/history/` | 1 h |
| Picks for a **started** GW | `GET /api/entry/{id}/event/{gw}/picks/` | until GW ends |
| Mini-league | `GET /api/leagues-classic/{id}/standings/` | 15 min |
| Player detail | `GET /api/element-summary/{playerId}/` | 1 h |

Notes for the implementation:
- Requires a proxy — the FPL API sends no CORS headers. Run fetches in the main/server
  process, never the renderer.
- **Picks for the upcoming gameweek are not public.** Before a GW starts, load the previous
  GW's picks and let the user amend them by hand; store as `Squad.source = 'manual'` and
  label it in the UI. This is the one place the app must be explicit about where data
  came from.
- Cache to a local store (SQLite or a JSON file). Every screen renders from cache first,
  then reconciles.
- Deadline countdown comes from `events[].deadline_time` on bootstrap; tick client-side.

---

## 5. Derived logic

- **Form delta** — `candidate.form − outgoing.form`; positive shown lime.
- **Transfer cost** — `candidate.price − outgoing.price`; must be ≤ bank + outgoing price.
- **Hit** — `max(0, transfersMade − freeTransfers) × 4`. Warn banner at ≥ 4.
- **Legality** — max 3 players per club; formation valid (1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD).
- **Clash insight** — two owned players whose clubs meet in the same fixture; severity
  `warn` when one is a defender/GK.
- **Injury insight** — `status !== 'a'` or `chanceOfPlaying < 100`; severity `crit` if the
  player is in the starting XI.
- **Rebuild** — spend the bench budget first (4 players, minutes-per-start ≥ 60% preferred),
  then optimise the XI on remaining funds against locked keeps.
- **Bench Boost readiness** — bench minutes ÷ available minutes; ≥ 80% "nailed",
  55–80% "rotation risk", below "passenger".
- **Ticker average** — mean difficulty over the next six fixtures; ≤ 2.8 lime, ≥ 3.8 crit.

---

## 6. Component list

```
AppShell        rail + header + <slot>
NavRail         nav items, DeadlineBlock
DeadlineBlock   live countdown, progress hairline
PageHeader      kicker / title / subtitle / KpiStrip
KpiStrip        4 × mono figure + caption
PitchBoard      grid-lined board, rows by position, BenchStrip
PlayerCard      name, badge (C/V/!), opponent + FdrChip, price, form
FdrChip         difficulty 2–5
InsightCard     left-border tone, kind label, title, body
StandingsTable  compact (top 4) and full variants
TransferHeader  out → in, cost / form delta / hit, VerdictBanner
CandidateTable  selectable rows
BenchBudget     range + live label + build action
KeepChip        toggle lock
TickerGrid      club rows × 6 GW cells + average
PlayerDrawer    stats grid, NextFive, FormBars, swap table
ToggleRow       label, description, switch
```

State: `entryId`, `teamName`, `screen`, `selectedPlayerId`, `transferOut`, `transferInIdx`,
`benchBudget`, `lockedPlayerIds`, `settings.toggles[]`. All persisted locally except
`selectedPlayerId`.

---

## 7. Rules the redesign encodes

1. The deadline is a fixed instrument in the rail, always visible, always live.
2. The pitch is a data board, not a decoration — no green gradient, no shirt art.
3. Every number is monospaced and right-aligned in tables so columns scan vertically.
4. Colour carries one meaning each: lime = good/live, amber = doubt, red = injury/cost.
5. The app never writes to FPL. Every recommendation ends with the user typing it in.
