# Gaffer API

Base: `https://yourdomain.com`
Auth: `Authorization: Bearer <jwt>` or the `gaffer_session` cookie.

All data is read-only. No endpoint changes anyone's FPL team.

## Auth

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/auth/request` | `{"email":"..."}` | Emails a single-use link, valid 20 min. Always returns the same message, so it can't be used to discover who has an account. |
| GET | `/api/auth/callback?token=` | — | Consumes the token, sets the session cookie, redirects to `/app`. |
| POST | `/api/auth/logout` | — | Clears the cookie. |
| GET | `/api/me` | — | `{signed_in, email, plan, pro, team_id}` |

## Free

| Method | Path | Returns |
|---|---|---|
| GET | `/api/season` | Next gameweek, deadline, chip expiry |
| GET | `/api/team/<id>` | Entry, squad, fixtures, flags, advice, leagues |
| GET | `/api/league/<id>?team=<id>` | Standings with movement |
| GET | `/api/search?q=` | Player search |
| GET | `/api/ticker?n=5` | Fixture difficulty by club |

`/api/team/<id>` omits `replacements` for free accounts — it's the paid
feature and the expensive half of the request.

## Pro

| Method | Path | Query |
|---|---|---|
| GET | `/api/team/<id>/rebuild` | `lock=<player_id>` (repeatable), `bench=19.0`, `budget=` |

## Billing

| Method | Path | Body |
|---|---|---|
| POST | `/api/billing/checkout` | `{"cadence":"monthly"\|"annual"}` → `{url}` |
| POST | `/api/billing/portal` | — → `{url}` |
| POST | `/api/billing/webhook` | Stripe event (signature verified) |

## Errors

```json
{"error": "This is a Pro feature.", "code": "upgrade_required"}
```

| Code | HTTP | Meaning |
|---|---|---|
| `auth_required` | 401 | Sign in |
| `upgrade_required` | 402 | Pro feature, or free daily limit hit |
| `team_not_found` | 404 | No such FPL team id |
| `rate_limited` | 429 | `Retry-After` header included |

## Rate limits

20/min anonymous · 60/min free · 180/min Pro. Free accounts also get 25 team
lookups a day.
