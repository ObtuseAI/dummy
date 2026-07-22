"""Run Dummy's exact BTC/ETH/SOL multi-horizon paper digital twin.

This process uses public GET data only. It has no broker, credential, live
session, production-ledger write, execution, or capital authority.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.crypto_paper_twin import (  # noqa: E402
    CryptoPaperTwin,
    PaperTwinLedger,
    write_paper_twin_report,
)
from autonomy.session import PAPER_RESULTS_AUTHORITY  # noqa: E402


def _acquire_lock(path: Path, stale_seconds: int = 1800) -> int | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and time.time() - path.stat().st_mtime > stale_seconds:
        path.unlink(missing_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(descriptor, f"pid={os.getpid()} created={time.time()}\n".encode())
    return descriptor


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _summary(report: dict, report_path: Path) -> dict:
    lanes = report.get("lanes") or {}
    target_selection = report.get("price_target_selection") or {}
    rejection_regret = target_selection.get("rejection_regret") or {}
    return {
        "report_name": report.get("report_name"),
        "report_path": str(report_path.resolve()),
        "paper_mode": "LIVE_PUBLIC_READ_ONLY_SIMULATION",
        "cycle_id": report.get("cycle_id"),
        "started_at": report.get("started_at"),
        "completed_at": report.get("completed_at"),
        "status": report.get("status"),
        "markets_seen": report.get("markets_seen"),
        "observations_written": report.get("observations_written"),
        "trades_opened": report.get("trades_opened"),
        "settlements_recorded": report.get("settlements_recorded"),
        "forced_crypto_trades_recorded": report.get(
            "forced_crypto_trades_recorded"
        ),
        "forced_crypto_settlements_recorded": report.get(
            "forced_crypto_settlements_recorded"
        ),
        "target_candidate_forecasts_recorded": report.get(
            "target_candidate_forecasts_recorded"
        ),
        "target_candidate_settlements_recorded": report.get(
            "target_candidate_settlements_recorded"
        ),
        "maker_updates": report.get("maker_updates"),
        "lanes": lanes,
        "cohorts": report.get("cohorts"),
        "vertical_timeframes": report.get("vertical_timeframes"),
        "assets_by_vertical": report.get("assets_by_vertical"),
        "universe_policy": report.get("universe_policy"),
        "horizon_execution_contract": report.get("horizon_execution_contract"),
        "active_recursive_epoch": report.get("active_recursive_epoch"),
        "hourly_calibration": report.get("hourly_calibration"),
        "target_candidate_counts": rejection_regret.get("counts"),
        "forced_crypto_coverage": report.get("forced_crypto_coverage"),
        "throughput": {
            key: (report.get("phase_3_execution") or {}).get(f"throughput_{key}")
            for key in ("classes", "actionable", "expected", "legend")
        },
        "weaknesses": list(report.get("weaknesses") or [])[:20],
        "evidence_quarantine": report.get("evidence_quarantine"),
        "authority": report.get("authority"),
        "errors": report.get("errors"),
    }


def _console_summary(summary: dict) -> dict:
    authority = summary.get("authority") or {}
    return {
        "paper_mode": summary.get("paper_mode"),
        "cycle_id": summary.get("cycle_id"),
        "started_at": summary.get("started_at"),
        "completed_at": summary.get("completed_at"),
        "status": summary.get("status"),
        "markets_seen": summary.get("markets_seen"),
        "observations_written": summary.get("observations_written"),
        "trades_opened": summary.get("trades_opened"),
        "settlements_recorded": summary.get("settlements_recorded"),
        "forced_crypto_trades_recorded": summary.get(
            "forced_crypto_trades_recorded"
        ),
        "forced_crypto_settlements_recorded": summary.get(
            "forced_crypto_settlements_recorded"
        ),
        "target_candidate_forecasts_recorded": summary.get(
            "target_candidate_forecasts_recorded"
        ),
        "target_candidate_settlements_recorded": summary.get(
            "target_candidate_settlements_recorded"
        ),
        "broker_contacted": bool(authority.get("broker_contacted")),
        "execution_authority": bool(authority.get("execution_authority")),
        "capital_authority": bool(authority.get("capital_authority")),
        "errors": summary.get("errors") or [],
    }


def _append_rotating_jsonl(
    path: Path,
    row: dict,
    *,
    max_bytes: int = 5 * 1024 * 1024,
    backups: int = 3,
) -> None:
    """Append one compact scheduler record with a bounded local footprint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= max(1024, int(max_bytes)):
        for index in range(max(1, int(backups)) - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            destination = path.with_name(f"{path.name}.{index + 1}")
            if source.exists():
                os.replace(source, destination)
        os.replace(path, path.with_name(f"{path.name}.1"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=Path("runtime/autonomy/crypto_paper_twin.db"),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("artifacts/dummy/crypto_paper_twin"),
    )
    parser.add_argument(
        "--lock", type=Path, default=Path("runtime/autonomy/crypto_paper_twin.lock"),
    )
    parser.add_argument("--lock-stale-seconds", type=int, default=1800)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    if PAPER_RESULTS_AUTHORITY == "RETIRED_NON_AUTHORITATIVE":
        print(json.dumps({
            "status": PAPER_RESULTS_AUTHORITY,
            "paper_mode": "RETIRED",
            "trades_opened": 0,
            "settlements_recorded": 0,
            "broker_contacted": False,
            "execution_authority": False,
            "capital_authority": False,
            "note": "Paper-twin production is retired; raw history remains audit-only.",
        }, sort_keys=True))
        return 0

    descriptor = _acquire_lock(
        args.lock,
        stale_seconds=max(60, int(args.lock_stale_seconds)),
    )
    if descriptor is None:
        print(json.dumps({"status": "SKIPPED_ALREADY_RUNNING", "lock": str(args.lock)}))
        return 0
    ledger = PaperTwinLedger(args.db)
    twin = CryptoPaperTwin(ledger=ledger)
    try:
        report = twin.run_cycle()
        report_path = write_paper_twin_report(report, args.out_dir)
        summary = _summary(report, report_path)
        _atomic_json(args.lock.parent / "crypto_paper_twin_latest.json", summary)
        console = _console_summary(summary)
        if args.log is not None:
            _append_rotating_jsonl(args.log, console)
        print(json.dumps(console if args.summary else {
            **report, "report_path": str(report_path.resolve()),
        }, indent=None if args.summary else 2, sort_keys=True, default=str))
        return 0 if report.get("status") == "CYCLE_OK" else 1
    finally:
        twin.close()
        os.close(descriptor)
        args.lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
