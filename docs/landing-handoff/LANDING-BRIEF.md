# Landing page — brief for Claude Design

One page. Its only job is to get someone to **download the Mac app** and trust it enough
to install something unsigned. Everything else is subordinate to that.

Paste this whole file into Claude Design.

---

## Design system — reuse, don't reinvent

Identical tokens to the app, so the site and the product feel like one thing.

```
--bg          #0E1116   page ground
--panel       #11161C   cards
--panel-2     #161D25   inputs, inner cards
--line        #1C232C   hairline
--line-strong #242C36   card border
--text        #E9EEF4
--muted       #8B97A6
--faint       #5D6875
--accent      #C8FF3D   lime
--accent-ink  #0E1116   text on lime
--crit        #FF5C7A
--warn        #FFB020
```

Type: **Sora** 400/500/600/700, **IBM Plex Mono** 400/500 for every number, code and
fixture. Body 15px/1.65. Radii 7px controls, 12px panels. Borders 1px. **No shadows.**

**Lime appears at most three times on the page.** One is the download button. Spend the
other two deliberately.

**Do not use:** gradient heroes, glassmorphism, blurred glows, emoji as section markers,
stock photos of footballers, mockups floating at a 3D angle, "Trusted by 10,000 managers"
(it isn't true yet), or any Premier League club badge, kit or crest.

The logo is a lime rounded square with a dark arc-and-arrow glyph — the `G` mark from
`src/fpl/webapp/static/mark.svg`. Attach that file when you paste this.

---

## Sections, in order

### 1. Nav
Logo + wordmark left. Right: "How it works", "Privacy", and a small lime **Download**
button. Sticky, 62px, 1px bottom border.

### 2. Hero
The thesis, not a feature list.

- Eyebrow: `FANTASY PREMIER LEAGUE ASSISTANT`
- Headline, 58–72px, -0.035em, max 12ch: **"Know your best move before the deadline."**
- Sub, 17px muted, max 52ch: *"Gaffer reads your squad from public FPL data and tells you
  what to fix — flagged players, blank gameweeks, and the transfers that actually improve
  your team rather than just changing it."*
- Primary: lime **Download for Mac** button. Under it, in 12px faint: `macOS 11+ · free ·
  no account required`
- Secondary text link: "How it works ↓"

**To the right of the copy, show the actual app.** A real screenshot of the squad screen,
in a panel with a 1px border and 12px radius. Not a floating device mockup, not angled.
The product is the proof.

### 3. The refusal — the one thing to get right
This is the differentiator. Give it a full section, dark panel, mono type.

Headline: **"It tells you when you're about to be wrong."**

Then a terminal-style block, `IBM Plex Mono` 13.5px:

```
OUT  Brobbey (SUN, FWD, £6.0m)          form 2.0
IN   Igor Jesus (NFO, FWD, £6.0m)       form 1.5

Form change: -0.5   Cost: £+0.0m

BLOCKED
  Igor Jesus form 1.5 is BELOW Brobbey form 2.0 — you'd be
  paying a transfer to move backwards
```

`BLOCKED` and the reason in `--crit`. Everything else muted.

Caption beneath, 14px: *"Most tools suggest transfers. Gaffer checks the one you already
want to make and blocks it when the numbers say it makes your team worse."*

### 4. What it does — four cards, two columns
Titles 20px, body 14px muted. No icons unless they're line-drawn and consistent.

1. **Your squad, read properly** — The XI on a tactics board with fixture difficulty,
   injuries, blank gameweeks, illegal formations, bad bench order, and players of yours
   facing each other.
2. **The transfer planner** — Every suggested replacement has already cleared your form
   rule, your bank, and the three-per-club limit. If nothing clears them, it says so
   instead of inventing a pick.
3. **The squad rebuilder** — Lock who you keep, set a bench budget, get a legal 15. It
   buys the bench *first*, so a Bench Boost is actually worth playing.
4. **Your mini-leagues** — Standings, weekly movement, and one click into any rival's
   squad to see what they own that you don't.

### 5. Download — the section that has to be honest
Panel, centred, generous padding.

- **Download Gaffer for Mac** (lime button, links to the GitHub Release .dmg/.zip)
- Under it, mono 12px: `Version 1.0 · macOS 11+ · Apple silicon and Intel`

Then a bordered callout, **not hidden and not apologetic**:

> **First launch: right-click the app and choose Open.**
> Gaffer isn't signed with an Apple Developer certificate yet, so macOS will warn that the
> developer can't be verified. Right-click → Open, once, and it won't ask again.
> Only download Gaffer from this page — that warning is also what malware looks like.

Three trust lines under that, mono `01` `02` `03` markers:
- Never asks for your FPL password, and cannot change your team
- Reads only public Fantasy Premier League data
- No tracking, no ads, no telemetry

### 6. Accounts — optional, say so
Short section, two columns.

Left: **"An account is optional."**
Right: *"Signed out, Gaffer works exactly the same — your team ID is remembered on your
machine. Sign in and it follows you to another Mac. We hold your email address and your
team ID. Nothing else. No password: we email you a six-digit code."*

One line in `--faint`: *"Your FPL team ID is public data — anyone can look up any team on
the official site. An account protects your email and your setup, not your squad."*

That honesty is the point. Don't soften it.

### 7. FAQ — four items, collapsible
- **Do I have to give you my FPL password?** No, and you never should, to anyone. Gaffer
  needs only your team ID, the number in the URL of your Points page.
- **Can it make my transfers for me?** No, deliberately. FPL has no official write API, so
  any tool claiming to act for you is storing your login and driving the website. Gaffer
  advises; you type it in.
- **Will it show transfers I've already made this week?** Not until the deadline passes.
  Public FPL data doesn't publish a squad for a gameweek that hasn't started. Gaffer tells
  you which gameweek it's showing rather than pretending it's current.
- **Is this official?** No. Gaffer is independent and not affiliated with, endorsed by, or
  connected to the Premier League or Fantasy Premier League.

### 8. Footer
Logo, then links: Privacy · Terms · Licence · GitHub. Then, in `--faint`, 12px:

> Gaffer is an independent tool and is not affiliated with, endorsed by, or connected to
> the Premier League, Fantasy Premier League, or any football club. "Premier League" and
> "Fantasy Premier League" are trademarks of the Football Association Premier League
> Limited. Player and fixture data is read from publicly available endpoints.

**This paragraph is required. Do not cut it for visual balance.**

---

## Copy rules

- Never claim user numbers, ratings or testimonials you don't have.
- Never imply the app can act in the game.
- Never call it official, or use PL branding.
- Prices in `£`, monospaced. Form to one decimal.
- British English: "gameweek", "favourite", "licence" (noun).

## Responsive
Full width 1200px max. Single column below 900px. The hero screenshot drops below the copy
on mobile. Download button full-width on mobile. Tap targets ≥ 44px.

## What I need back
A single self-contained HTML file with inline CSS, no build step and no external JS. Google
Fonts is the only external request. I'll wire the download link and drop it into the site.
