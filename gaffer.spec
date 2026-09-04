# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Gaffer — macOS and Windows.

Produces a self-contained build: Python, the dependencies and the web assets
all ship inside it, so it runs on a machine that has never seen this project.
Anything the app writes goes to the platform's per-user data directory.

PyInstaller cannot cross-compile. The macOS .app is built on macOS and the
Windows .exe on Windows — see .github/workflows/build-windows.yml.
"""
import os
import sys
from pathlib import Path

WINDOWS = sys.platform == 'win32'

ROOT = Path(SPECPATH)
# build-release.sh passes the version it is packaging, so the bundle can
# never disagree with the filename of the archive it ships in.
VERSION = os.environ.get("GAFFER_VERSION", "1.0.0")

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "src" / "fpl" / "webapp" / "static"), "fpl/webapp/static"),
        (str(ROOT / "src" / "fpl" / "templates"), "fpl/templates"),
        (str(ROOT / "defaults"), "defaults"),
    ],
    hiddenimports=[
        "fpl.webapp.server", "fpl.webapp.service", "fpl.webapp.account",
        "fpl.engine.advice", "fpl.engine.budget", "fpl.engine.deadlines",
        "fpl.engine.fixtures", "fpl.engine.form", "fpl.engine.league",
        "fpl.engine.live", "fpl.engine.prices", "fpl.engine.replacements",
        "fpl.engine.squad", "fpl.engine.status", "fpl.engine.wildcard",
        # Only the current platform's webview backend can be imported here.
        *(["webview.platforms.edgechromium", "clr_loader", "pythonnet"]
          if WINDOWS else ["webview.platforms.cocoa"]),
    ],
    excludes=[
        # Build-time only, or unused — keeps the bundle small.
        "PyInstaller", "PIL", "tkinter", "unittest", "pydoc", "doctest",
        "stripe", "gunicorn", "psycopg",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Gaffer",
    console=False,             # no terminal window on either platform
    argv_emulation=False,
    target_arch=None,          # builds for the host arch
    icon=str(ROOT / "build-assets" / ("gaffer.ico" if WINDOWS else "gaffer.icns")),
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Gaffer")

# BUNDLE is macOS-only; on Windows COLLECT above is the finished build.
app = None if WINDOWS else BUNDLE(
    coll,
    name="Gaffer.app",
    icon=str(ROOT / "build-assets" / "gaffer.icns"),
    bundle_identifier="com.gaffer.app",
    version=VERSION,
    info_plist={
        "CFBundleName": "Gaffer",
        "CFBundleDisplayName": "Gaffer",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.sports",
        "NSHumanReadableCopyright": "Independent tool. Not affiliated with the Premier League.",
        # Loopback only — the app talks to its own server on 127.0.0.1.
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    },
)
