# Launching Gaffer

Everything below is the work that remains. The product is built; this is
plumbing, accounts and a legal decision.

---

## 0. Read this first — the legal position

Gaffer reads the **public** Fantasy Premier League endpoints. That is how
almost every FPL tool works, and several are paid products (Fantasy Football
Hub, FPL Review Premium, Fantasy Football Scout). So there is real precedent
for charging. But the endpoints are undocumented and carry no commercial
licence, so there is genuine risk, and it rises the moment money is involved.

**What reduces it, all already done in the code and copy:**

- No Premier League or club branding, badges, kits or crests anywhere.
- The name is "Gaffer", not "FPL <something>" — no implied endorsement.
- A clear not-affiliated disclaimer on the landing page, terms and privacy.
- Data is used for per-user analysis, **not redistributed in bulk** — there is
  no "download all players" endpoint.
- The shared cache honours the API's own `cache-control: max-age=300`, and
  requests are rate limited, so the service is a light, well-behaved client.
- No scraping of paid competitors, per the original build spec.

**What I cannot do for you:** tell you it is legally safe. Before you take
money, get an hour with a solicitor who knows IP — specifically about the
trademark use in marketing copy and the unlicensed API. That hour is cheap
next to a takedown after you have paying subscribers.

**Lower-risk variation if you want one:** let each user paste their own data or
authenticate against FPL themselves, and sell only the analysis. It's a worse
product; it's a cleaner position.

---

## 1. Accounts you need (only you can create these)

| Service | For | Cost |
|---|---|---|
| **Stripe** | Subscriptions | 1.5% + 20p per charge |
| **Fly.io** (or Railway/Render) | Hosting | ~$5/mo |
| **Domain** | gaffer.app or similar | ~$15/yr |
| **Email sender** (Resend/Postmark/SES) | Magic-link sign-in | Free tier is plenty |

---

## 2. Deploy the API

```bash
brew install flyctl && fly auth login
fly launch --no-deploy          # accept the existing fly.toml
fly volumes create gaffer_data --size 1 --region lhr
```

Set the secrets:

```bash
fly secrets set \
  GAFFER_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  STRIPE_SECRET_KEY="sk_live_..." \
  STRIPE_WEBHOOK_SECRET="whsec_..." \
  STRIPE_PRICE_MONTHLY="price_..." \
  STRIPE_PRICE_ANNUAL="price_..." \
  SMTP_HOST="smtp.resend.com" SMTP_PORT="587" \
  SMTP_USER="resend" SMTP_PASSWORD="re_..." \
  SMTP_FROM="hello@yourdomain.com"
```

```bash
fly deploy
```

`GAFFER_SECRET` must be at least 32 bytes — the app refuses to start otherwise,
because a short HS256 key is weaker than the hash it feeds.

## 3. Stripe

1. Create a **Product** "Gaffer Pro" with two prices: £3.99/month and £29/year.
   Copy both price ids into the secrets above.
2. Add a webhook endpoint: `https://yourdomain.com/api/billing/webhook`,
   subscribed to `checkout.session.completed`,
   `customer.subscription.created|updated|deleted`. Copy the signing secret.
3. Test with `stripe listen --forward-to localhost:8080/api/billing/webhook`.

The webhook signature is verified before the body is parsed — that is what
stops anyone POSTing themselves a free subscription.

## 4. Before you charge anyone

- [ ] Legal review (section 0)
- [ ] Point the domain at the app, set `GAFFER_BASE_URL`
- [ ] Send a real magic-link email and click it end to end
- [ ] Run one real £3.99 checkout with a live card, then refund it
- [ ] Cancel from the billing portal, confirm access drops to free
- [ ] Confirm the free tier still works signed-out
- [ ] Load-check: the FPL API is one upstream for all your users

---

## 5. Where Lovable and Base44 fit

Neither runs Python, and the Python engine *is* the product — the transfer
guard, the rebuilder, the fixture maths, and 27 tests covering the rules.
Rebuilding that in a prompt-driven app builder would mean rewriting tested
logic in TypeScript and losing the thing competitors can't copy in a weekend.

**Use them for the frontend, calling this API.** That's a real division of
labour and it works:

1. Deploy this API first (section 2). It already sends CORS headers — set
   `GAFFER_CORS_ORIGINS` to your Lovable/Base44 domain.
2. Build the interface there against the endpoints in `API.md`.
3. Keep auth and billing **here**, not in Supabase — the paywall has to be
   enforced server-side next to the data, or anyone can call the API directly
   and skip it.

**Or skip them.** The app in `src/fpl/cloud/web/` is already built, on-brand
and responsive. Lovable is worth it if you want a richer marketing site than
the current landing page, not for the app itself.

My recommendation: ship what exists, get ten paying users, and only then decide
whether the frontend is what's holding you back. It probably won't be.
