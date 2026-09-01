# Handoff: Gaffer 2.0 — FPL matchday assistant

## Overview

Gaffer is a local desktop app that reads a public Fantasy Premier League entry and tells the
manager, before each deadline, which move is worth making. It watches the
deadline, flags injuries and fixture clashes, models transfers, and rebuilds a squad on a
Wildcard. It never signs in and never changes a team — every recommendation ends with the
user typing it into FPL themselves.

This bundle is a full visual redesign of an existing working app. The logic already exists;
what is new here is the interface.

## About the design files

`design/Gaffer.dc.html` and `design/Gaffer Logo.dc.html` are **design references written in
HTML** — prototypes showing intended look and behaviour, not production code to lift. Open
them in a browser (keep `support.js` beside them) and click through.

The task is to **recreate these screens in the app's existing environment**, using its
established patterns, component library and state management. If the app has no UI framework
yet, pick the most appropriate one for a local desktop build (Electron or Tauri with React is
the natural fit given the FPL API needs a proxy process) and implement there.

Do not port the prototype's internals. It uses a single-component pattern with inline styles
purely so it could stream into a design tool. Real implementation should use the component
list below.

## Fidelity

**High-fidelity.** Colours, typography, spacing, border radii and interaction states are
final. Recreate pixel-for-pixel using the codebase's own primitives. The only placeholder
content is the data itself: player names, prices, forms, fixtures, league standings and the
per-player form bars are plausible samples, not real API responses.

## Design tokens

### Colour

| Token | Hex | Use |
|---|---|---|
| `bg` | `#0E1116` | app ground |
| `rail` | `#0A0D11` | left navigation column |
| `panel` | `#11161C` | cards, tables, drawer |
| `panel-2` | `#161D25` | player cards, inputs sitting on a panel |
| `panel-3` | `#1B222B` | active nav item, secondary buttons, selected table row |
| `line` | `#1C232C` | hairline dividers |
| `line-strong` | `#242C36` | card and input borders |
| `text` | `#E9EEF4` | primary |
| `muted` | `#8B97A6` | secondary copy, section labels |
| `faint` | `#5D6875` | captions, table meta |
| `ghost` | `#4C5665` | footnotes |
| `dim` | `#3E4855` | position labels on the pitch |
| `accent` | `#C8FF3D` | lime: live values, captain, positive delta |
| `accent-ink` | `#0E1116` | text on lime |
| `accent-dim` | `#2E4410` | filled toggle track, low form bar |
| `accent-border` | `#3D5216` | border on a lime-positive surface |
| `accent-wash` | `#15200E` | background of your own league row, positive verdict |
| `warn` | `#FFB020` | doubt, rotation risk, low form |
| `warn-wash` | `#221A0B` / border `#4A3A12` | marginal verdict banner |
| `crit` | `#FF5C7A` | injury, points cost, gap to leader |
| `crit-border` | `#3A2028` | border on a flagged player card |
| `light` | `#F4F1EA` | logo-on-light only |

Fixture difficulty (background / foreground):

| FDR | bg | fg |
|---|---|---|
| 2 | `#1F5F45` | `#8BEFC0` |
| 3 | `#2A323C` | `#B7C2CE` |
| 4 | `#4A2A1E` | `#FF9A5C` |
| 5 | `#4A1E2A` | `#FF7D96` |

**Accent discipline:** lime appears at most three times per screen. Everything else is grey.
Each colour carries exactly one meaning — lime good/live, amber doubt, red injury or cost.

### Typography

- **Sora** 400/500/600/700 — all UI and display text.
- **IBM Plex Mono** 400/500/600 — every number: prices, form, points, IDs, countdown,
  fixture codes, table figures, ranks.

| Role | Size | Weight | Tracking | Colour |
|---|---|---|---|---|
| Page title | 32px / 1 | 600 | -0.03em | text |
| Entry hero | 58px / 1.02 | 600 | -0.035em | text |
| Drawer name | 34px / 1.05 | 600 | -0.03em | text |
| Card / KPI figure (mono) | 19–25px | 600 | -0.02em | varies |
| Section label | 11px | 600 | 0.16em, uppercase | muted |
| Kicker | 10px | 600 | 0.18em, uppercase | accent |
| Micro label | 9–9.5px | 600 | 0.14em, uppercase | faint |
| Body | 13px / 1.5 | 400 | — | text |
| Secondary body | 12–12.5px / 1.55 | 400 | — | muted |
| Footnote | 11–11.5px / 1.55 | 400 | — | ghost |

### Spacing, radius, elevation

- Page padding 22–30px. Panel padding 16–20px. Card padding 8–13px.
- Grid gaps: 20–22px between major columns, 8–9px inside a card group, 6–7px between chips.
- Radii: 7px controls and inputs, 8–10px inner cards and chips, 12–14px panels, 22px on the
  app icon (96-unit viewBox), 99px pills.
- Borders 1px throughout. **No shadows** anywhere except the player drawer:
  `-30px 0 60px rgba(0,0,0,.45)`.
- Scrollbars 8px, thumb `#242C36`, radius 4px.

---

## Screens

Canvas is **1440 × 900, desktop only**. Persistent chrome on every screen except Entry:
a 216px navigation rail and a page header.

### 1. Entry

Shown when no entry ID is saved.

- Two equal columns, divider `1px #1C232C`.
- **Left** (`#0E1116`, padding 64px 60px, `space-between`): logo lockup at top — 26px lime
  rounded square (radius 6px) with `G` in 15px/700 `#0E1116`, plus "Gaffer" 600.
  Middle block: kicker "Matchday assistant"; h1 58px/1.02, -0.035em, max-width 12ch, copy
  *"Know your best move before the deadline."*; paragraph 15px/1.6 muted,
  max-width 44ch. Bottom row: three 12px `#5D6875` items — "Local · no account",
  "Public FPL data", "v2.0".
- **Right** (`#11161C`, vertically centred): section label "Load a team". Field labelled
  "Entry ID" — background `#0E1116`, border `1px #242C36` with a `2px #C8FF3D` bottom
  border, radius 8px, padding 16px 18px, mono 22px, 0.06em. Helper text 12px showing
  `fantasy.premierleague.com/entry/1234567/history` with the ID in lime.
  Primary button: lime fill, `#0E1116` text, radius 8px, padding 15px 24px, 14px/600,
  label "Load squad" left with a mono `→` right; hover `#DCFF7A`.
  Below a `1px #1C232C` rule, three numbered trust notes (mono `01`–`03` in faint, copy in
  muted 12.5px): public endpoints only, pre-gameweek squads typed by hand, everything cached
  locally.

### 2. Navigation rail — persistent, 216px

Background `#0A0D11`, right border `1px #1C232C`, padding 20px 12px 14px, `gap: 22px`.

- Logo lockup: 26px lime square + "Gaffer" 14px/600 + mono 10px `entry {id}` in faint.
- Six items, `gap: 1px`, each 9px 10px, radius 7px, 13px/500, 15px stroke-1.7 icon with
  11px gap: **Squad** (grid), **Transfers** (two-way arrow), **Rebuild** (bars),
  **Fixtures** (calendar), **League** (podium), **Settings** (gear).
  Active: background `#1B222B`, text `#E9EEF4`. Inactive: transparent, `#8B97A6`.
- Pinned to the bottom, the **deadline block**: panel card, radius 10px. Row of micro label
  "Deadline" and mono `GW3` in lime. Countdown mono 25px/600 lime, -0.03em, format
  `1d 04:12:33`, ticking every second. Mono 11px date line in faint. A 3px progress rail
  `#1C232C` with a lime fill (proportion of the gameweek window elapsed).
- Below it, 10.5px `#4C5665`: "Advises only. Never signs in, never changes a team."

### 3. Page header — persistent

Padding 24px 30px 18px, bottom border `1px #1C232C`, `align-items: flex-end`.

- Left: kicker (10px lime uppercase) / title (32px) / subtitle (12px faint).
- Right: four right-aligned KPIs, `gap: 30px`. Each is a mono 21px/600 figure over a 9.5px
  uppercase caption in faint: **Points** `146`, **To leader** `−4` (crit),
  **Squad** `£100.1`, **Bank** `£0.0`.

Per-screen header copy:

| Screen | Kicker | Title | Subtitle |
|---|---|---|---|
| Squad | `{league name} · 2nd of 7` | team name | `{manager} · {region} · ID {id}` |
| Transfers | Gameweek 3 · 1 free transfer | Transfer planner | Model a move before you make it. Nothing is submitted for you. |
| Rebuild | Gameweek 6 · Wildcard | Rebuild the squad | Bench first, then the XI — the order that stops four £4.0m passengers. |
| Fixtures | Gameweek 3 – 8 | Fixture ticker | Difficulty for every club you currently own. |
| League | `{league name}` | Mini-league | 7 teams · updated after every gameweek. |
| Settings | Local install | Settings | Stored on this machine. Nothing is sent anywhere. |

### 4. Squad

Two columns, `minmax(0,1.55fr) minmax(0,1fr)`, gap 22px, top-aligned.

**Pitch board** (left). Deliberately *not* a green pitch — a tactics board.
Panel `#10151B`, border `1px #1C232C`, radius 12px, padding 18px 16px 14px, with a 34px
graph-paper grid drawn from two `linear-gradient(#161D25 1px, transparent 1px)` layers.
Above it: "Gameweek 3 · 3-4-3" section label, and right-aligned 11.5px faint note
"Recorded by hand — pre-deadline squads aren't public".

Four rows (GK / DEF / MID / FWD): a 26px mono row label in `#3E4855`, then the row's cards
centred with `gap: 8px`. Then a `1px dashed #262E38` rule and a **BEN** row of four cards at
`opacity: .85`, background `#12171D`.

**PlayerCard** — 110px wide, `#161D25`, border `1px #242C36`, radius 9px, padding 9px 9px 8px,
cursor pointer, hover border `#3B4757`:
- Top row: name 12.5px/600, -0.01em, ellipsis; then a 15px square badge, radius 4px, mono
  9px/600 — captain `C` (lime bg, dark text, card border `#3D5216`), vice `V`
  (`#2A323C` bg, `#B7C2CE`), flagged `!` (`#4A1E2A` bg, crit text, card border `#3A2028`).
- Second row: mono 10px opponent code (`EVE A`) + FdrChip.
- Third row above a `1px #1C232C` rule: mono 10px price in faint, form right-aligned and
  coloured — `≥7` lime, `≥3` text, else amber.

**FdrChip** — mono 9px/600, radius 3px, padding 0 4px, colours from the FDR table.
Label reads `GW5 · 3` on the ticker, bare difficulty when the `showFdrChips` setting is off.

**Right column**, two stacked blocks:
- *What to look at* — section label with a mono item count on the right. Cards: panel
  background, `1px #1C232C` border with a `2px` left border in the severity tone, radius
  `0 9px 9px 0`, padding 12px 14px. Inside: 9px uppercase kind label in the tone + mono 10px
  gameweek in `#3E4855`; title 13.5px/600; body 12px/1.5 muted. Sample content —
  crit "Hughes is flagged — 25% chance"; warn "Gabriel and João Pedro face each other";
  info "Mitchell and Gonzalo face each other".
- *Mini-league* — section label with a lime "All 7 →" link. Table, radius 10px, rows
  `22px 1fr auto auto`, padding 10px 14px, 12.5px, divider `1px #1A212A`. The user's own row
  gets background `#15200E` and lime text.

### 5. Transfer planner

Two columns, `300px minmax(0,1fr)`, gap 22px.

- **Left — "Pick who leaves".** All 15 players, rows `30px 1fr auto auto`, padding 9px 13px,
  12.5px. Mono 9.5px position, name 500, mono price, mono form (lime ≥7, muted ≥3, else
  amber). Selected row: background `#1B222B`, name lime. Clicking sets the outgoing player
  and resets the candidate selection to the top row.
- **Right, top — TransferHeader.** Panel, radius 12px, padding 18px 20px. Out block (micro
  label crit) → mono 22px `→` in `#3E4855` → In block (micro label lime). Each: name 22px/600,
  -0.02em; mono 12px meta `{club} · {pos} · £{price} · form {form}`. Then a `1px` left
  divider and three right-aligned figures, mono 19px/600: **Cost** (`+£1.4` crit if
  positive, lime if a downgrade frees money), **Form Δ** (`+9.5` lime), **Hit** (`0`).
  Below, the **VerdictBanner** — radius 8px, padding 11px 14px, 12.5px/1.5.
  Positive: bg `#15200E`, border `#3D5216`, text `#D8FF8C`.
  Marginal: bg `#221A0B`, border `#4A3A12`, text `#FFD98A`.
  Threshold in the prototype is a form gain of 7.0.
- **Right, bottom — CandidateTable.** Section label "Replacements worth the transfer".
  Header row 9px uppercase faint; columns `1.4fr .7fr .8fr .8fr .9fr 1.1fr` —
  Player / Club / Price / Cost / Form + / Next. Rows padding 11px 14px, 12.5px, selected row
  `#1B222B`. Name 600, club mono muted, figures mono, gain lime 600. Footnote 11.5px ghost:
  higher form, fit, affordable, legal on three-per-club; nothing applied automatically.

### 6. Rebuild (Wildcard)

Vertical stack, gap 18px.

- **Control bar** — panel, radius 12px, padding 16px 20px, flex with gap 26px. "Bench budget"
  label, a range input (`min 12, max 26, step 0.5`, 190px, `accent-color: #C8FF3D`), the live
  value in mono 14px/600 lime (`£19.0m`, min-width 56px). A 22px vertical divider, then mono
  12px faint context "Budget £100.1m · 4-4-2 · £0.0m spare". Right-aligned lime
  **Build squad** button.
- **Explanatory paragraph** 13px muted, max-width 78ch: it buys the bench first, because
  building the XI first leaves four £4.0m players who never start.
- Two columns, `minmax(0,1.5fr) minmax(0,1fr)`, gap 20px:
  - *Proposed squad* — same graph-paper board, 98px cards showing name, mono price, lime form.
    Locked keeps get border `#3D5216`. Dashed rule then the bench row (`#12171D`); a bench
    player under 60% of available minutes shows amber form and border `#4A3A12`.
  - *Keep — click to lock* — 15 pill chips, radius 99px, padding 5px 12px, 12px, label
    `{name} £{price}`. Locked: bg `#15200E`, border `#3D5216`, lime text. Unlocked:
    `#12171D`, `#242C36`, muted.
  - *Bench Boost readiness* — table, rows `1.3fr .9fr .9fr`, padding 10px 14px. Name 600 with
    the club in mono 10.5px faint; mono minutes and share (`180′ 100%`); status —
    "nailed" lime at ≥80%, "rotation risk" amber 55–80%, "passenger" below.

### 7. Fixture ticker

Section label "Next six — clubs you own", plus a right-aligned legend: "Easy", four 14×8px
radius-2 swatches in FDR order, "Hard".

Table, radius 12px. Columns `150px repeat(6,1fr) 74px`, gap 1px, header padding 10px 16px,
rows padding 7px 16px, dividers `1px #1A212A`. First cell stacks the club code (12.5px/600)
over the owned players (10px `#4C5665`, ellipsis). Each of six cells: radius 5px, padding
6px 8px, mono 11px, FDR colours, `margin-right: 5px`. Last column: mono 13px/600 six-fixture
average — lime at ≤2.8, crit at ≥3.8, else muted.

### 8. Mini-league

Two columns, `minmax(0,1fr) 320px`, gap 22px.

- **Table** — columns `34px 1fr 90px 80px 80px 90px`: # / Team / Manager / GW / Total / Gap.
  Header 9px uppercase faint, padding 11px 18px. Rows padding 13px 18px, team 14px/600,
  manager 11.5px faint ellipsis, figures mono 13px right-aligned, gap `−4` (`—` for the
  leader). Own row: bg `#15200E`, lime text. Rows are clickable — opens a rival's squad once
  their gameweek has started; the footnote says so in 11.5px ghost.
- **Side column** — a standing card (league name micro label, "2nd *of 7*" at 26px/600 with
  the total in faint 16px, a `1px` rule, then three label/value rows: best GW rank lime,
  points off top crit, points to third) and a differential note card with a `2px` lime left
  border and radius `0 12px 12px 0`.

### 9. Settings

Single column, max-width 720px, gap 26px.

- *Team* — panel, two fields side by side: Entry ID (mono 14px) and Team name. Labels 11.5px
  faint, inputs `#0E1116` / `1px #242C36` / radius 7px / padding 10px 12px.
- *Behaviour* — five ToggleRows, padding 15px 18px, divider `1px #1A212A`. Label 13.5px/500,
  description 11.5px faint. Switch: 42px × 24px, radius 99px, 18px knob, `left` transitions
  over 150ms (2px → 20px). On: track `#2E4410`, border `#3D5216`, lime knob. Off: `#161D25`,
  `#242C36`, `#5D6875` knob. The five: warn before a points hit (≥4); watch price changes;
  auto-refresh on deadline day (every 15 min Friday); flag fixture clashes; sound on alerts.
- *Data* — cache line "Bootstrap cached **6 min ago** · 782 players, 20 clubs, 380 fixtures",
  a secondary **Refresh now** button (`#1B222B` / `1px #242C36`), and a destructive
  **Clear & sign out** (transparent, border `#3A2028`, crit text).

### 10. Player drawer — overlay

Opens from any player card. Scrim `rgba(6,8,11,.6)` over the full frame, click to dismiss.
Panel: right-anchored, 470px, full height, `#11161C`, left border `1px #242C36`, padding
26px 26px 20px, scrollable, shadow `-30px 0 60px rgba(0,0,0,.45)`.

- Header: micro label `{club} · {pos}` (append "· flagged" when applicable), name 34px/600,
  and a secondary **Close** button.
- Stats grid, 3 × 2, gap 9px. Each: `#0E1116`, border `1px #1C232C`, radius 9px, padding
  11px 13px — 9px uppercase label over a mono 18px/600 value. Price, Form (tone-coloured),
  Points, Per game, Minutes, Selected.
- *Next five* — five equal cards, radius 8px, padding 9px 8px, centred: mono 9px gameweek,
  11.5px/600 opponent, FdrChip full-width.
- *Form, last five* — 78px bar chart inside a bordered panel. Each column: mono 10px points
  above a bar, radius `3px 3px 0 0`, height `max(4px, points × 7px)`; bar colour lime at ≥6,
  `#2E4410` at ≥2, `#242C36` for a blank.
- *Replacements worth the transfer* — compact 4-column table, gain in lime.
- Footnote: "Nothing here is applied automatically. Gaffer advises; you make the change in FPL."

---

## Interactions & behaviour

- **Navigation** — rail selects a screen and clears any open drawer. No page transitions.
- **Entry** — "Load squad" validates the ID is numeric, fetches entry meta, and lands on
  Squad. Persist the ID; skip Entry on subsequent launches.
- **Player card click** → drawer. Scrim click or Close → dismiss. `Esc` should also dismiss.
- **Transfer planner** — selecting an outgoing player recomputes the candidate pool for that
  position and resets the selection to the strongest option. Selecting a candidate updates
  cost, form delta, hit and the verdict banner together.
- **Rebuild** — the bench slider re-solves the squad; keep-chips pin players through the
  re-solve. Debounce the solve ~120ms while dragging.
- **Hover** — nav items lift to `#1B222B`; player cards move their border to `#3B4757`;
  the primary button to `#DCFF7A`. Transitions 120–150ms ease.
- **Countdown** — ticks every second from `events[].deadline_time`; no network per tick.
- **Loading** — render from cache immediately, then reconcile. Show a mono skeleton figure
  (`—`) rather than a spinner in KPI slots.
- **Errors** — a network failure keeps the cached view and adds an info Insight card naming
  the stale timestamp. Never blank a screen.
- **Not responsive.** Fixed 1440 × 900 minimum; the content column scrolls, the rail does not.

## State

```
entryId, teamName            persisted
screen                       'entry' | 'squad' | 'transfers' | 'rebuild' | 'fixtures' | 'league' | 'settings'
selectedPlayerId             transient — drawer
transferOut, transferInIdx   transient
benchBudget                  persisted, default 19.0 (£m)
lockedPlayerIds              persisted
settings.toggles[5]          persisted, defaults [on, on, off, on, off]
showFdrChips                 persisted, default on
```

Data-fetching requirements, endpoints, cache windows, the CORS proxy note, the
pre-deadline manual-squad rule, and all derived logic (form delta, hit, legality, clash and
injury insights, rebuild ordering, Bench Boost readiness, ticker averages) are specified in
**`BUILD-SPEC.md`** in this folder. Read it alongside this README.

## Component list

```
AppShell        rail + header + content slot
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

## Assets

Vector only — nothing raster, no external image dependency.

| File | Use |
|---|---|
| `brand/gaffer-mark-inverse.svg` | **primary** — dark `#0E1116` tile, lime glyph, sits on `#F4F1EA`. App icon, marketing, docs, favicon. |
| `brand/gaffer-mark.svg` | dark-UI variant — lime tile, dark glyph. Used inside the app itself (Entry pane, nav rail) where the primary would disappear. |
| `brand/gaffer-mark-16.svg` | 16–20px variant: heavier stroke, arrowhead removed |
| `brand/gaffer-lockup.svg` | horizontal mark + "Gaffer" wordmark |

The mark is a geometric `G` whose terminal doubles as a substitution arrow. Construction, on
a 96 × 96 viewBox: tile radius 22; strokes 9 units, round caps and joins; the arc runs from
(62.6, 32.1) with radius 22 to (70, 48); the crossbar runs (70, 48) → (51.5, 48); the
arrowhead is (62.2, 39.6) → (70.8, 48.2) → (62.2, 56.8).

The chosen lockup is the mark on paper `#F4F1EA` beside "Gaffer" in `#0E1116` — see the
"On light" panel in the logo sheet. The lime-tile variant exists only for dark surfaces.

Rules: minimum clear space equal to the tile's corner radius on all sides. Never recolour the
glyph outside `#0E1116` on `#C8FF3D` or `#C8FF3D` on `#0E1116`. Never stretch, rotate, or add
effects. Below 20px use `gaffer-mark-16.svg`. Two alternate directions (a tactics-board mark
and a deadline-dial mark) are shown in `design/Gaffer Logo.dc.html` if the primary is rejected.

Fonts: Sora and IBM Plex Mono, both SIL Open Font License — bundle the woff2 files locally
rather than loading from Google Fonts, since the app runs offline.

Icons in the rail are 24-unit stroke icons, `stroke-width 1.7`, round caps, rendered at 15px
in `currentColor`. Any comparable stroke set (Lucide, Feather) matches.

## Files in this bundle

```
README.md                     this document
BUILD-SPEC.md                 data model, FPL endpoints, caching, derived logic
design/Gaffer.dc.html         the interactive prototype — all 8 screens + drawer
design/Gaffer Logo.dc.html    logo options, usage, size tests
design/support.js             runtime the two HTML files need to open locally
brand/gaffer-mark.svg
brand/gaffer-mark-inverse.svg
brand/gaffer-mark-16.svg
brand/gaffer-lockup.svg
```
