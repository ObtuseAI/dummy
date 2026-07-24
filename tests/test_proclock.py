"""A dead process must not be able to hold a single-instance lock.

Age-only guards turned every crash into a guaranteed outage of stale_seconds.
On 2026-07-24 four locks were held by four dead pids simultaneously and
DummySimulationTrainer -- hourly -- had been printing SKIPPED_ALREADY_RUNNING
and exiting 0 since 14:54, so the scheduler showed green while its artifact
went stale.
"""
from __future__ import annotations

import json
import os
import time

from autonomy.proclock import acquire_lock, pid_alive, read_lock, release_lock


def test_dead_pid_lock_is_broken_immediately(tmp_path):
    lock = tmp_path / "task.lock"
    # A pid that cannot be running, written "just now" so age never breaks it.
    lock.write_text("pid=999999999 created=%f\n" % time.time(), encoding="utf-8")
    descriptor = acquire_lock(lock, stale_seconds=7200)
    assert descriptor is not None, "a dead holder must not block the lock"
    assert read_lock(lock)["pid"] == str(os.getpid())
    release_lock(descriptor, lock)
    assert not lock.exists()


def test_live_pid_lock_is_respected_even_when_fresh(tmp_path):
    lock = tmp_path / "task.lock"
    lock.write_text(f"pid={os.getpid()} created={time.time()}\n", encoding="utf-8")
    assert acquire_lock(lock, stale_seconds=7200) is None


def test_live_pid_lock_is_respected_even_when_aged(tmp_path):
    """Age must not override liveness -- a long job is not a dead job.

    This is the safety direction: breaking a lock a live process still holds
    would run two writers at once.
    """
    lock = tmp_path / "task.lock"
    lock.write_text(f"pid={os.getpid()} created={time.time()}\n", encoding="utf-8")
    os.utime(lock, (time.time() - 99999, time.time() - 99999))
    assert acquire_lock(lock, stale_seconds=1) is None


def test_unparseable_lock_falls_back_to_age(tmp_path):
    """Unknown pid keeps the old behaviour rather than never breaking."""
    lock = tmp_path / "task.lock"
    lock.write_text("garbage", encoding="utf-8")
    os.utime(lock, (time.time() - 99999, time.time() - 99999))
    descriptor = acquire_lock(lock, stale_seconds=10)
    assert descriptor is not None
    release_lock(descriptor, lock)

    lock.write_text("garbage", encoding="utf-8")      # fresh, unknown pid
    assert acquire_lock(lock, stale_seconds=10) is None


def test_reads_both_lock_formats(tmp_path):
    kv = tmp_path / "kv.lock"
    kv.write_text("pid=4321 created=1784922842.06\n", encoding="utf-8")
    assert read_lock(kv)["pid"] == "4321"

    js = tmp_path / "js.lock"
    js.write_text(json.dumps({"pid": 5312, "at": "2026-07-24T22:36:11Z"}), encoding="utf-8")
    assert read_lock(js)["pid"] == 5312

    empty = tmp_path / "empty.lock"
    empty.write_text("", encoding="utf-8")
    assert read_lock(empty) == {}


def test_json_lock_with_dead_pid_is_broken(tmp_path):
    """The live poller writes JSON; it must get the same protection."""
    lock = tmp_path / "poller.lock"
    lock.write_text(json.dumps({"pid": 999999999, "at": "now"}), encoding="utf-8")
    descriptor = acquire_lock(lock, stale_seconds=7200)
    assert descriptor is not None
    release_lock(descriptor, lock)


def test_pid_liveness_is_conservative():
    assert pid_alive(os.getpid()) is True
    assert pid_alive(999999999) is False
    assert pid_alive(0) is False
    assert pid_alive(-1) is False
