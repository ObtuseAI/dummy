"""Run Dummy's report-only simulation-training curriculum.

This command performs no network calls, opens the autonomy ledger read-only,
and cannot place orders or modify model weights, risk caps, or readiness
evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.simulation_training import (  # noqa: E402
    run_simulation_training,
    write_simulation_training_report,
)


def _acquire_lock(path: Path, stale_seconds: int = 7200) -> int | None:
    """Delegates to autonomy.proclock: a DEAD holder never blocks the task.

    The age-only guard this replaced turned every crash into a guaranteed
    outage of ``stale_seconds`` -- on 2026-07-24 four locks were held by four
    dead pids at once and the hourly simulation trainer had been skipping since
    14:54 while reporting exit 0.
    """
    from autonomy.proclock import acquire_lock

    return acquire_lock(path, stale_seconds)


def _summary(report: dict, path: Path) -> dict:
    forecast = report.get("forecast_training") or {}
    execution = report.get("execution_training") or {}
    compounding = report.get("compounding_stress") or {}
    evolution = report.get("evolution_lab") or {}
    forward = evolution.get("forward_ratchet") or {}
    active = evolution.get("active_research_candidate") or {}
    return {
        "report_name": report.get("report_name"),
        "report_path": str(path.resolve()),
        "created_at": report.get("created_at"),
        "ledger_counts": report.get("ledger_counts"),
        "forecast_status": forecast.get("status"),
        "forecast_oos": forecast.get("challenger_out_of_sample"),
        "incumbent_oos": forecast.get("incumbent_out_of_sample"),
        "execution_status": execution.get("status"),
        "execution_overall": execution.get("overall"),
        "crypto_execution_truth": report.get("crypto_execution_truth"),
        "execution_trace_replay": report.get("execution_trace_replay"),
        "evolution_lab": {
            "generation": evolution.get("generation"),
            "status": evolution.get("status"),
            "evidence": evolution.get("evidence"),
            "population": evolution.get("population"),
            "active_research_candidate": active,
            "forward_ratchet": forward,
            "authority": evolution.get("authority"),
        },
        "improvement_queue": report.get("improvement_queue"),
        "highest_stress_safe_fraction": compounding.get("highest_stress_safe_fraction"),
        "execution_authority": report.get("execution_authority"),
        "evidence_quarantine": report.get("evidence_quarantine"),
    }


def _load_previous_report(out_dir: Path) -> dict | None:
    latest = out_dir / "LATEST.json"
    if not latest.exists():
        return None
    try:
        value = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_runtime_latest(summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("runtime/autonomy/ledger.db"))
    parser.add_argument("--out-dir", type=Path,
                        default=Path("artifacts/dummy/simulation_training"))
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--lock", type=Path,
                        default=Path("runtime/autonomy/simulation_training.lock"))
    args = parser.parse_args()

    descriptor = _acquire_lock(args.lock)
    if descriptor is None:
        print(json.dumps({"status": "SKIPPED_ALREADY_RUNNING", "lock": str(args.lock)}))
        return 0
    try:
        previous_report = _load_previous_report(args.out_dir)
        report = run_simulation_training(
            args.db,
            simulations=max(100, args.simulations),
            previous_report=previous_report,
        )
        path = write_simulation_training_report(report, args.out_dir)
        summary = _summary(report, path)
        _write_runtime_latest(summary, args.lock.parent / "simulation_training_latest.json")
        print(json.dumps(summary if args.summary else {
            **report, "report_path": str(path.resolve()),
        }, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        os.close(descriptor)
        args.lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
