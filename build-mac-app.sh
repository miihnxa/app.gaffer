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

# Icon: the same brand mark the app draws in its own chrome
# (src/fpl/webapp/static/mark-icon.svg) — glyph only, transparent ground.
ICONSET="$(mktemp -d)/gaffer.iconset"; mkdir -p "$ICONSET"
"$HERE/.venv/bin/python" - "$ICONSET" "$HERE/src/fpl/webapp/static/mark-icon.svg" <<'PYICON'
import sys, subprocess, pathlib, shutil
out = pathlib.Path(sys.argv[1])
src = pathlib.Path(sys.argv[2])
work = out.parent
svg = work / "mark-icon.svg"
shutil.copyfile(src, svg)
png = work / "mark-icon.png"

# No SVG rasteriser ships with macOS, but Quick Look renders one.
subprocess.run(["qlmanage", "-t", "-s", "1024", "-o", str(work), str(svg)],
               capture_output=True)
produced = work / "mark-icon.svg.png"
if produced.exists():
    produced.rename(png)

if not png.exists():
    sys.exit("could not rasterise mark.svg — icon skipped")

for size in (16, 32, 64, 128, 256, 512):
    for scale, suffix in ((1, ""), (2, "@2x")):
        px = size * scale
        subprocess.run(["sips", "-z", str(px), str(px), str(png),
                        "--out", str(out / f"icon_{size}x{size}{suffix}.png")],
                       capture_output=True)
print("  rasterised", png.stat().st_size, "bytes")
PYICON
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/gaffer.icns" 2>/dev/null \
  && echo "  icon built" || echo "  icon skipped (app still works)"

touch "$APP"
echo "✓ Built $APP"
echo "  Open it from Launchpad, Spotlight ('Gaffer'), or:  open '$APP'"
