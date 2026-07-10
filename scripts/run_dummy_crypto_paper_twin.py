"""Run Dummy's always-on BTC/ETH 15m + hourly paper digital twin.

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
    return {
        "report_name": report.get("report_name"),
        "report_path": str(report_path.resolve()),
        "cycle_id": report.get("cycle_id"),
        "started_at": report.get("started_at"),
        "completed_at": report.get("completed_at"),
        "status": report.get("status"),
        "markets_seen": report.get("markets_seen"),
        "observations_written": report.get("observations_written"),
        "trades_opened": report.get("trades_opened"),
        "settlements_recorded": report.get("settlements_recorded"),
        "maker_updates": report.get("maker_updates"),
        "lanes": lanes,
        "active_recursive_epoch": report.get("active_recursive_epoch"),
        "phase_4_canary_decision": report.get("phase_4_canary_decision"),
        "phase_5_compounding": report.get("phase_5_compounding"),
        "weaknesses": report.get("weaknesses"),
        "recent_explanations": report.get("recent_explanations"),
        "evidence_quarantine": report.get("evidence_quarantine"),
        "authority": report.get("authority"),
        "errors": report.get("errors"),
    }


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
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    descriptor = _acquire_lock(args.lock)
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
        print(json.dumps(summary if args.summary else {
            **report, "report_path": str(report_path.resolve()),
        }, indent=2, sort_keys=True, default=str))
        return 0 if report.get("status") == "CYCLE_OK" else 1
    finally:
        twin.close()
        os.close(descriptor)
        args.lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
