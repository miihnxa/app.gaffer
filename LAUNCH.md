# Launching Gaffer — free

The product is built. This is what's left: hosting, a domain, and the frontend.

---

## 0. The legal position, now that it's free

Gaffer reads the **public** Fantasy Premier League endpoints. That's how nearly
every FPL tool works. Giving it away removes the sharpest edge of the risk —
you are not commercialising someone else's data — and puts you alongside the
many free community tools that have run for years without trouble.

Still worth keeping true, and all already done in code and copy:

- No Premier League or club branding, badges, kits or crests.
- Named "Gaffer", not "FPL <something>" — no implied endorsement.
- Not-affiliated disclaimer on the landing page, terms and privacy.
- Analysis per user, **no bulk redistribution** — there is no dump-all endpoint.
- The shared cache honours the API's own `cache-control: max-age=300`, and
  requests are rate limited. The service is a light, well-behaved client.

**If you later decide to charge**, re-read this section — the risk calculus
changes and it's worth a conversation with an IP solicitor first.

---

## 1. Deploy the API — free options

The app is a container, so anything that runs Docker works. Ranked for a free
launch:

### Fly.io — recommended
Free allowance covers this comfortably. Needs a card on file for verification
but won't charge at this size.

```bash
brew install flyctl && fly auth login
fly launch --no-deploy
fly volumes create gaffer_data --size 1 --region lhr
fly secrets set GAFFER_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
fly deploy
```

### Render — no card
Free web service, but it **sleeps after 15 minutes idle** and takes ~40s to
wake, refetching FPL data on boot. Fine for launch, irritating once people use
it. Point it at the Dockerfile and set `GAFFER_SECRET`.

### Railway
$5 of monthly credit, no sleeping. Comfortably enough for this.

**Whichever you pick**, `GAFFER_SECRET` must be at least 32 bytes — the app
refuses to boot otherwise, since a short HS256 key is weaker than the hash it
feeds. Everything else has a working default.

Optional, only if you want sign-in emails to actually send:
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
Resend's free tier is 3,000 emails a month. Without it, sign-in is disabled in
practice — which is fine, because nothing requires an account.

---

## 2. Frontend

Two routes. Pick one:

**A — ship what exists.** `src/fpl/cloud/web/` is already built, on-brand and
responsive, and it's served by the same container. Nothing more to do. Deploy
and you have a working product today.

**B — rebuild the UI in Lovable or Base44.** See `LOVABLE-BRIEF.md` — it has
staged prompts, the exact palette and type, screen-by-screen specs, and real
API samples to attach. Set `GAFFER_CORS_ORIGINS` to your Lovable domain or the
browser will block every request.

Do A first regardless. It costs nothing, and it means you have something live
while you iterate on B.

---

## 3. Domain

You already own the repo name `gaffer.app`. If you own the domain too, point it
at the deploy and set `GAFFER_BASE_URL=https://gaffer.app`. If not, the
`.fly.dev` or `.onrender.com` subdomain is fine to launch on.

---

## 4. Before you tell anyone

- [ ] Load a team ID that isn't yours and confirm it works
- [ ] Check it on a phone — most people will open it on one
- [ ] Confirm the stale-gameweek banner appears before a deadline
- [ ] Break something on purpose: a bad team id should say so, not 500
- [ ] Watch the logs through one deadline — that's peak traffic

---

## 5. Where the traffic risk actually is

Every user of your service hits the same upstream FPL API through your one
server. The shared cache means one fetch serves everyone for 5 minutes, and
responses carry `s-maxage=300` so a CDN in front absorbs the rest.

If it gets popular, put Cloudflare in front before you scale the server. That
is the single highest-leverage thing you can do, and it's free.

---

## 6. What to build next, if people use it

The engine already supports these — they just need surfacing:

- **Deadline reminders** by email, the thing the CLI already does over ntfy.
- **Price change alerts** — `engine/prices.py` is written and tested.
- **Rival diffing** in the league view — `engine/league.py` has it.
- **Live gameweek tracking** — `engine/live.py`, polls only during matches.
