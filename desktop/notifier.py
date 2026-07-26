"""Tiny, read-only Windows notification worker for the Dummy desktop launcher.

The worker reads only new rows from the outcome ledger through
``desktop.bet_notify``. It has no Qt dependency, network client, broker import,
or configuration/authority write path.
"""
from __future__ import annotations

import argparse
import base64
import html
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

from desktop import bet_notify

_CREATE_NO_WINDOW = 0x08000000
_ALREADY_EXISTS = 183
_MUTEX_NAME = "Local\\DummyDesktopNotifier"


def acquire_singleton() -> Any | None:
    """Return a process-lifetime Windows mutex, or None if one already exists."""
    if sys.platform != "win32":
        return object()
    import ctypes

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle or ctypes.windll.kernel32.GetLastError() == _ALREADY_EXISTS:
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


def _powershell_toast_script(title: str, body: str) -> str:
    safe_title = html.escape(title, quote=True)
    safe_body = html.escape(body, quote=True)
    return (
        "[Windows.UI.Notifications.ToastNotificationManager, "
        "Windows.UI.Notifications, ContentType=WindowsRuntime] > $null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
        "ContentType=WindowsRuntime] > $null\n"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        "$xml.LoadXml('<toast><visual><binding template=\"ToastGeneric\">"
        f"<text>{safe_title}</text><text>{safe_body}</text>"
        "</binding></visual></toast>')\n"
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)\n"
        "[Windows.UI.Notifications.ToastNotificationManager]"
        "::CreateToastNotifier('Dummy.OperatorBoard').Show($toast)\n"
    )


def show_windows_toast(event: dict[str, Any]) -> bool:
    """Show one native toast without a shell or third-party package."""
    if sys.platform != "win32":
        return False
    script = _powershell_toast_script(
        str(event.get("title") or "Dummy"),
        str(event.get("body") or ""),
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded,
            ],
            creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return True


def process_once(
    last_id: int,
    *,
    emit: Callable[[dict[str, Any]], Any] = show_windows_toast,
) -> int:
    """Emit a bounded batch and persist progress, returning the new cursor."""
    events, new_last = bet_notify.collect_events(last_id)
    for event in events:
        emit(event)
    if new_last != last_id:
        bet_notify.write_state(new_last)
    return new_last


def run(*, poll_seconds: float = 15.0) -> int:
    mutex = acquire_singleton()
    if mutex is None:
        return 0
    bet_notify.seed_silently()
    last_id = bet_notify.read_state()
    try:
        while True:
            last_id = process_once(last_id)
            time.sleep(max(1.0, poll_seconds))
    except KeyboardInterrupt:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    args = parser.parse_args()
    return run(poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
