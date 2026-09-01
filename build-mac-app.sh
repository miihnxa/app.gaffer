#!/usr/bin/env bash
# Builds "Gaffer.app" — a real double-clickable Mac app.
#
# It wraps the project's venv rather than freezing a binary: no py2app or
# PyInstaller, nothing to re-sign, and the app always runs the current code.
# The trade-off is that the .app depends on this folder staying put.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="${1:-$HOME/Applications/Gaffer.app}"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Gaffer</string>
  <key>CFBundleDisplayName</key><string>Gaffer</string>
  <key>CFBundleIdentifier</key><string>com.mihnea.gaffer</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>gaffer</string>
  <key>CFBundleIconFile</key><string>gaffer</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSAppTransportSecurity</key>
  <dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/gaffer" <<LAUNCH
#!/bin/bash
cd "$HERE"
exec "$HERE/.venv/bin/python" "$HERE/desktop.py" "\$@"
LAUNCH
chmod +x "$APP/Contents/MacOS/gaffer"

# Icon: drawn by make-icon.py, which owns the geometry and real transparency.
# (macOS has no SVG rasteriser and qlmanage flattens alpha onto white.)
ICONSET="$(mktemp -d)/gaffer.iconset"
"$HERE/.venv/bin/python" "$HERE/make-icon.py" "$ICONSET"

iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/gaffer.icns" 2>/dev/null \
  && echo "  icon built" || echo "  icon skipped (app still works)"

touch "$APP"
echo "✓ Built $APP"
echo "  Open it from Launchpad, Spotlight ('Gaffer'), or:  open '$APP'"
