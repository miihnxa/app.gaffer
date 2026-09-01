#!/usr/bin/env bash
# One-shot Fly deploy. Run `fly auth login` first — that step is interactive.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

APP="${1:-gaffer-fpl}"
REGION="${FLY_REGION:-lhr}"          # London — nearest to the FPL API

command -v flyctl >/dev/null || { echo "flyctl not installed: brew install flyctl"; exit 1; }
flyctl auth whoami >/dev/null 2>&1 || { echo "Not logged in. Run: fly auth login"; exit 1; }
echo "==> authenticated as $(flyctl auth whoami)"

# Fly app names are globally unique; walk to a free one rather than failing.
if ! flyctl apps list 2>/dev/null | awk '{print $1}' | grep -qx "$APP"; then
  for candidate in "$APP" "$APP-api" "$APP-$RANDOM"; do
    if flyctl apps create "$candidate" --org personal >/dev/null 2>&1; then
      APP="$candidate"; echo "==> created app $APP"; break
    fi
    echo "    name '$candidate' unavailable, trying another"
  done
fi
flyctl apps list | awk '{print $1}' | grep -qx "$APP" || { echo "could not create an app"; exit 1; }
echo "==> using app: $APP"

# fly.toml must name the app it deploys to.
/usr/bin/sed -i '' "s|^app = .*|app = \"$APP\"|" fly.toml
/usr/bin/sed -i '' "s|GAFFER_BASE_URL = .*|GAFFER_BASE_URL = \"https://$APP.fly.dev\"|" fly.toml

# SQLite holds accounts, so it needs a volume that survives redeploys.
if ! flyctl volumes list -a "$APP" 2>/dev/null | grep -q gaffer_data; then
  echo "==> creating 1GB volume"
  flyctl volumes create gaffer_data --size 1 --region "$REGION" -a "$APP" --yes
fi

# The app refuses to boot on a short signing key, so generate a real one.
if ! flyctl secrets list -a "$APP" 2>/dev/null | grep -q GAFFER_SECRET; then
  echo "==> setting GAFFER_SECRET"
  flyctl secrets set -a "$APP" \
    GAFFER_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" \
    --stage
fi

echo "==> deploying (remote builder — no local Docker needed)"
flyctl deploy -a "$APP" --remote-only --yes

URL="https://$APP.fly.dev"
echo "==> verifying $URL"
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$URL/healthz" || true)
  [ "$code" = "200" ] && { echo "    healthz OK"; break; }
  sleep 4
done
for p in / /app /api/season "/api/team/1234567"; do
  printf "    %-22s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' "$URL$p")"
done

echo
echo "LIVE: $URL"
echo "Next: allow your Base44 domain to call it —"
echo "  flyctl secrets set -a $APP GAFFER_CORS_ORIGINS='https://gaffer-match-ready.base44.app'"
