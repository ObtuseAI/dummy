"""Bounded runtime controls for the read-only market observer."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Callable


class RequestBudgetExceeded(RuntimeError):
    pass


class CircuitBreakerOpen(RuntimeError):
    pass


class ObserverAlreadyRunning(RuntimeError):
    pass


class RequestRateBudget:
    """Fail-closed fixed-window budget; it never sleeps or retries."""

    def __init__(
        self,
        *,
        max_requests: int = 30,
        window_s: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if (
            not isinstance(max_requests, int)
            or isinstance(max_requests, bool)
            or max_requests <= 0
        ):
            raise ValueError("max_requests must be a positive integer")
        if float(window_s) <= 0:
            raise ValueError("window_s must be positive")
        self.max_requests = max_requests
        self.window_s = float(window_s)
        self.clock = clock or time.monotonic
        self._events: deque[float] = deque()
        self._last_now: float | None = None
        self._lock = threading.Lock()

    def acquire(self) -> None:
        now = float(self.clock())
        with self._lock:
            if self._last_now is not None and now < self._last_now:
                raise RequestBudgetExceeded("rate-budget clock moved backwards")
            self._last_now = now
            cutoff = now - self.window_s
            while self._events and self._events[0] <= cutoff:
                self._events.popleft()
            if len(self._events) >= self.max_requests:
                raise RequestBudgetExceeded("market-observer request budget exhausted")
            self._events.append(now)

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            return {
                "max_requests": self.max_requests,
                "window_s": self.window_s,
                "requests_in_window": len(self._events),
            }


class CircuitBreaker:
    """Provider failure breaker with one bounded half-open probe."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if (
            not isinstance(failure_threshold, int)
            or isinstance(failure_threshold, bool)
            or failure_threshold <= 0
        ):
            raise ValueError("failure_threshold must be a positive integer")
        if float(recovery_timeout_s) <= 0:
            raise ValueError("recovery_timeout_s must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = float(recovery_timeout_s)
        self.clock = clock or time.monotonic
        self._state = "CLOSED"
        self._failure_count = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False
        self._lock = threading.Lock()

    def before_call(self) -> None:
        now = float(self.clock())
        with self._lock:
            if self._state == "OPEN":
                assert self._opened_at is not None
                if now - self._opened_at < self.recovery_timeout_s:
                    raise CircuitBreakerOpen("market-observer provider circuit is open")
                self._state = "HALF_OPEN"
                self._probe_in_flight = True
                return
            if self._state == "HALF_OPEN":
                raise CircuitBreakerOpen("market-observer provider probe is in flight")

    def record_success(self) -> None:
        with self._lock:
            self._state = "CLOSED"
            self._failure_count = 0
            self._opened_at = None
            self._probe_in_flight = False

    def record_failure(self) -> None:
        now = float(self.clock())
        with self._lock:
            if self._state == "HALF_OPEN":
                self._state = "OPEN"
                self._failure_count = self.failure_threshold
                self._opened_at = now
                self._probe_in_flight = False
                return
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = "OPEN"
                self._opened_at = now
                self._probe_in_flight = False

    def cancel_probe(self) -> None:
        """Return an unissued half-open probe to OPEN without a provider call."""
        with self._lock:
            if self._state == "HALF_OPEN" and self._probe_in_flight:
                self._state = "OPEN"
                self._probe_in_flight = False

    def snapshot(self) -> dict[str, int | float | str | None]:
        with self._lock:
            return {
                "state": self._state,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_s": self.recovery_timeout_s,
                "opened_at": self._opened_at,
            }


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        # ``os.kill(pid, 0)`` is not a harmless existence probe on Windows:
        # non-console signals route through TerminateProcess. Query the process
        # handle instead.
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return ctypes.get_last_error() == 5  # access denied implies it exists
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(
                ctypes.c_void_p(handle),
                ctypes.byref(exit_code),
            ):
                return True  # fail closed if the queried handle is indeterminate
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class SingleRunLock:
    """Cross-process ownership lock based on atomic file creation."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._token: str | None = None

    def _create(self) -> None:
        token = uuid.uuid4().hex
        payload = json.dumps(
            {
                "schema_version": 1,
                "pid": os.getpid(),
                "token": token,
                "created_at_s": time.time(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        descriptor = os.open(
            self.path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, payload.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._token = token

    def acquire(self) -> None:
        if self._token is not None:
            raise ObserverAlreadyRunning("this lock instance already owns the run")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._create()
            return
        except FileExistsError:
            pass
        try:
            owner = json.loads(self.path.read_text(encoding="utf-8"))
            owner_pid = int(owner["pid"])
            owner_token = str(owner["token"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ObserverAlreadyRunning(
                "market-observer lock exists but is not safely reclaimable"
            ) from exc
        if owner_token and _pid_is_running(owner_pid):
            raise ObserverAlreadyRunning(
                f"market observer is already running under pid {owner_pid}"
            )

        quarantine = self.path.with_name(
            f"{self.path.name}.stale.{uuid.uuid4().hex}"
        )
        try:
            os.replace(self.path, quarantine)
            self._create()
        except FileExistsError as exc:
            raise ObserverAlreadyRunning(
                "another market observer acquired the run lock"
            ) from exc
        finally:
            quarantine.unlink(missing_ok=True)

    def release(self) -> None:
        if self._token is None:
            return
        try:
            owner = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            self._token = None
            return
        if owner.get("token") == self._token:
            self.path.unlink(missing_ok=True)
        self._token = None

    def __enter__(self) -> "SingleRunLock":
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()
