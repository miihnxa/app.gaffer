# Handoff: Gaffer landing page

## Overview
A single-page marketing site whose only job is to get a visitor to download the Gaffer Mac
app and trust it enough to install an unsigned binary. Eight sections in fixed order:
nav, hero, "the refusal" demo, four feature cards, download + trust callout, accounts,
FAQ, footer.

## About the design files
`index.html` in this folder is a **finished, self-contained static page** — inline CSS, no
build step, no external JS. Google Fonts is the only external request. It is intended to
ship as-is: drop it on a static host, wire two links, done.

The other files are references:

- `LANDING-BRIEF.md` — the original brief. It is the source of truth for copy, tokens and
  the "do not use" list. **Read it before changing anything.**
- `mark.svg` — the logo mark. The nav and footer inline the same paths directly, so the
  file is only needed as the favicon.
- `reference/Gaffer Landing.dc.html` + `reference/support.js` — the design-tool version of
  the same page. Useful only if you want to open the original prototype. Not needed to
  ship, and not a dependency of `index.html`.

If you are instead recreating this page inside an existing site (Next.js, Astro, Hugo,
etc.), treat `index.html` as a pixel-level spec and rebuild it with that project's
component and styling conventions rather than pasting the markup.

## Fidelity
**High-fidelity.** Final colours, type, spacing and copy. Recreate exactly if porting.

## What must be wired before launch
Four placeholders, all `href="#"`:

1. Download button in the download section → GitHub Release `.dmg` / `.zip` URL.
   (The nav and hero buttons are anchors to `#download` and are already correct.)
2. Footer links: Privacy, Terms, Licence, GitHub.
3. Version string `Version 1.0 · macOS 11+ · Apple silicon and Intel` — update per release.
4. The nav "Privacy" link currently anchors to the trust lines inside the download panel
   (`#privacy`). Point it at a real privacy page when one exists.

## Known substitution — hero image
The brief calls for **a real screenshot of the squad screen** in the hero panel. No
screenshot was available, so the hero currently contains a faithful HTML rendering of that
screen (tactics-board XI, mono price/form values, one flagged player in `--crit`, one blank
gameweek in `--warn`, bench row, status line).

Replace it with a real PNG/WebP screenshot before launch. The container to swap is the
second child of `section.hero` — a `div` with `border: 1px solid #242C36; border-radius:
12px; background: #11161C; overflow: hidden`. Put an `<img style="display:block;
width:100%; height:auto">` inside it and delete the rendered contents. Do not add a device
frame, angle or shadow.

## Screens / views
One page. Max content width 1200px, 32px side padding, centred.

### 1. Nav
- Sticky, `top: 0`, `z-index: 20`, height 62px, `border-bottom: 1px solid #1C232C`,
  background `rgba(14,17,22,0.94)`.
- Left: 26px logo mark + wordmark "Gaffer", 16px/600, `-0.02em`, 10px gap.
- Right: "How it works" (`#how`), "Privacy" (`#privacy`) — 14px, `#8B97A6`, 28px gap —
  then the Download button: 34px tall, 0 14px padding, radius 7px, `#C8FF3D` on
  `#0E1116` text, 13.5px/600.
- Below 900px the two text links are hidden; logo + button remain.

### 2. Hero
- Grid `minmax(0,1fr) minmax(0,1.02fr)`, 64px gap, `align-items: center`,
  padding `104px 0 96px`. Single column with 40px gap below 900px (screenshot drops under
  the copy).
- Eyebrow: `FANTASY PREMIER LEAGUE ASSISTANT`, IBM Plex Mono 12px, `0.14em`, `#8B97A6`,
  26px bottom margin.
- H1: 64px (44px below 900px), `line-height: 1.02`, `-0.035em`, weight 600, `max-width:
  12ch`. Copy: "Know your best move before the deadline."
- Sub: 17px `#8B97A6`, `max-width: 52ch`, 28px top margin.
- CTA: 48px tall lime button "Download for Mac", radius 7px, 0 24px padding, 15px/600.
  Full-width below 900px.
- Under it: IBM Plex Mono 12px `#5D6875` — `macOS 11+ · free · no account required`.
- Then text link "How it works ↓", 14px `#8B97A6`, 1px `#242C36` bottom border.

### 3. The refusal
- Full-width panel: `#11161C`, 1px `#242C36`, radius 12px, padding `56px 48px`.
- H2 40px, `1.1`, `-0.03em`, 600, `max-width: 22ch`: "It tells you when you're about to be
  wrong."
- `<pre>` block: IBM Plex Mono 13.5px, `line-height: 1.7`, `#8B97A6` on `#0E1116`, 1px
  `#1C232C`, radius 7px, 24px padding, `overflow-x: auto`, 40px top margin. `BLOCKED` is
  `#FF5C7A` weight 500; its two reason lines are `#FF5C7A`. Content verbatim from the brief.
- Caption 14px `#8B97A6`, `max-width: 66ch`, 28px top margin.

### 4. What it does
- H2 28px `-0.03em` 600, 40px bottom margin.
- 2×2 grid, 20px gap; one column below 900px.
- Cards: `#11161C`, 1px `#242C36`, radius 12px, 28px padding. Title 20px/600 `-0.02em`,
  12px bottom margin; body 14px `#8B97A6`. No icons.
- Card 3 italicises "first" in "It buys the bench *first*".

### 5. Download
- Panel `#11161C`, 1px `#242C36`, radius 12px, padding `64px 48px`.
- Centred 620px column: H2 34px `-0.03em` 600 → lime button (48px, 0 26px, 32px top
  margin) → mono 12px `#5D6875` version line, 14px top margin.
- Unsigned-app callout: 620px, `#161D25`, 1px `#242C36`, radius 7px, padding `22px 24px`,
  40px top margin. Bold 15px lead line, 14px `#8B97A6` body. Not collapsed, not styled as
  a warning — plain and matter-of-fact by design.
- Three trust lines, `id="privacy"`: mono 12px `#5D6875` markers `01 02 03`, 14px gap,
  text 14px `#8B97A6`.

### 6. Accounts
- Two columns, 48px gap, `border-top: 1px solid #1C232C`, `padding-top: 72px`.
  One column below 900px.
- Left: H2 28px `-0.03em` 600, `max-width: 16ch` — "An account is optional."
- Right: 15px `#8B97A6` paragraph, then a 14px `#5D6875` line about team IDs being public.

### 7. FAQ
- H2 28px, 32px bottom margin. Native `<details>` — no JS.
- Each row: `border-bottom: 1px solid #1C232C`; `<summary>` is flex, space-between, 20px
  vertical padding, `min-height: 44px`, 16px/500. Right side is a `+` (18px `#8B97A6`)
  that rotates 45° when open via `details[open] .faq-plus { transform: rotate(45deg) }`,
  0.15s transition. Answer 14px `#8B97A6`, `max-width: 72ch`, 22px bottom margin.
- Default marker is hidden (`summary::-webkit-details-marker { display: none }` +
  `list-style: none`).

### 8. Footer
- `border-top: 1px solid #1C232C`, padding `48px 32px 64px`.
- 22px mark + wordmark, then links row (14px `#8B97A6`, 20px gap, wraps), then the legal
  paragraph: 12px, `line-height: 1.7`, `#5D6875`, `max-width: 80ch`.
- **The legal paragraph is required. Do not cut or shorten it.**

## Interactions & behaviour
- No JavaScript anywhere. FAQ uses `<details>`; smooth scrolling uses
  `html { scroll-behavior: smooth }`.
- Anchors: `#top`, `#how`, `#download`, `#privacy`.
- Global link hover: `a:hover { color: #C8FF3D }`. Buttons have no hover change.
- Responsive breakpoint: 900px only. Below it — single-column grids, 44px H1, hidden nav
  links, full-width buttons, 20px side padding.
- All tap targets ≥ 34px in the nav and ≥ 44px in the FAQ and CTAs.

## State management
None. Static document.

## Design tokens
Values are written as literals in the file (no CSS custom properties), so a find-and-replace
is safe.

| Token | Value | Used for |
| --- | --- | --- |
| `--bg` | `#0E1116` | page ground, code block, text on lime |
| `--panel` | `#11161C` | cards, panels |
| `--panel-2` | `#161D25` | inner cards, callout, player tiles |
| `--line` | `#1C232C` | hairlines, tile borders |
| `--line-strong` | `#242C36` | panel/card borders |
| `--text` | `#E9EEF4` | headings, body |
| `--muted` | `#8B97A6` | secondary text |
| `--faint` | `#5D6875` | mono meta, legal |
| `--accent` | `#C8FF3D` | download buttons, logo, link hover |
| `--accent-ink` | `#0E1116` | text on lime |
| `--crit` | `#FF5C7A` | BLOCKED, flagged player |
| `--warn` | `#FFB020` | blank gameweek |

**Lime appears exactly three times as UI** (nav button, hero button, download button),
plus the logo mark and the link-hover colour. Keep it that way.

- Type: Sora 400/500/600/700; IBM Plex Mono 400/500 for every number, price, code and
  fixture. Body 15px / 1.65.
- Radii: 7px controls, 12px panels.
- Borders: 1px. **No shadows anywhere.**
- Section rhythm: 96px bottom padding per section; 104px hero top.
- Prices in `£`, monospaced. Form to one decimal. British English throughout
  ("gameweek", "licence").

## Assets
- `mark.svg` — lime rounded square (radius 22/96) with a dark arc-and-arrow glyph, 9px
  strokes. Inlined in nav (26px) and footer (22px); also the favicon.
- No other images. No stock photography, no club badges, kits or crests — prohibited by
  the brief.
- Fonts from Google Fonts: `Sora:wght@400;500;600;700` and `IBM+Plex+Mono:wght@400;500`,
  `display=swap`. Self-host if you want zero third-party requests.

## Files
```
design_handoff_gaffer_landing/
  index.html                        ship this
  mark.svg                          favicon / logo source
  README.md                         this document
  LANDING-BRIEF.md                  original brief — copy and rules
  reference/
    Gaffer Landing.dc.html          design-tool prototype (optional)
    support.js                      runtime for the prototype only
```
