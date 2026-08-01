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
LOG_TAIL_MAX_BYTES = 1_048_576
CONTENT_TIMESTAMP_FIELDS = ("generated_at", "completed_at", "at", "started_at")
RESEARCH_STALL_SECONDS = 48 * 60 * 60
MAX_FUTURE_CLOCK_SKEW_SECONDS = 300.0


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
    content_success_statuses: tuple[str, ...] = ()
    content_failure_statuses: tuple[str, ...] = ()

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
    TaskSpec(
        "DummyLedgerRetention",
        "ledger_retention_stdout.log",
        (),
        86400,
        "ledger retention archive",
        content_success_statuses=("APPLIED",),
        content_failure_statuses=("REFUSED", "FAILED", "ERROR"),
    ),
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

    # schtasks is a console application and the watchdog runs under pythonw.exe,
    # which has no console to inherit -- so Windows allocates a NEW one and a
    # terminal flashes on every run. CREATE_NO_WINDOW suppresses it (0 on
    # non-Windows). Same fix Wave-50 applied to the dashboard's scheduler poll;
    # this caller was missed.
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/V"],
            capture_output=True, text=True, timeout=60, check=True,
            creationflags=no_window,
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


def _read_text_tail(path: Path, max_bytes: int = LOG_TAIL_MAX_BYTES) -> str | None:
    """Read a bounded UTF-8 tail so a runaway stdout log cannot wedge checks."""
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, 2)
            handle.seek(max(0, size - max_bytes))
            return handle.read(max_bytes).decode("utf-8", errors="replace")
    except OSError:
        return None


def _structured_log_records(path: Path) -> list[dict[str, Any]]:
    """Extract concatenated JSON objects from a bounded mixed-text log tail."""
    text = _read_text_tail(path)
    if text is None:
        return []
    try:
        tail_was_truncated = path.stat().st_size > LOG_TAIL_MAX_BYTES
    except OSError:
        return []
    if tail_was_truncated:
        _, separator, text = text.partition("\n")
        if not separator:
            return []
    decoder = json.JSONDecoder()
    records: list[dict[str, Any]] = []
    position = 0
    while position < len(text):
        start = text.find("{", position)
        if start < 0:
            break
        # Producers write each top-level receipt at column zero. Reject braces
        # embedded in tracebacks, exception strings, or nested JSON so text
        # content cannot masquerade as an APPLIED terminal record.
        line_start = text.rfind("\n", 0, start) + 1
        if start != line_start:
            position = start + 1
            continue
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            position = start + 1
            continue
        if isinstance(value, dict):
            records.append(value)
        position = end
    return records


def _record_timestamp(record: dict[str, Any]) -> tuple[float | None, str | None]:
    for field_name in CONTENT_TIMESTAMP_FIELDS:
        epoch = _to_epoch(record.get(field_name))
        if epoch is not None:
            return epoch, field_name
    return None, None


def _content_contract(
    path: Path,
    *,
    success_statuses: tuple[str, ...],
    failure_statuses: tuple[str, ...],
    now_epoch: float,
) -> dict[str, Any]:
    """Evaluate terminal job records without trusting a freshly touched log."""
    successes = {item.upper() for item in success_statuses}
    failures = {item.upper() for item in failure_statuses}
    records = [
        record
        for record in _structured_log_records(path)
        if str(record.get("status") or "").strip()
    ]
    if not records:
        return {
            "last_status": None,
            "last_status_at": None,
            "last_success_at": None,
            "last_success_age_seconds": None,
            "last_success_epoch": None,
            "timestamp_source": "content:no_structured_status",
            "content_failure": False,
            "content_error": "no_structured_status",
            "status_records_seen": 0,
        }

    latest = records[-1]
    latest_status = str(latest["status"]).strip().upper()
    latest_epoch, latest_field = _record_timestamp(latest)
    last_success_epoch: float | None = None
    last_success_field: str | None = None
    for record in reversed(records):
        if str(record.get("status") or "").strip().upper() not in successes:
            continue
        last_success_epoch, last_success_field = _record_timestamp(record)
        if last_success_epoch is not None:
            break

    last_success_age = (
        None
        if last_success_epoch is None
        else round(now_epoch - last_success_epoch, 1)
    )
    content_failure = latest_status in failures
    content_error: str | None = None
    if content_failure:
        content_error = f"terminal_status:{latest_status}"
    elif latest_status not in successes:
        content_error = f"unexpected_terminal_status:{latest_status}"
    elif latest_epoch is None:
        content_error = "latest_success_missing_timestamp"
    elif last_success_age is not None and (
        last_success_age < -MAX_FUTURE_CLOCK_SKEW_SECONDS
    ):
        content_error = "latest_success_timestamp_in_future"

    return {
        "last_status": latest_status,
        "last_status_at": (
            None
            if latest_epoch is None
            else datetime.fromtimestamp(latest_epoch, tz=timezone.utc).isoformat()
        ),
        "last_success_at": (
            None
            if last_success_epoch is None
            else datetime.fromtimestamp(
                last_success_epoch,
                tz=timezone.utc,
            ).isoformat()
        ),
        "last_success_age_seconds": last_success_age,
        "last_success_epoch": last_success_epoch,
        "timestamp_source": (
            f"content:last_success.{last_success_field}"
            if last_success_field
            else "content:no_timestamped_success"
        ),
        "last_status_timestamp_source": latest_field,
        "content_failure": content_failure,
        "content_error": content_error,
        "status_records_seen": len(records),
    }


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
    content: dict[str, Any] | None = None
    if spec.content_success_statuses:
        content = _content_contract(
            path,
            success_statuses=spec.content_success_statuses,
            failure_statuses=spec.content_failure_statuses,
            now_epoch=now_epoch,
        )
        epoch = content["last_success_epoch"]
        source = str(content["timestamp_source"])
    else:
        epoch, source = _artifact_timestamp(path, spec.ts_fields)
    age = None if epoch is None else round(now_epoch - epoch, 1)
    # Fail-closed: a missing artifact or an unreadable timestamp is stale.
    stale = (
        (age is None)
        or (age > spec.threshold_seconds)
        or bool(content and content["content_failure"])
        or bool(content and content["content_error"])
    )
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
    data = _load_json(path) if present and content is None else None
    last_status = (
        content["last_status"]
        if content is not None
        else (
            data.get("status") or data.get("last_status")
            if isinstance(data, dict)
            else None
        )
    )
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
        "last_status_at": content.get("last_status_at") if content else None,
        "last_success_at": content.get("last_success_at") if content else None,
        "last_success_age_seconds": (
            content.get("last_success_age_seconds") if content else None
        ),
        "content_contract": bool(spec.content_success_statuses),
        "content_failure": bool(content and content["content_failure"]),
        "content_error": content.get("content_error") if content else None,
        "status_records_seen": content.get("status_records_seen") if content else None,
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


def _last_forward_issuance(
    observation_path: Path,
    registry_id: str,
) -> tuple[float | None, int]:
    """Return the latest issuance for the current candidate registry."""
    text = _read_text_tail(observation_path)
    if text is None:
        return None, 0
    try:
        if observation_path.stat().st_size > LOG_TAIL_MAX_BYTES:
            _, separator, text = text.partition("\n")
            if not separator:
                return None, 0
    except OSError:
        return None, 0
    latest: float | None = None
    matching_records = 0
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("registry_id") or "") != registry_id:
            continue
        issued_epoch = _to_epoch(payload.get("issued_at"))
        if issued_epoch is None:
            continue
        matching_records += 1
        latest = issued_epoch if latest is None else max(latest, issued_epoch)
    return latest, matching_records


def _research_progress(runtime_dir: Path, now_epoch: float) -> dict[str, Any]:
    """Detect active forward candidates that have made no progress for 48h."""
    cohort_root = runtime_dir / "autoresearch" / "cohorts"
    candidates: list[dict[str, Any]] = []
    invalid_registries: list[str] = []
    for registry_path in sorted(cohort_root.glob("*/forward_registry.json")):
        cohort = registry_path.parent.name
        registry = _load_json(registry_path)
        if not isinstance(registry, dict):
            invalid_registries.append(cohort)
            continue
        active = registry.get("active_candidate")
        if not active:
            continue
        if not isinstance(active, dict):
            candidates.append({
                "cohort": cohort,
                "registry_id": None,
                "candidate_epoch_started_at": None,
                "last_forward_issuance_at": None,
                "progress_age_seconds": None,
                "threshold_seconds": RESEARCH_STALL_SECONDS,
                "matching_observations_in_tail": 0,
                "zero_forward_issuance": True,
                "stalled": True,
                "reason": "invalid_active_candidate",
            })
            continue

        registry_id = str(registry.get("registry_id") or "")
        candidate_epoch = _to_epoch(active.get("epoch_started_at"))
        issued_epoch, matching_records = _last_forward_issuance(
            registry_path.parent / "forward_observations.jsonl",
            registry_id,
        )
        reference_epoch = (
            issued_epoch if issued_epoch is not None else candidate_epoch
        )
        age = (
            None
            if reference_epoch is None
            else round(now_epoch - reference_epoch, 1)
        )
        reason: str | None = None
        stalled = False
        if not registry_id:
            stalled = True
            reason = "missing_registry_id"
        elif reference_epoch is None:
            stalled = True
            reason = "missing_progress_timestamp"
        elif age is not None and age < -MAX_FUTURE_CLOCK_SKEW_SECONDS:
            stalled = True
            reason = "progress_timestamp_in_future"
        elif age is not None and age > RESEARCH_STALL_SECONDS:
            stalled = True
            reason = "no_forward_issuance_within_threshold"

        candidates.append({
            "cohort": cohort,
            "registry_id": registry_id or None,
            "candidate_epoch_started_at": (
                None
                if candidate_epoch is None
                else datetime.fromtimestamp(
                    candidate_epoch,
                    tz=timezone.utc,
                ).isoformat()
            ),
            "last_forward_issuance_at": (
                None
                if issued_epoch is None
                else datetime.fromtimestamp(
                    issued_epoch,
                    tz=timezone.utc,
                ).isoformat()
            ),
            "progress_age_seconds": age,
            "threshold_seconds": RESEARCH_STALL_SECONDS,
            "matching_observations_in_tail": matching_records,
            "zero_forward_issuance": issued_epoch is None,
            "stalled": stalled,
            "reason": reason,
        })

    stalled_candidates = [row for row in candidates if row["stalled"]]
    return {
        "threshold_seconds": RESEARCH_STALL_SECONDS,
        "active_candidate_count": len(candidates),
        "stalled_candidate_count": len(stalled_candidates),
        "candidates": candidates,
        "stalled_candidates": stalled_candidates,
        "invalid_registries": invalid_registries,
    }


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
    sports_freshness: dict[str, Any] | None = None,
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
    research_progress = _research_progress(rd, now)
    research_stalls = [
        row["cohort"]
        for row in research_progress["stalled_candidates"]
    ]

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

    # Sports DATA freshness, distinct from every task check above. Those read
    # artifacts; this reads rows. The 2026-07-24 outage wrote a fresh
    # ingest_log artifact every cycle containing nothing, so artifact-age
    # checks stayed green for eight days. Injected rather than queried here so
    # evaluate_watchdog stays pure and unit runs never touch the lake; None
    # means the caller did not supply it and it contributes nothing.
    sports_stale = list((sports_freshness or {}).get("stale_leagues") or [])

    healthy = not (
        stale_tasks or ledger_over or disk_low or error_streak_alarm
        or kill_present or uncovered_failing or research_stalls
        or sports_stale
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
        "research_progress": research_progress,
        "research_stalls": research_stalls,
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
        "sports_ingest_freshness": sports_freshness,
        "sports_stale_leagues": sports_stale,
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
        if row.get("content_failure"):
            fired.append(emit_alert(
                "WATCHDOG_JOB_REFUSED",
                f"scheduled task {name} ended {row.get('last_status')}; "
                f"last successful APPLIED={row.get('last_success_at')}",
                {"task": row},
                now_iso,
            ))
            continue
        reason = (
            f"content_error={row.get('content_error')}"
            if row.get("content_error")
            else (
                f"{row.get('age_seconds')}s > "
                f"{row.get('threshold_seconds')}s"
            )
        )
        fired.append(emit_alert(
            "WATCHDOG_TASK_STALE",
            f"scheduled task {name} artifact is stale ({reason})",
            {"task": row}, now_iso,
        ))

    prior_research_stalls = set(state.get("research_stalls") or [])
    research_stalls = set(status.get("research_stalls") or [])
    research_rows = (
        status.get("research_progress", {}).get("stalled_candidates", [])
    )
    for cohort in sorted(research_stalls - prior_research_stalls):
        row = next(
            (item for item in research_rows if item.get("cohort") == cohort),
            {"cohort": cohort},
        )
        fired.append(emit_alert(
            "RESEARCH_STALL",
            f"active autoresearch cohort {cohort} has no forward issuance "
            f"within {row.get('threshold_seconds')}s",
            {"research_candidate": row},
            now_iso,
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
    state["research_stalls"] = sorted(research_stalls)
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
