"""Self-heal / reconnect loop for the scheduled-task fleet.

The existing watchdog MONITORS (reads artifacts, fires alerts) but is
read-only by contract. This is its active counterpart: every few minutes it
(1) probes real connectivity to the data venues so an internet outage is
visible and timestamped, and (2) restarts any continuously-running task that
has died, so the fleet recovers on its own from a crash, a network blip, or a
resume-from-sleep -- without waiting for a human.

Durability model, together with the task-settings hardening
(scripts/harden_task_durability.ps1):
  * fire-and-exit tasks already "reconnect" every few minutes -- each fire is
    a fresh process that re-establishes every connection -- and now catch up
    missed runs (StartWhenAvailable) and auto-retry crashes (RestartCount);
  * the few continuously-RUNNING tasks (dashboard, crypto paper twin) can die
    silently between triggers, so this loop resurrects them.

Pure decision core (`plan_heals`, `assess`) with injected probe / query /
restart callables, so every path is testable without a socket or a live task.
Fail-open: any probe or restart error degrades to "unknown / skipped", never
an exception into the scheduled fire.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Callable

# Tasks that must be continuously RUNNING (not fire-and-exit); a "Ready" state
# means the process has exited and should be brought back. Only the dashboard
# (a LogonTrigger uvicorn server with no periodic trigger) qualifies -- every
# other Dummy task is fire-and-exit, where "Ready" is the healthy resting
# state, so restarting it would only cause churn.
PERSISTENT_TASKS: tuple[str, ...] = ("DummyDashboard",)
# States we will NOT touch: an operator-disabled task stays disabled.
_DO_NOT_RESTART_STATES = frozenset({"Disabled", "Running"})
# Venue hosts probed for connectivity; reachable-any => internet up.
DEFAULT_PROBE_HOSTS: tuple[tuple[str, int], ...] = (
    ("api.the-odds-api.com", 443),
    ("api.elections.kalshi.com", 443),
    ("site.api.espn.com", 443),
)
PROBE_TIMEOUT = 4.0


@dataclass
class HealReport:
    at: str
    connectivity_ok: bool
    reachable: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    restarted: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "at": self.at,
            "connectivity_ok": self.connectivity_ok,
            "reachable": self.reachable,
            "unreachable": self.unreachable,
            "restarted": self.restarted,
            "checked": self.checked,
            "errors": self.errors,
        }


def _tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_connectivity(
    hosts: tuple[tuple[str, int], ...] = DEFAULT_PROBE_HOSTS,
    *,
    probe: Callable[[str, int, float], bool] = _tcp_reachable,
    timeout: float = PROBE_TIMEOUT,
) -> tuple[bool, list[str], list[str]]:
    """(any_reachable, reachable_hosts, unreachable_hosts)."""
    reachable, unreachable = [], []
    for host, port in hosts:
        ok = False
        try:
            ok = probe(host, port, timeout)
        except Exception:
            ok = False
        (reachable if ok else unreachable).append(host)
    return (len(reachable) > 0, reachable, unreachable)


def plan_heals(
    task_states: dict[str, str],
    *,
    persistent: tuple[str, ...] = PERSISTENT_TASKS,
) -> list[str]:
    """Which persistent tasks need restarting: those present and not currently
    Running and not operator-Disabled. Unknown/absent tasks are left alone."""
    out = []
    for name in persistent:
        state = task_states.get(name)
        if state is None:
            continue
        if state not in _DO_NOT_RESTART_STATES:
            out.append(name)
    return out


def assess(
    *,
    now_iso: str,
    query_states: Callable[[], dict[str, str]],
    restart: Callable[[str], bool],
    hosts: tuple[tuple[str, int], ...] = DEFAULT_PROBE_HOSTS,
    probe: Callable[[str, int, float], bool] = _tcp_reachable,
    persistent: tuple[str, ...] = PERSISTENT_TASKS,
) -> HealReport:
    """One heal pass: probe connectivity, then restart any dead persistent
    task. Fail-open on every step."""
    ok, reachable, unreachable = check_connectivity(hosts, probe=probe)
    report = HealReport(at=now_iso, connectivity_ok=ok,
                        reachable=reachable, unreachable=unreachable)
    try:
        states = query_states()
    except Exception as exc:
        report.errors.append(f"query:{type(exc).__name__}")
        return report
    report.checked = list(persistent)
    for name in plan_heals(states, persistent=persistent):
        try:
            if restart(name):
                report.restarted.append(name)
            else:
                report.errors.append(f"restart_failed:{name}")
        except Exception as exc:
            report.errors.append(f"restart:{name}:{type(exc).__name__}")
    return report
