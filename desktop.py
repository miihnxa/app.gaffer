"""Gaffer — the Mac app shell.

Runs the local Flask server on a loopback port and puts a native WebKit window
in front of it. Nothing is exposed to the network and the app never signs in.
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import webview  # noqa: E402

from fpl.jobs.context import setup_logging  # noqa: E402
from fpl.config import user_dir  # noqa: E402
from fpl.webapp import create_app, free_port  # noqa: E402

log = logging.getLogger(__name__)

APP_NAME = "Gaffer"


def _claim_menu_bar_name() -> None:
    """Without this the menu bar and Cmd-Tab read "Python".

    The name comes from the running process's bundle info, which is the
    Python framework's, not ours — so overwrite it in memory before the
    Cocoa app is created.
    """
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = APP_NAME
            info["CFBundleDisplayName"] = APP_NAME
    except Exception:  # noqa: BLE001 — cosmetic only, never block startup
        log.debug("could not set the bundle display name", exc_info=True)


def main() -> int:
    setup_logging(verbose="--verbose" in sys.argv)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    _claim_menu_bar_name()

    port = free_port()
    app = create_app()

    threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port,
                               debug=False, use_reloader=False, threaded=True),
        daemon=True,
    ).start()

    webview.create_window(
        APP_NAME,
        f"http://127.0.0.1:{port}/",
        width=1280, height=880, min_size=(940, 640),
        frameless=False, easy_drag=False,
        background_color="#140419",
    )
    # Cocoa/WebKit ships with macOS, so there is no runtime to bundle.
    # private_mode defaults to True, which wipes localStorage on every launch.
    # App state lives on disk (webapp/prefs.py), but persisting the web store
    # too keeps scroll position and similar niceties across restarts.
    storage = user_dir() / "webview"
    storage.mkdir(parents=True, exist_ok=True)

    # macOS: WebKit ships with the OS. Windows: WebView2, which ships with
    # Windows 11 and with Edge on Windows 10. Anything else: let pywebview pick.
    gui = {"darwin": "cocoa", "win32": "edgechromium"}.get(sys.platform)

    webview.start(gui=gui, debug="--devtools" in sys.argv,
                  private_mode=False, storage_path=str(storage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
