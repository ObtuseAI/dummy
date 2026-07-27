"""Small cross-platform file lock for durable state transactions."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator


_REGISTRY_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


def _shared_thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve()))
    with _REGISTRY_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


class InterprocessFileLock:
    """Serialize one-byte sidecar locks across threads and processes."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._thread_lock = _shared_thread_lock(self.path)

    @staticmethod
    @contextmanager
    def _lock_handle(handle: BinaryIO) -> Iterator[None]:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(  # type: ignore[attr-defined]
            handle.fileno(),
            fcntl.LOCK_EX,  # type: ignore[attr-defined]
        )
        try:
            yield
        finally:
            fcntl.flock(  # type: ignore[attr-defined]
                handle.fileno(),
                fcntl.LOCK_UN,  # type: ignore[attr-defined]
            )

    @contextmanager
    def hold(self) -> Iterator[None]:
        with self._thread_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                    os.fsync(handle.fileno())
                with self._lock_handle(handle):
                    yield


__all__ = ["InterprocessFileLock"]
