#!/usr/bin/env python
"""Thin launcher for Dummy's canonical local operator board.

Opens the loopback-only web board served by the ``DummyDashboard`` task at
http://127.0.0.1:8787 in a chromeless browser window. It also starts the
single-instance, read-only outcome notifier.

Run windowless with the project Python ``pythonw.exe``. The retired PySide
renderer and its private virtual environment are not required.
"""
from __future__ import annotations

import os
import subprocess
import sys
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


def ensure_server(max_wait_seconds: float = 30.0) -> bool:
    """Start the board task and retry with bounded backoff until it answers."""
    if _serving():
        return True
    # Canonical path: run the fleet-managed dashboard task (its own interpreter).
    try:
        subprocess.run(["schtasks", "/Run", "/TN", "DummyDashboard"],
                       creationflags=_NO_WINDOW, capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        pass
    deadline = time.monotonic() + max(0.0, max_wait_seconds)
    delay = 0.25
    while time.monotonic() < deadline:
        if _serving():
            return True
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(2.0, delay * 1.5)
    return _serving()


def show_startup_error() -> None:
    """Show a windowless-launch-friendly error without opening a dead URL."""
    message = "Dummy Dashboard did not become ready within 30 seconds. Check the DummyDashboard scheduled task."
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "Dummy", 0x10)
    except Exception:  # noqa: BLE001 -- last-ditch user notification
        print(message)


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


def start_notifier() -> None:
    """Start the bounded read-only notification worker without a console."""
    subprocess.Popen(
        [sys.executable, "-m", "desktop.notifier"],
        cwd=REPO,
        creationflags=_NO_WINDOW | _DETACHED,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    if not ensure_server():
        show_startup_error()
        return 1
    open_board()
    try:
        start_notifier()
    except OSError:
        # The board remains useful if Windows notification services are absent.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
