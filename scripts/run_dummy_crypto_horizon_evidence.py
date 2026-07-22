"""Run the public-read-only Crypto Horizon Evidence Matrix once.

The command records research forecasts and public settlements in its own
SQLite database.  It has no execution, capital, promotion, gate, weight, or
risk authority.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from functools import partial
from pathlib import Path
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autonomy.crypto_horizon_evidence import (  # noqa: E402
    CryptoHorizonEvidenceMatrix,
    CryptoHorizonEvidenceStore,
    build_registered_crypto_sources,
    fair_batch,
    write_evidence_report,
)
from autonomy.crypto_paper_twin import WATCHLIST  # noqa: E402
from autonomy.ontology import Vertical  # noqa: E402
from autonomy.reconciler import default_fetch_market_result  # noqa: E402
from autonomy.scanner import (  # noqa: E402
    MarketScanner,
    default_fetch_series_markets,
)
from autonomy.signals.crypto_indicators import CryptoDataHub  # noqa: E402


DEFAULT_MAX_SETTLEMENT_TICKERS = 12
DEFAULT_SETTLEMENT_TIME_BUDGET_SECONDS = 45.0
DEFAULT_MAX_SCAN_SERIES = 4
DEFAULT_SCAN_TIME_BUDGET_SECONDS = 60.0
DEFAULT_MAX_CYCLE_MARKETS = 300
DEFAULT_PUBLIC_REQUEST_TIMEOUT_SECONDS = 4.0
DEFAULT_MAX_SETTLED_REPORT_ROWS = 25_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("runtime/autonomy/crypto_horizon_evidence.db"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/dummy/crypto_horizon_evidence"),
    )
    parser.add_argument(
        "--max-settlement-tickers",
        type=int,
        default=DEFAULT_MAX_SETTLEMENT_TICKERS,
        help="Maximum distinct closed tickers checked in this fair sweep segment.",
    )
    parser.add_argument(
        "--settlement-time-budget-seconds",
        type=float,
        default=DEFAULT_SETTLEMENT_TIME_BUDGET_SECONDS,
        help="Cooperative wall-clock budget checked between public result requests.",
    )
    parser.add_argument(
        "--max-scan-series",
        type=int,
        default=DEFAULT_MAX_SCAN_SERIES,
        help="Maximum crypto series scanned in this persistent round-robin segment.",
    )
    parser.add_argument(
        "--scan-time-budget-seconds",
        type=float,
        default=DEFAULT_SCAN_TIME_BUDGET_SECONDS,
        help="Cooperative wall-clock budget checked between series requests.",
    )
    parser.add_argument(
        "--max-cycle-markets",
        type=int,
        default=DEFAULT_MAX_CYCLE_MARKETS,
        help="Maximum unique markets researched this cycle across scanned series.",
    )
    parser.add_argument(
        "--public-request-timeout-seconds",
        type=float,
        default=DEFAULT_PUBLIC_REQUEST_TIMEOUT_SECONDS,
        help="Timeout for each public read-only Kalshi request.",
    )
    parser.add_argument(
        "--max-settled-report-rows",
        type=int,
        default=DEFAULT_MAX_SETTLED_REPORT_ROWS,
        help="Maximum settled forecasts rescored in one report; excess is disclosed.",
    )
    parser.add_argument("--summary", action="store_true")
    return parser


def _scan_series_market_batch(
    store: CryptoHorizonEvidenceStore,
    *,
    fetch_series: Callable[[str], dict[str, Any]],
    watchlist: Sequence[str],
    max_series: int,
    max_markets: int,
    time_budget_seconds: float,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> tuple[list[Any], dict[str, Any], list[dict[str, Any]]]:
    """Scan a persistent fair series segment and round-robin its markets."""
    series_batch = store.fair_work_batch(
        "crypto_horizon_scan_series",
        list(watchlist),
        limit=max(0, int(max_series)),
    )
    started = monotonic_fn()
    deadline_reached = False
    errors: list[str] = []
    candidates: dict[str, list[Any]] = {}
    candidate_batches: dict[str, dict[str, Any]] = {}
    discovered_tickers: set[str] = set()
    attempted_series: list[str] = []
    for series in series_batch["items"]:
        if monotonic_fn() - started >= max(0.0, float(time_budget_seconds)):
            deadline_reached = True
            break
        attempted_series.append(str(series))
        fetch_errors: list[str] = []

        def observed_fetch(requested: str) -> dict[str, Any]:
            try:
                return fetch_series(requested)
            except Exception as exc:
                fetch_errors.append(type(exc).__name__)
                raise

        scanner = MarketScanner(
            fetch_series=observed_fetch,
            watchlist=[str(series)],
            verticals={Vertical.CRYPTO},
        )
        views = scanner.scan()
        discovered_tickers.update(str(view.ticker) for view in views)
        if fetch_errors:
            errors.append(f"{series}:{fetch_errors[-1]}")
        market_state = store.work_state(f"crypto_horizon_scan_market:{series}")
        batch = fair_batch(
            views,
            cursor=market_state.get("cursor"),
            limit=max(0, int(max_markets)),
            key=lambda market: str(market.ticker),
        )
        candidate_batches[str(series)] = batch
        candidates[str(series)] = list(batch["items"])

    selected: list[Any] = []
    selected_tickers: set[str] = set()
    consumed_by_series: dict[str, list[str]] = defaultdict(list)
    positions = {series: 0 for series in attempted_series}
    bounded_markets = max(0, int(max_markets))
    while len(selected) < bounded_markets:
        progressed = False
        for series in attempted_series:
            rows = candidates.get(series, [])
            position = positions[series]
            if position >= len(rows):
                continue
            market = rows[position]
            positions[series] = position + 1
            ticker = str(market.ticker)
            consumed_by_series[series].append(ticker)
            progressed = True
            if ticker in selected_tickers:
                continue
            selected_tickers.add(ticker)
            selected.append(market)
            if len(selected) >= bounded_markets:
                break
        if not progressed:
            break

    cursor_updates: list[dict[str, Any]] = []
    if attempted_series:
        cursor_updates.append(
            {
                "work_name": "crypto_horizon_scan_series",
                "cursor": attempted_series[-1],
                "metadata": {
                    "attempted_series": attempted_series,
                    "errors": errors,
                },
            }
        )
    for series, keys in consumed_by_series.items():
        if not keys:
            continue
        cursor_updates.append(
            {
                "work_name": f"crypto_horizon_scan_market:{series}",
                "cursor": keys[-1],
                "metadata": {
                    "markets_consumed": len(keys),
                    "markets_selected_unique": sum(
                        1 for key in keys if key in selected_tickers
                    ),
                },
            }
        )

    discovered_unique = len(discovered_tickers)
    series_deferred = max(0, int(series_batch["total"]) - len(attempted_series))
    market_deferred = max(0, discovered_unique - len(selected))
    partial = bool(errors or deadline_reached or series_deferred or market_deferred)
    report = {
        "status": "SCAN_PARTIAL" if partial else "SCAN_COMPLETE",
        "partial": partial,
        "series_available": int(series_batch["total"]),
        "series_selected": len(series_batch["items"]),
        "series_attempted": len(attempted_series),
        "attempted_series": attempted_series,
        "series_deferred": series_deferred,
        "market_candidates": discovered_unique,
        "markets_selected": len(selected),
        "markets_deferred": market_deferred,
        "deadline_reached": deadline_reached,
        "errors": errors,
        "work_cap": {
            "max_series": max(0, int(max_series)),
            "max_markets": bounded_markets,
            "time_budget_seconds": max(0.0, float(time_budget_seconds)),
            "deadline_enforcement": "cooperative_between_public_requests",
        },
        "series_cursor": {
            "before": series_batch.get("cursor_before"),
            "after": attempted_series[-1] if attempted_series else series_batch.get("cursor_before"),
            "wrapped": bool(series_batch.get("wrapped")),
            "persistent": True,
        },
        "market_cursors": {
            series: {
                "before": batch.get("cursor_before"),
                "after": (
                    consumed_by_series.get(series, [batch.get("cursor_before")])[-1]
                    if consumed_by_series.get(series)
                    else batch.get("cursor_before")
                ),
                "available": int(batch.get("total") or 0),
                "deferred": max(
                    0,
                    int(batch.get("total") or 0)
                    - len(consumed_by_series.get(series, [])),
                ),
            }
            for series, batch in sorted(candidate_batches.items())
        },
        "authority": {
            "research_only": True,
            "execution_authority": False,
            "capital_authority": False,
        },
    }
    return selected, report, cursor_updates


def _commit_cursor_updates(
    store: CryptoHorizonEvidenceStore,
    updates: Sequence[dict[str, Any]],
    *,
    updated_at: str,
) -> None:
    for update in updates:
        store.set_work_cursor(
            str(update["work_name"]),
            update.get("cursor"),
            updated_at=updated_at,
            metadata=update.get("metadata") or {},
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    for name in (
        "max_settlement_tickers",
        "max_scan_series",
        "max_cycle_markets",
        "max_settled_report_rows",
    ):
        if int(getattr(args, name)) < 0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")
    for name in (
        "settlement_time_budget_seconds",
        "scan_time_budget_seconds",
        "public_request_timeout_seconds",
    ):
        if float(getattr(args, name)) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")

    store = CryptoHorizonEvidenceStore(args.db)
    def bounded_client_factory():
        import httpx

        return httpx.Client(
            timeout=args.public_request_timeout_seconds,
            headers={
                "User-Agent": "DummyPredictionResearch/0.1 (public-read-only)"
            },
        )

    hub = CryptoDataHub(client_factory=bounded_client_factory)
    sources = build_registered_crypto_sources(
        hub,
        public_request_timeout_seconds=args.public_request_timeout_seconds,
    )
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        hub=hub,
        sources=sources,
    )
    try:
        settlement_fetch = partial(
            default_fetch_market_result,
            timeout_seconds=args.public_request_timeout_seconds,
        )
        settlement = matrix.reconcile_settlements(
            settlement_fetch,
            max_tickers=args.max_settlement_tickers,
            time_budget_seconds=args.settlement_time_budget_seconds,
        )
        series_fetch = partial(
            default_fetch_series_markets,
            timeout_seconds=args.public_request_timeout_seconds,
        )
        markets, scan_workload, cursor_updates = _scan_series_market_batch(
            store,
            fetch_series=series_fetch,
            watchlist=list(WATCHLIST),
            max_series=args.max_scan_series,
            max_markets=args.max_cycle_markets,
            time_budget_seconds=args.scan_time_budget_seconds,
        )
        workload = {
            "partial": bool(
                scan_workload["partial"]
                or settlement["status"] == "RECONCILIATION_PARTIAL"
            ),
            "scan": scan_workload,
            "settlement_reconciliation": {
                "status": settlement["status"],
                "eligible_tickers_at_start": settlement[
                    "eligible_tickers_at_start"
                ],
                "tickers_attempted": settlement["tickers_attempted"],
                "deferred_in_sweep": settlement["deferred_in_sweep"],
                "unresolved_eligible_tickers": settlement[
                    "unresolved_eligible_tickers"
                ],
                "cursor": settlement["cursor"],
            },
            "authority": {
                "research_only": True,
                "execution_authority": False,
                "capital_authority": False,
            },
        }
        report = matrix.run_cycle(
            markets,
            workload=workload,
            report_max_settled_rows=args.max_settled_report_rows,
        )
        _commit_cursor_updates(
            store,
            cursor_updates,
            updated_at=str(report["completed_at"]),
        )
        report["settlement_reconciliation"] = settlement
        report_path = write_evidence_report(report, args.out_dir)
        output = (
            {
                "status": report["status"],
                "cycle_id": report["cycle_id"],
                "markets_seen": report["markets_seen"],
                "attempts_written": report["attempts_written"],
                "settlements_recorded": settlement["settlements_recorded"],
                "settlement_status": settlement["status"],
                "settlement_backlog": settlement["unresolved_eligible_tickers"],
                "scan_status": scan_workload["status"],
                "scan_series_attempted": scan_workload["series_attempted"],
                "scan_markets_deferred": scan_workload["markets_deferred"],
                "execution_authority": False,
                "capital_authority": False,
                "report_path": str(report_path.resolve()),
            }
            if args.summary
            else {**report, "report_path": str(report_path.resolve())}
        )
        print(json.dumps(output, indent=None if args.summary else 2, sort_keys=True))
        return 0 if report["status"] in {"CYCLE_OK", "CYCLE_PARTIAL"} else 1
    finally:
        matrix.close()


if __name__ == "__main__":
    raise SystemExit(main())
