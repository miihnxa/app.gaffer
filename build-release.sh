#!/usr/bin/env bash
# Builds, signs and packages Gaffer.app for distribution.
#
# The signing happens on a copy made with `ditto --norsrc --noextattr`: this
# project lives under Desktop, where Finder attaches metadata that makes
# codesign fail with "resource fork, Finder information, or similar detritus".
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-1.0.0}"
export GAFFER_VERSION="$VERSION"
STAGE="$(mktemp -d)"

echo "==> icon"
"$HERE/.venv/bin/python" "$HERE/make-icon.py" "$HERE/build-assets/gaffer.iconset" >/dev/null
iconutil -c icns "$HERE/build-assets/gaffer.iconset" -o "$HERE/build-assets/gaffer.icns"

echo "==> refusing to ship anything personal"
if grep -rqiE "mihnea|cirstica|mourinho to the pl|6445742|631812" "$HERE/defaults/"; then
  echo "    FAIL: defaults/ contains personal data" >&2; exit 1
fi

echo "==> build"
rm -rf "$HERE/build" "$HERE/dist"
"$HERE/.venv/bin/pyinstaller" "$HERE/gaffer.spec" --noconfirm --clean --log-level ERROR || true
[ -d "$HERE/dist/Gaffer.app" ] || { echo "    FAIL: no bundle produced" >&2; exit 1; }

echo "==> sign (on a metadata-free copy)"
ditto --norsrc --noextattr --noqtn "$HERE/dist/Gaffer.app" "$STAGE/Gaffer.app"
codesign --force --deep --sign - "$STAGE/Gaffer.app"
codesign --verify --deep --strict "$STAGE/Gaffer.app"

echo "==> package"
mkdir -p "$HERE/release"
ZIP="$HERE/release/Gaffer-${VERSION}-macOS.zip"
rm -f "$ZIP"
( cd "$STAGE" && ditto -c -k --keepParent --norsrc --noextattr "Gaffer.app" "$ZIP" )

echo "==> verify the version the bundle reports"
BUILT="$(defaults read "$HERE/dist/Gaffer.app/Contents/Info.plist" CFBundleShortVersionString)"
[ "$BUILT" = "$VERSION" ] || { echo "    FAIL: bundle says $BUILT, packaging $VERSION" >&2; exit 1; }

echo "==> verify the archive a user would download"
VERIFY="$(mktemp -d)"
( cd "$VERIFY" && unzip -q "$ZIP" && codesign --verify --deep --strict "Gaffer.app" )
if grep -rlq "Mihnea\|Cirstica\|6445742\|Mourinho" "$VERIFY/Gaffer.app" 2>/dev/null; then
  echo "    FAIL: personal data inside the bundle" >&2; exit 1
fi
rm -rf "$VERIFY" "$STAGE"

echo
echo "✓ $ZIP"
echo "  $(shasum -a 256 "$ZIP" | awk '{print $1}')"
echo "  $(ls -la "$ZIP" | awk '{printf "%.1f MB", $5/1048576}')"
