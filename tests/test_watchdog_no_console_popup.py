"""The watchdog must never flash a console window.

Wave-50 removed the popup spam by running the fleet under pythonw.exe and
spawning console children with CREATE_NO_WINDOW. ``_scheduled_task_inventory``
was missed: it shells out to ``schtasks``, a console application, with no
creationflags. Under pythonw there is no console to inherit, so Windows
allocates a NEW one -- a terminal flashing on every watchdog run, which is one
of the most frequent tasks in the fleet.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from autonomy import watchdog


def test_scheduler_inventory_spawns_schtasks_without_a_console(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    watchdog._scheduled_task_inventory()

    assert captured, "watchdog must have shelled out to the scheduler"
    expected = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert captured["kwargs"].get("creationflags", 0) == expected


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only flag")
def test_create_no_window_is_a_real_flag_on_windows():
    """Guard the guard: a typo'd attribute would silently degrade to 0."""
    assert getattr(subprocess, "CREATE_NO_WINDOW", 0) != 0
