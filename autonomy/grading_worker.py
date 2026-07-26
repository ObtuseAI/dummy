"""Supervised, public-read-only forecast settlement grading.

The normal autonomy cycle performs the same work opportunistically.  This
one-shot worker makes backlog coverage independently schedulable and
observable without importing an executor, broker client, authority state, or
order API.  Atomic settlement claims ensure an overlapping daemon and worker
cannot grade the same outcome twice.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from autonomy.correlation import group_key
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.reconciler import Reconciler, default_fetch_settled_page

GRADING_WORKER_VERSION = "dummy-grading-worker-v1"
DEFAULT_RECEIPT_PATH = Path("runtime/autonomy/grading_worker_latest.json")
DEFAULT_MIN_ATTEMPT_COVERAGE = 0.95


@dataclass(frozen=True)
class GradingPassResult:
    receipt: dict[str, Any]
    exit_code: int


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode(
                "utf-8"
            )
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _coverage_passes(
    coverage: dict[str, Any],
    *,
    minimum_attempt_coverage: float,
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    ratio = coverage.get("attempt_coverage_ratio")
    eligible = coverage.get("eligible_unsettled_forecasts")
    if eligible == 0:
        return True, blockers
    if ratio is None or float(ratio) < minimum_attempt_coverage:
        blockers.append(
            "attempt_coverage_below_"
            f"{minimum_attempt_coverage:.3f}"
        )
    if coverage.get("pagination_truncated"):
        blockers.append("settled_listing_pagination_truncated")
    if coverage.get("listing_errors"):
        blockers.append("settled_listing_errors")
    return not blockers, blockers


def run_grading_pass(
    ledger: AutonomyLedger,
    *,
    fetch_settled_page: Callable[..., dict[str, Any]] = default_fetch_settled_page,
    receipt_path: Path | None = DEFAULT_RECEIPT_PATH,
    lookback_hours: float = 24.0 * 7.0,
    max_pages_per_series: int = 20,
    minimum_attempt_coverage: float = DEFAULT_MIN_ATTEMPT_COVERAGE,
    now: datetime | None = None,
) -> GradingPassResult:
    """Settle and grade the current ungraded forecast backlog once.

    The requested series are derived from the backlog itself rather than a
    mutable scanner watchlist.  A removed or newly introduced series therefore
    remains gradeable until its recent forecast window expires.
    """
    if not 0.0 <= float(minimum_attempt_coverage) <= 1.0:
        raise ValueError("minimum_attempt_coverage must be in [0, 1]")
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")
    if max_pages_per_series < 1:
        raise ValueError("max_pages_per_series must be positive")

    generated_at = (now or datetime.now(timezone.utc)).astimezone(
        timezone.utc
    ).isoformat()
    backlog = sorted(set(ledger.unsettled_forecast_markets()))
    series = sorted({ticker.split("-", 1)[0] for ticker in backlog if ticker})
    previous_weights = ledger.all_weights()
    reconciler = Reconciler(
        ledger,
        fetch_settled_page=fetch_settled_page,
    )
    if backlog:
        settlements = reconciler.reconcile_forecast_settlements(
            series,
            lookback_hours=lookback_hours,
            max_pages_per_series=max_pages_per_series,
        )
        coverage = dict(reconciler.last_forecast_coverage)
    else:
        settlements = []
        coverage = {
            "phantom_coverage_version": "phantom-coverage-v1",
            "status": "NOTHING_ELIGIBLE",
            "eligible_unsettled_forecasts": 0,
            "eligible_in_requested_series": 0,
            "eligible_outside_requested_series": 0,
            "attempted_eligible_forecasts": 0,
            "graded_this_pass": 0,
            "attempt_coverage_ratio": None,
            "graded_coverage_ratio": None,
            "series_requested": 0,
            "series_attempted": 0,
            "series_failed": [],
            "series_truncated": [],
            "max_pages_per_series": int(max_pages_per_series),
            "pagination_truncated": False,
            "listing_errors": False,
            "complete": True,
        }

    signals_by_ticker = (
        ledger.calibration_signals_for_settled(
            [ticker for ticker, _result in settlements]
        )
        if settlements
        else {}
    )
    cluster_counts: dict[str, int] = {}
    for ticker, _result in settlements:
        key = group_key(ticker)
        cluster_counts[key] = cluster_counts.get(key, 0) + 1

    learner = Learner(ledger)
    weight_updates: dict[str, float] = {}
    for ticker, result_yes in settlements:
        key = group_key(ticker)
        weight_updates.update(
            learner.apply_settlement(
                ticker,
                result_yes,
                signals=signals_by_ticker.get(ticker),
                cluster_weight=1.0 / cluster_counts[key],
            )
        )

    guard_report = SimpleNamespace(weight_updates=weight_updates, notes=[])
    guard = learner.guard_cycle_weights(guard_report, previous_weights)
    coverage_ok, blockers = _coverage_passes(
        coverage,
        minimum_attempt_coverage=float(minimum_attempt_coverage),
    )
    if not guard.get("accepted", False):
        blockers.append("trust_weight_sanity_guard_rejected")
    status = "PASS" if coverage_ok and not blockers else "DEGRADED"

    receipt: dict[str, Any] = {
        "grading_worker_version": GRADING_WORKER_VERSION,
        "generated_at": generated_at,
        "status": status,
        "execution_authority": False,
        "order_authority": False,
        "cancel_authority": False,
        "authenticated_broker_contacted": False,
        "public_settlement_endpoint_used": bool(backlog),
        "backlog_at_start": len(backlog),
        "series_derived_from_backlog": series,
        "settlements_claimed_for_grading": len(settlements),
        "settled_tickers": sorted(ticker for ticker, _result in settlements),
        "weight_updates": dict(guard_report.weight_updates),
        "weight_guard": guard,
        "notes": list(guard_report.notes),
        "required_attempt_coverage": float(minimum_attempt_coverage),
        "coverage": coverage,
        "blockers": sorted(set(blockers)),
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        _canonical_bytes(receipt)
    ).hexdigest()
    if receipt_path is not None:
        _write_atomic_json(Path(receipt_path), receipt)
    return GradingPassResult(
        receipt=receipt,
        exit_code=0 if status == "PASS" else 2,
    )


__all__ = [
    "DEFAULT_MIN_ATTEMPT_COVERAGE",
    "DEFAULT_RECEIPT_PATH",
    "GRADING_WORKER_VERSION",
    "GradingPassResult",
    "run_grading_pass",
]
