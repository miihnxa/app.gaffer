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

# Icon: render the pitch-green badge at every size macOS asks for.
ICONSET="$(mktemp -d)/gaffer.iconset"; mkdir -p "$ICONSET"
"$HERE/.venv/bin/python" - "$ICONSET" <<'PYICON'
import sys, subprocess, pathlib
out = pathlib.Path(sys.argv[1])
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#2E8B57"/><stop offset="1" stop-color="#123F2A"/></linearGradient></defs>
<rect width="1024" height="1024" rx="228" fill="#140419"/>
<rect x="112" y="112" width="800" height="800" rx="160" fill="url(#g)"/>
<rect x="196" y="196" width="632" height="632" rx="104" fill="none" stroke="#ffffff" stroke-opacity=".34" stroke-width="14"/>
<circle cx="512" cy="512" r="120" fill="none" stroke="#ffffff" stroke-opacity=".34" stroke-width="14"/>
<path d="M370 196v96h284v-96" fill="none" stroke="#ffffff" stroke-opacity=".34" stroke-width="14"/>
<path d="M370 828v-96h284v96" fill="none" stroke="#ffffff" stroke-opacity=".34" stroke-width="14"/>
<text x="512" y="596" font-family="Helvetica-Bold,Helvetica,Arial" font-weight="bold"
 font-size="300" fill="#ffffff" text-anchor="middle">G</text></svg>'''
src = out.parent/"icon.svg"; src.write_text(svg)
png = out.parent/"icon.png"
subprocess.run(["qlmanage","-t","-s","1024","-o",str(out.parent),str(src)],
               capture_output=True)
cand = out.parent/"icon.svg.png"
if cand.exists(): cand.rename(png)
if not png.exists():
    subprocess.run(["sips","-s","format","png",str(src),"--out",str(png)],capture_output=True)
for size in (16,32,64,128,256,512):
    for scale,suffix in ((1,""),(2,"@2x")):
        px = size*scale
        subprocess.run(["sips","-z",str(px),str(px),str(png),
                        "--out",str(out/f"icon_{size}x{size}{suffix}.png")],capture_output=True)
PYICON
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/gaffer.icns" 2>/dev/null \
  && echo "  icon built" || echo "  icon skipped (app still works)"

touch "$APP"
echo "✓ Built $APP"
echo "  Open it from Launchpad, Spotlight ('Gaffer'), or:  open '$APP'"
