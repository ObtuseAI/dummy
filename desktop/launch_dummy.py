#!/usr/bin/env python
"""All-in-one Dummy launcher.

Opens the elevated **Dummy Totalizator** command board (the live web UI served
by the ``DummyDashboard`` task at http://127.0.0.1:8787) as a chromeless
desktop-app window -- no browser chrome, its own taskbar entry, the branded
icon on the shortcut. Ensures the board server is actually up first (nudges the
scheduled task, waits briefly), so a single click always lands on the live UI.

Run windowless via the desktop venv's ``pythonw.exe`` (stdlib only -- needs none
of dummy's own deps). Console subprocesses use CREATE_NO_WINDOW so nothing
flashes.
"""
from __future__ import annotations

import os
import subprocess
import time
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8787/"
REPO = Path(__file__).resolve().parent.parent
ICON = REPO / "desktop" / "assets" / "dummy.ico"
_NO_WINDOW = 0x08000000        # subprocess.CREATE_NO_WINDOW
_DETACHED = 0x00000008         # subprocess.DETACHED_PROCESS


def _serving(timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=timeout) as r:
            return 200 <= r.status < 500
    except Exception:  # noqa: BLE001 -- any failure => treat as down
        return False


def ensure_server() -> None:
    """Best-effort: make sure the board server answers before we open it."""
    if _serving():
        return
    # Canonical path: run the fleet-managed dashboard task (its own interpreter).
    try:
        subprocess.run(["schtasks", "/Run", "/TN", "DummyDashboard"],
                       creationflags=_NO_WINDOW, capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        pass
    for _ in range(24):        # up to ~12s for uvicorn to bind
        if _serving():
            return
        time.sleep(0.5)


def open_board() -> None:
    """Open the board as a chromeless app window (Edge, then Chrome, then default)."""
    app_dir = str(Path.home() / ".dummy-desktop" / "app")  # isolated app profile
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(exe):
            subprocess.Popen(
                [exe, f"--app={URL}", f"--user-data-dir={app_dir}",
                 "--no-first-run", "--no-default-browser-check",
                 "--window-size=1500,950", "--window-position=140,80"],
                creationflags=_NO_WINDOW | _DETACHED)
            return
    os.startfile(URL)  # last resort: default browser, normal tab


def main() -> int:
    ensure_server()
    open_board()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
