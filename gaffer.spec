# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Gaffer.app.

Produces a self-contained bundle: Python, the dependencies and the web assets
all live inside the .app, so it runs on a Mac that has never seen this project.
Anything the app writes goes to ~/Library/Application Support/Gaffer.
"""
from pathlib import Path

ROOT = Path(SPECPATH)

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
        "webview.platforms.cocoa",
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
    console=False,
    argv_emulation=False,
    target_arch=None,          # builds for the host arch
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Gaffer")

app = BUNDLE(
    coll,
    name="Gaffer.app",
    icon=str(ROOT / "build-assets" / "gaffer.icns"),
    bundle_identifier="com.gaffer.app",
    version="1.0.0",
    info_plist={
        "CFBundleName": "Gaffer",
        "CFBundleDisplayName": "Gaffer",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.sports",
        "NSHumanReadableCopyright": "Independent tool. Not affiliated with the Premier League.",
        # Loopback only — the app talks to its own server on 127.0.0.1.
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    },
)
