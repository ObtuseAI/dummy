"""Single-instance locks that a dead process cannot hold.

Every long-running Dummy task guards itself with a lock file so two copies
never run at once. Those guards were age-only: a lock was broken solely when
its mtime aged past a per-task ``stale_seconds`` (7200s for the simulation
trainer, 1800s for the crypto paper twin). Nothing ever asked whether the
process that wrote it still existed.

The consequence was a silent, self-inflicted outage. On 2026-07-24 four lock
files were held by four DEAD pids at once (17060, 37212, 7736, 5312), and
``DummySimulationTrainer`` -- which fires hourly -- had been printing
``SKIPPED_ALREADY_RUNNING`` and exiting **0** since 14:54, so Task Scheduler
showed green while the artifact went stale. An age-only guard turns every crash
into a guaranteed outage of ``stale_seconds``, whether or not anything is
actually running.

The fix is to ask. A lock naming a pid that is not alive is broken IMMEDIATELY;
the age fallback is kept only for locks whose pid is unknown or unparseable, so
the guard still degrades safely rather than never breaking at all.

Deliberately conservative in one direction: pid liveness that cannot be
determined is treated as ALIVE, so an ambiguous probe never lets two writers
run concurrently. Only a definite "that process is gone" breaks a lock.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

__all__ = ["acquire_lock", "read_lock", "pid_alive", "release_lock"]


def pid_alive(pid: int) -> bool:
    """Whether ``pid`` is a live process. Unknown counts as ALIVE.

    Never report a live process as dead: that would let a second writer in.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            # PROCESS_QUERY_LIMITED_INFORMATION; works without elevation.
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                # ERROR_INVALID_PARAMETER (87) is the definite "no such pid".
                return ctypes.windll.kernel32.GetLastError() != 87
            try:
                exit_code = ctypes.c_ulong()
                if ctypes.windll.kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(exit_code)
                ):
                    STILL_ACTIVE = 259
                    return exit_code.value == STILL_ACTIVE
                return True
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:      # noqa: BLE001 -- probe failed, assume alive
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:    # exists, owned by someone else
        return True
    except Exception:          # noqa: BLE001
        return True
    return True


def read_lock(path: Path | str) -> dict[str, Any]:
    """Parse a lock file. Tolerates both formats in use, and empty files.

    ``pid=1234 created=1784922842.0``  (trainer / paper twin)
    ``{"pid": 1234, "at": "..."}``     (live poller)
    """
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return {}
    if not text:
        return {}
    if text.startswith("{"):
        try:
            blob = json.loads(text)
            return blob if isinstance(blob, dict) else {}
        except json.JSONDecodeError:
            return {}
    out: dict[str, Any] = {}
    for token in text.replace("\n", " ").split():
        key, _, value = token.partition("=")
        if key and value:
            out[key] = value
    return out


def _lock_pid(path: Path) -> int | None:
    raw = read_lock(path).get("pid")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def acquire_lock(
    path: Path | str, stale_seconds: float = 7200.0,
) -> int | None:
    """Take the lock, or return None if a LIVE holder has it.

    Breaks the lock when its pid is definitely gone, regardless of age; falls
    back to the age rule only when the pid is unknown.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        pid = _lock_pid(target)
        aged_out = (
            stale_seconds > 0
            and time.time() - target.stat().st_mtime > stale_seconds
        )
        # Known-dead pid breaks the lock at any age; unknown pid falls back to
        # the age rule. A known-LIVE pid is never broken, however old -- a long
        # job is not a dead job, and breaking it would run two writers at once.
        if (pid is not None and not pid_alive(pid)) or (pid is None and aged_out):
            target.unlink(missing_ok=True)
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(
        descriptor,
        f"pid={os.getpid()} created={time.time()}\n".encode(),
    )
    return descriptor


def release_lock(descriptor: int | None, path: Path | str) -> None:
    """Close and remove the lock; safe to call with None."""
    if descriptor is not None:
        try:
            os.close(descriptor)
        except OSError:
            pass
    Path(path).unlink(missing_ok=True)
