"""Fail-closed coordination primitives for destructive ledger maintenance.

The SQLite busy timeout is not a scheduler: it does not prevent retention,
pruning, and vacuum from racing one another, and retrying only ``commit`` does
not help when ``BEGIN IMMEDIATE`` or ``DELETE`` is the statement that loses the
writer lock.  This module provides:

* one process-owned maintenance lease shared by all ledger maintenance jobs;
* bounded acquisition with dead-pid recovery via :mod:`autonomy.proclock`;
* bounded retry of the *contending SQLite statement* only.

The lease is advisory.  Maintenance code must hold it; normal runtime writers
can inspect it and defer starting a new cycle, while SQLite remains the final
source of truth for a writer that was already in flight.
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from autonomy.proclock import acquire_lock, pid_alive, read_lock, release_lock

__all__ = [
    "MaintenanceBusy",
    "MaintenanceLease",
    "acquire_maintenance",
    "maintenance_active",
    "maintenance_lock_path",
    "release_maintenance",
    "retry_sqlite_locked",
]


class MaintenanceBusy(RuntimeError):
    """Another live maintenance owner outlasted the bounded wait."""


@dataclass(frozen=True)
class MaintenanceLease:
    descriptor: int
    path: Path
    operation: str
    acquired_at_monotonic: float
    wait_seconds: float


def maintenance_lock_path(db_path: Path | str) -> Path:
    """Return the lock shared by maintenance jobs for one ledger."""
    return Path(db_path).resolve().parent / "ledger.maintenance.lock"


def _positive_env(name: str, default: float, *, allow_zero: bool = False) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    if allow_zero and value == 0:
        return 0.0
    return value if value > 0 else default


def acquire_maintenance(
    db_path: Path | str,
    operation: str,
    *,
    wait_seconds: float | None = None,
    poll_seconds: float | None = None,
    stale_seconds: float | None = None,
) -> MaintenanceLease:
    """Acquire the ledger's maintenance lease within a wall-clock budget.

    A timeout raises :class:`MaintenanceBusy`; callers must surface that as a
    non-zero scheduled-task result.  A live pid is never displaced, regardless
    of lock age.
    """
    wait = (
        _positive_env("DUMMY_MAINTENANCE_WAIT_S", 300.0, allow_zero=True)
        if wait_seconds is None
        else max(0.0, float(wait_seconds))
    )
    poll = (
        _positive_env("DUMMY_MAINTENANCE_POLL_S", 0.25)
        if poll_seconds is None
        else max(0.01, float(poll_seconds))
    )
    stale = (
        _positive_env("DUMMY_MAINTENANCE_STALE_S", 21_600.0)
        if stale_seconds is None
        else max(1.0, float(stale_seconds))
    )
    target = maintenance_lock_path(db_path)
    started = time.monotonic()
    deadline = started + wait
    while True:
        descriptor = acquire_lock(target, stale_seconds=stale)
        if descriptor is not None:
            # Append parseable metadata without replacing the O_EXCL-created
            # inode. The descriptor remains the proof of ownership.
            safe_operation = "".join(
                char if char.isalnum() or char in "._-" else "_"
                for char in str(operation)
            )[:80]
            os.write(descriptor, f"operation={safe_operation}\n".encode("ascii"))
            return MaintenanceLease(
                descriptor=descriptor,
                path=target,
                operation=safe_operation,
                acquired_at_monotonic=time.monotonic(),
                wait_seconds=time.monotonic() - started,
            )
        if time.monotonic() >= deadline:
            holder = read_lock(target)
            raise MaintenanceBusy(
                "ledger maintenance lease unavailable within "
                f"{wait:g}s; holder_pid={holder.get('pid')!r} "
                f"operation={holder.get('operation')!r}"
            )
        time.sleep(min(poll, max(0.0, deadline - time.monotonic())))


def release_maintenance(lease: MaintenanceLease | None) -> None:
    """Release a lease acquired by :func:`acquire_maintenance`."""
    if lease is not None:
        release_lock(lease.descriptor, lease.path)


def maintenance_active(db_path: Path | str) -> dict[str, Any] | None:
    """Return live-holder metadata, or ``None`` when maintenance is inactive.

    Ambiguous/unparseable locks fail closed and count as active. A lock with a
    definitely dead pid is reported inactive and will be removed by the next
    acquirer.
    """
    target = maintenance_lock_path(db_path)
    if not target.exists():
        return None
    holder = read_lock(target)
    raw_pid = holder.get("pid")
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return {"path": str(target), "pid": raw_pid, "operation": holder.get("operation")}
    if not pid_alive(pid):
        return None
    return {"path": str(target), "pid": pid, "operation": holder.get("operation")}


def retry_sqlite_locked(
    operation: Callable[[], Any],
    *,
    deadline_monotonic: float,
    initial_delay_s: float = 0.1,
    max_delay_s: float = 2.0,
    on_retry: Callable[[int, sqlite3.OperationalError], None] | None = None,
) -> Any:
    """Retry SQLITE_BUSY/LOCKED until ``deadline_monotonic``.

    Non-lock errors are propagated immediately.  The last lock error is also
    propagated, which keeps scheduled-task failure truthful.
    """
    delay = max(0.01, float(initial_delay_s))
    attempts = 0
    while True:
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" not in message and "busy" not in message:
                raise
            attempts += 1
            if time.monotonic() >= deadline_monotonic:
                raise
            if on_retry is not None:
                on_retry(attempts, exc)
            remaining = max(0.0, deadline_monotonic - time.monotonic())
            time.sleep(min(delay, remaining))
            delay = min(delay * 2.0, max(0.01, float(max_delay_s)))
