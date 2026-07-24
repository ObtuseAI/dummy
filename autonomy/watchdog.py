"""Ops watchdog: one aggregate monitor over the whole scheduled-task fleet.

~10 Windows scheduled tasks run the paper-trading system; each writes its own
freshest-artifact JSON but nothing watches them together, so a dead task fails
silently while the dashboard still shows its last (stale) payload as healthy.

This module reads each known task's freshest artifact, compares its age against
2x that task's cadence, and -- together with a handful of environmental floors
(cycle-error streaks, ledger size, kill-file presence, free-disk floor) -- fires
de-duplicated ``autonomy.alerts`` alerts and writes ``watchdog_status.json`` for
the dashboard. Read-only over the runtime tree; it never touches ledger.db and
never controls a task.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime/autonomy")
STATUS_PATH = RUNTIME_DIR / "watchdog_status.json"
WATCHDOG_STATE_PATH = RUNTIME_DIR / "watchdog_state.json"

# Capacity ceiling. Wave-85 (owner decision 2026-07-24): 16.0 -> 20.0 GB,
# taken together with the retention cut from 5 to 3 days, NOT instead of it.
#
# Why 20.0 and not "whatever clears the alarm": the file had plateaued at
# 16.25 GB with freelist ~0 right after a successful retention pass, so the
# 16.0 ceiling had become a permanent red that VACUUM could not clear (0.35 GB
# reclaimed on 2026-07-23). A ceiling that is always breached trains the
# operator to ignore the watchdog, which defeats the tripwire. 20.0 GB sits
# ~23% above the current plateau -- roughly four days of measured gross growth
# (~0.9 GB/day before retention) of headroom -- so it still trips well before
# the independent 10 GB free-disk floor on a 145 GB volume, and it still trips
# on genuinely unbounded growth rather than on steady state.
#
# The 3-day retention cut is expected to pull the steady state well below this;
# if the measured plateau settles far under 20.0, lower this to match rather
# than leaving slack that hides real growth.
#
# UNITS: decimal GB (bytes / 1e9), matching ``_ledger_size_gb`` below. The
# heartbeat's ledger_health reports GiB (bytes / 1024**3) instead, so the two
# operator surfaces differ by ~7% for the same file -- 16.20 GB reads as 15.13
# GiB. Both are emitted with explicit names rather than silently reconciled:
# changing which basis the threshold compares would move the alarm point, and
# that is a capacity decision, not a units cleanup.
DEFAULT_LEDGER_MAX_GB = 20.0
DEFAULT_DISK_FLOOR_GB = 10.0
DEFAULT_ERROR_STREAK_THRESHOLD = 3
STALE_MULTIPLIER = 2.0


@dataclass(frozen=True)
class TaskSpec:
    """One scheduled task -> its freshest artifact + expected cadence."""

    name: str
    artifact: str
    ts_fields: tuple[str, ...]
    cadence_seconds: float
    role: str = ""
    stale_multiplier: float = STALE_MULTIPLIER
    authoritative: bool = True
    requires_seed_binding: bool = False

    @property
    def threshold_seconds(self) -> float:
        return self.cadence_seconds * self.stale_multiplier


# Cadences mirror scripts/install_*_task.ps1 (minutes -> seconds; daily -> 86400).
DEFAULT_TASKS: list[TaskSpec] = [
    # Wave-83: corrected from "retired non-authoritative". The shadow daemon
    # runs the full paper cycle and the auto-promotion runner treats its
    # heartbeat as a mandatory rail (auto_promotion_runner.py) — the two
    # labels contradicted each other, and the promotion rail is the one that
    # bites, so the watchdog now agrees with it.
    TaskSpec(
        "DummyShadowPredator",
        "heartbeat.json",
        ("last_cycle_at",),
        600,
        "authoritative shadow cycle (paper evidence engine; promotion rail input)",
    ),
    TaskSpec(
        "DummySportsModelSeed",
        "sports_model_seed_authoritative_status.json",
        ("last_success_at",),
        300,
        "authoritative sports model seed",
        requires_seed_binding=True,
    ),
    TaskSpec(
        "DummySportsBoardRefresh",
        "bet_board_display.json",
        ("generated_at",),
        300,
        "authoritative sports quote board",
    ),
    TaskSpec(
        "DummyMispricingMonitor",
        "mispricing_monitor_latest.json",
        ("generated_at",),
        300,
        "legacy mispricing research (non-authoritative)",
        authoritative=False,
    ),
    TaskSpec(
        "DummyCryptoPaperTwin",
        "crypto_paper_twin_latest.json",
        ("completed_at", "started_at"),
        300,
        "retired crypto paper research (non-authoritative)",
        authoritative=False,
    ),
    TaskSpec(
        "DummySportsSimulation",
        "sports_simulation_latest.json",
        ("completed_at", "started_at"),
        600,
        "sports research simulation (non-authoritative)",
        authoritative=False,
    ),
    TaskSpec("DummySimulationTrainer", "simulation_training_latest.json", ("created_at",), 3600, "simulation trainer"),
    TaskSpec("DummyStrategyMiner", "strategy_mining_report.json", ("generated_at",), 86400, "strategy miner"),
    TaskSpec("DummyReadinessReport", "readiness_report.json", ("generated_at",), 86400, "readiness report"),
    # Wave-83 fleet expansion (audit: 9 specs vs ~43 live tasks). Artifact-
    # backed tasks get real specs; everything else is surfaced through the
    # scheduler inventory (see _scheduled_task_inventory) so nothing can die
    # invisibly again. stdout logs count via file mtime — cheap but honest.
    TaskSpec("DummyVnextShadow", "vnext_shadow_status.json", ("at",), 900, "vNext shadow organism"),
    TaskSpec("DummyDashboardSnapshot", "latest_dashboard_snapshot.json", ("generated_at",), 1200, "dashboard snapshot"),
    TaskSpec("DummyWeightsRecal", "last_recalibration.json", ("at",), 21600, "out-of-band weights recalibration"),
    TaskSpec("DummyBacktestReport", "latest_backtest_summary.json", ("generated_at",), 43200, "backtest diagnostics"),
    TaskSpec("DummySelfImprovement", "self_improvement_report.json", ("generated_at",), 86400, "nightly self-improvement chain"),
    TaskSpec("DummyHealer", "healer_stdout.log", (), 300, "self-heal loop"),
    TaskSpec("DummyLivePoller", "live_poller_status.json", ("at",), 300, "live game poller"),
    TaskSpec("DummyCryptoHorizonEvidence", "crypto_horizon_evidence_stdout.log", (), 7200, "crypto horizon evidence"),
    TaskSpec("DummyLedgerRetention", "ledger_retention_stdout.log", (), 86400, "ledger retention archive"),
    TaskSpec("DummyLedgerPrune", "signal_prune_stdout.log", (), 86400, "ledger signal prune"),
    TaskSpec("DummyLogRotation", "log_rotation_stdout.log", (), 86400, "log rotation"),
    TaskSpec("DummyLiveAccountSnapshot", "live_account_snapshot.json", ("generated_at",), 900, "live account snapshot"),
    # Registered 2026-07-24 after the audit found the lab unscheduled for 9
    # days. Read-only over the ledger, no network, no promotion authority.
    TaskSpec("DummyAutoresearch", "autoresearch_status.json", ("last_success_at",), 3600, "bounded real-ledger autoresearch"),
    # Wave-85: both were in uncovered_tasks while being killed at their time
    # limits every run, so the self-tuner and the walk-forward evaluation could
    # rot indefinitely without a single alarm. The per-league DummyWF_<league>
    # tasks share one artifact, so they are covered by the scheduler inventory
    # (which now treats a time-limit kill as failing) plus this freshness spec.
    TaskSpec("DummyTune", "sports_tuned_params.json", ("generated_at",), 86400, "sports self-tuner"),
    TaskSpec("DummyWF", "sports_walk_forward.json", ("generated_at",), 86400, "sports walk-forward evaluation"),
]

# Scheduler results that do not indicate failure: 0 success, 0x41301 running,
# 0x41303 never-yet-run.
#
# Wave-85 removed 0x41306 / 267014 (SCHED_S_TASK_TERMINATED). It was described
# as "terminated-by-user", but Task Scheduler returns the SAME code when it
# kills a task that outran its ExecutionTimeLimit -- so treating it as OK made
# every time-limit kill invisible. DummyTune (PT1H) and DummyWF_ncaamb (PT20M)
# had both been killed on every run while reporting failing=False, which is why
# four leagues had never been tuned even once and ncaamb never persisted a full
# walk-forward. An operator-terminated task is incomplete too, so surfacing it
# is right in both readings of the code.
_SCHEDULER_OK_RESULTS = {0, 267009, 267011}


def _scheduled_task_inventory(prefix: str = "Dummy") -> list[dict[str, Any]]:
    """Best-effort read-only scheduler inventory (Windows schtasks CSV).

    Returns one row per matching task: name, scheduler status, last run time,
    and last result. Empty on any failure or off-Windows — the watchdog's
    artifact specs still work without it.
    """
    import csv
    import io
    import subprocess

    try:
        out = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/V"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    try:
        for row in csv.DictReader(io.StringIO(out)):
            name = str(row.get("TaskName") or "").lstrip("\\")
            if not name.startswith(prefix):
                continue
            try:
                last_result: int | None = int(str(row.get("Last Result") or "").strip())
            except ValueError:
                last_result = None
            rows.append({
                "task_name": name,
                "scheduler_status": row.get("Status") or "",
                "last_run_time": row.get("Last Run Time") or "",
                "last_result": last_result,
                "failing": last_result is not None and last_result not in _SCHEDULER_OK_RESULTS,
            })
    except Exception:
        return []
    # /V repeats tasks per trigger; keep first occurrence per name.
    seen: set[str] = set()
    unique = []
    for row in rows:
        if row["task_name"] in seen:
            continue
        seen.add(row["task_name"])
        unique.append(row)
    return unique


def _now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _to_epoch(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _artifact_timestamp(path: Path, ts_fields: tuple[str, ...]) -> tuple[float | None, str]:
    """Best available timestamp for one artifact: a named field, else mtime."""
    data = _load_json(path)
    if isinstance(data, dict):
        for field_name in ts_fields:
            epoch = _to_epoch(data.get(field_name))
            if epoch is not None:
                return epoch, field_name
    if path.exists():
        try:
            return path.stat().st_mtime, "file_mtime"
        except OSError:
            return None, "unavailable"
    return None, "missing"


def evaluate_task(spec: TaskSpec, runtime_dir: Path, now_epoch: float) -> dict[str, Any]:
    path = runtime_dir / spec.artifact
    present = path.exists()
    epoch, source = _artifact_timestamp(path, spec.ts_fields)
    age = None if epoch is None else round(now_epoch - epoch, 1)
    # Fail-closed: a missing artifact or an unreadable timestamp is stale.
    stale = (age is None) or (age > spec.threshold_seconds)
    integrity_status = "NOT_REQUIRED"
    integrity_error: str | None = None
    binding: dict[str, Any] | None = None
    if spec.requires_seed_binding:
        try:
            from autonomy.sports_board_refresh import (
                validate_authoritative_model_seed_binding,
            )

            binding = validate_authoritative_model_seed_binding(
                seed_path=runtime_dir / "sports_model_seed_authoritative.json",
                status_path=path,
                now=datetime.fromtimestamp(now_epoch, tz=timezone.utc),
            )
            integrity_status = "VALID"
        except Exception as exc:
            # A fresh-looking status timestamp is not authority without an
            # exact byte-hash/run binding to the producer's seed artifact.
            stale = True
            integrity_status = "INVALID"
            integrity_error = f"{type(exc).__name__}: {exc}"
    data = _load_json(path) if present else None
    last_status = data.get("status") or data.get("last_status") if isinstance(data, dict) else None
    return {
        "task_name": spec.name,
        "role": spec.role,
        "authoritative": spec.authoritative,
        "artifact": spec.artifact,
        "present": present,
        "timestamp_source": source,
        "age_seconds": age,
        "cadence_seconds": spec.cadence_seconds,
        "threshold_seconds": spec.threshold_seconds,
        "stale": bool(stale),
        "last_status": last_status,
        "integrity_status": integrity_status,
        "integrity_error": integrity_error,
        "binding": binding,
    }


def _cycle_error_streak(runtime_dir: Path, limit: int = 50) -> tuple[int, str | None]:
    """Trailing run of consecutive CYCLE_ERROR statuses in cycles.jsonl."""
    path = runtime_dir / "cycles.jsonl"
    if not path.exists():
        return 0, None
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return 0, None
    streak = 0
    latest: str | None = None
    for line in reversed(lines[-limit:]):
        try:
            status = str(json.loads(line).get("status", ""))
        except Exception:
            break
        if latest is None:
            latest = status
        if status.startswith("CYCLE_ERROR"):
            streak += 1
        else:
            break
    return streak, latest


def _ledger_size_gb(runtime_dir: Path) -> float | None:
    path = runtime_dir / "ledger.db"
    try:
        return round(path.stat().st_size / 1e9, 3)
    except OSError:
        return None


def _disk_free_gb(runtime_dir: Path) -> float | None:
    try:
        return round(shutil.disk_usage(str(runtime_dir)).free / 1e9, 2)
    except OSError:
        return None


def evaluate_watchdog(
    runtime_dir: Path | None = None,
    *,
    now_epoch: float | None = None,
    tasks: list[TaskSpec] | None = None,
    ledger_max_gb: float = DEFAULT_LEDGER_MAX_GB,
    disk_floor_gb: float = DEFAULT_DISK_FLOOR_GB,
    error_streak_threshold: int = DEFAULT_ERROR_STREAK_THRESHOLD,
    kill_path: Path | None = None,
    inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the full watchdog status (pure; writes nothing, fires nothing)."""
    rd = runtime_dir or RUNTIME_DIR
    now = now_epoch if now_epoch is not None else _now_epoch()
    specs = tasks if tasks is not None else DEFAULT_TASKS

    task_rows = [evaluate_task(spec, rd, now) for spec in specs]
    streak, latest_status = _cycle_error_streak(rd)
    ledger_gb = _ledger_size_gb(rd)
    disk_gb = _disk_free_gb(rd)
    kill = kill_path or (rd / "KILL")
    kill_present = kill.exists()

    stale_tasks = [
        row["task_name"]
        for row in task_rows
        if row["stale"] and row["authoritative"]
    ]
    observational_stale_tasks = [
        row["task_name"]
        for row in task_rows
        if row["stale"] and not row["authoritative"]
    ]
    ledger_over = ledger_gb is not None and ledger_gb > ledger_max_gb
    disk_low = disk_gb is not None and disk_gb < disk_floor_gb
    error_streak_alarm = streak >= error_streak_threshold

    # Wave-83: the fleet is larger than the artifact-backed spec table, and a
    # task outside it used to be able to die invisibly. Surface every Dummy*
    # scheduled task; ones without a spec are listed as uncovered, and an
    # uncovered task with a failing scheduler result degrades health.
    if inventory is None:
        # Injectable for tests; env-gated so unit runs never shell out to the
        # scheduler (conftest exports DUMMY_WATCHDOG_INVENTORY=0).
        if os.environ.get("DUMMY_WATCHDOG_INVENTORY", "1") == "1":
            inventory = _scheduled_task_inventory()
        else:
            inventory = []
    covered = {spec.name for spec in specs}
    uncovered = [row for row in inventory if row["task_name"] not in covered]
    # The watchdog must not grade its OWN exit code. run_dummy_watchdog.py
    # exits nonzero when the FLEET is unhealthy, so that result reports the
    # verdict rather than the watchdog's health. Counting it created a latch:
    # anything unhealthy -> watchdog exits 1 -> the inventory reads DummyWatchdog
    # as failing -> uncovered_failing is non-empty -> unhealthy, forever, even
    # after the original cause was fixed. It surfaced the moment Wave-85 stopped
    # treating a terminated task as OK, because the watchdog had previously been
    # caught mid-run (267009) more often than it was seen completing.
    uncovered_failing = [
        row["task_name"] for row in uncovered
        if row["failing"] and row["task_name"] != "DummyWatchdog"
    ]

    healthy = not (
        stale_tasks or ledger_over or disk_low or error_streak_alarm
        or kill_present or uncovered_failing
    )
    return {
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "healthy": healthy,
        "tasks": task_rows,
        "stale_tasks": stale_tasks,
        "observational_stale_tasks": observational_stale_tasks,
        "scheduler_inventory": inventory,
        "uncovered_tasks": [row["task_name"] for row in uncovered],
        "uncovered_failing_tasks": uncovered_failing,
        "cycle_error_streak": streak,
        "cycle_error_streak_threshold": error_streak_threshold,
        "latest_cycle_status": latest_status,
        "ledger_size_gb": ledger_gb,
        "ledger_size_gib": (
            None if ledger_gb is None else round(ledger_gb * 1e9 / 1024 ** 3, 3)
        ),
        "ledger_max_gb": ledger_max_gb,
        "ledger_size_units": "decimal_gb_bytes_over_1e9",
        "ledger_over_threshold": ledger_over,
        "disk_free_gb": disk_gb,
        "disk_floor_gb": disk_floor_gb,
        "disk_below_floor": disk_low,
        "kill_file_present": kill_present,
    }


def _load_state(path: Path) -> dict[str, Any]:
    data = _load_json(path)
    return data if isinstance(data, dict) else {}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def fire_watchdog_alerts(
    status: dict[str, Any],
    *,
    now_iso: str | None = None,
    state_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Emit rising-edge, de-duplicated alerts for the watchdog status.

    An alert fires when a condition newly becomes true; it does not re-fire
    while the condition stays true, and its latch clears when it recovers.
    """
    from autonomy.alerts import emit_alert

    sp = state_path or WATCHDOG_STATE_PATH
    state = _load_state(sp)
    prior_stale = set(state.get("stale_tasks") or [])
    fired: list[dict[str, Any]] = []

    stale_now = set(status.get("stale_tasks") or [])
    for name in sorted(stale_now - prior_stale):
        row = next((r for r in status["tasks"] if r["task_name"] == name), {})
        fired.append(emit_alert(
            "WATCHDOG_TASK_STALE",
            f"scheduled task {name} artifact is stale "
            f"({row.get('age_seconds')}s > {row.get('threshold_seconds')}s)",
            {"task": row}, now_iso,
        ))

    def _edge(key: str, active: bool, kind: str, message: str, detail: dict[str, Any]) -> None:
        if active and not state.get(key):
            fired.append(emit_alert(kind, message, detail, now_iso))
        state[key] = active

    _edge(
        "error_streak_alarm", status.get("cycle_error_streak", 0) >= status.get("cycle_error_streak_threshold", 3),
        "WATCHDOG_CYCLE_ERROR_STREAK",
        f"{status.get('cycle_error_streak')} consecutive cycle errors "
        f"(latest {status.get('latest_cycle_status')})",
        {"streak": status.get("cycle_error_streak"), "latest": status.get("latest_cycle_status")},
    )
    _edge(
        "ledger_over", bool(status.get("ledger_over_threshold")),
        "WATCHDOG_LEDGER_SIZE",
        f"ledger.db {status.get('ledger_size_gb')} GB exceeds {status.get('ledger_max_gb')} GB ceiling",
        {"ledger_size_gb": status.get("ledger_size_gb"), "ledger_max_gb": status.get("ledger_max_gb")},
    )
    _edge(
        "kill_present", bool(status.get("kill_file_present")),
        "WATCHDOG_KILL_FILE",
        "operator KILL file present -- trading is halted",
        {},
    )
    _edge(
        "disk_low", bool(status.get("disk_below_floor")),
        "WATCHDOG_DISK_FLOOR",
        f"free disk {status.get('disk_free_gb')} GB below floor {status.get('disk_floor_gb')} GB",
        {"disk_free_gb": status.get("disk_free_gb"), "disk_floor_gb": status.get("disk_floor_gb")},
    )

    state["stale_tasks"] = sorted(stale_now)
    _save_state(sp, state)
    return fired


def write_status(status: dict[str, Any], path: Path | None = None) -> Path:
    target = path or STATUS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    return target


def run_watchdog(
    runtime_dir: Path | None = None,
    *,
    now_epoch: float | None = None,
    emit_alerts: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate, persist ``watchdog_status.json``, and fire de-duped alerts."""
    rd = runtime_dir or RUNTIME_DIR
    status = evaluate_watchdog(rd, now_epoch=now_epoch, **kwargs)
    write_status(status, rd / STATUS_PATH.name)
    if emit_alerts and os.environ.get("DUMMY_WATCHDOG_ALERTS", "1") == "1":
        try:
            fire_watchdog_alerts(status, state_path=rd / WATCHDOG_STATE_PATH.name)
        except Exception:
            pass  # alerting must never wedge the watchdog
    return status
