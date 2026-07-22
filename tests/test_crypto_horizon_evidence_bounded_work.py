from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.crypto_horizon_evidence import (
    AUTHORITY,
    MATRIX_VERSION,
    CryptoHorizonEvidenceMatrix,
    CryptoHorizonEvidenceStore,
    deterministic_provenance_hash,
    fair_batch,
)
from scripts.run_dummy_crypto_horizon_evidence import (
    DEFAULT_MAX_CYCLE_MARKETS,
    DEFAULT_MAX_SCAN_SERIES,
    DEFAULT_MAX_SETTLEMENT_TICKERS,
    _commit_cursor_updates,
    _scan_series_market_batch,
    build_parser,
)


AS_OF = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _seed_closed_attempts(
    store: CryptoHorizonEvidenceStore,
    count: int,
) -> list[str]:
    cycle_id = "bounded-work-fixture"
    store.start_cycle(cycle_id, AS_OF.isoformat(), AS_OF.isoformat())
    tickers: list[str] = []
    for index in range(count):
        ticker = f"KXBTC15M-22JUL2611{index:02}-T{index:02}"
        tickers.append(ticker)
        provenance = {"ticker": ticker, "fixture": True}
        store.record_attempt(
            {
                "cycle_id": cycle_id,
                "source": "bounded_fixture",
                "emitted_source": "bounded_fixture",
                "asset": "BTC",
                "horizon": "15m",
                "contract_family": "direction",
                "event_cluster": ticker,
                "ticker": ticker,
                "close_time": (AS_OF - timedelta(minutes=1)).isoformat(),
                "status": "EMITTED",
                "probability_yes": 0.6,
                "uncertainty": 0.2,
                "market_probability": 0.5,
                "source_created_at": (AS_OF - timedelta(minutes=2)).isoformat(),
                "as_of_at": (AS_OF - timedelta(minutes=2)).isoformat(),
                "features": {"research_only": True},
                "provenance": provenance,
                "provenance_hash": deterministic_provenance_hash(provenance),
            }
        )
    store.finish_cycle(
        cycle_id,
        completed_at=AS_OF.isoformat(),
        status="CYCLE_OK",
        markets_seen=count,
        attempts_written=count,
        errors=[],
    )
    return tickers


def test_fair_batch_resumes_after_cursor_and_wraps() -> None:
    first = fair_batch(["c", "a", "b", "d"], cursor=None, limit=2)
    assert first["items"] == ["a", "b"]
    assert first["deferred"] == 2
    second = fair_batch(
        ["a", "b", "c", "d"], cursor=first["cursor_after"], limit=3
    )
    assert second["items"] == ["c", "d", "a"]
    assert second["wrapped"] is True
    assert second["cursor_after"] == "a"


def test_reconciliation_is_bounded_persistent_and_fair(tmp_path) -> None:
    path = tmp_path / "matrix.db"
    store = CryptoHorizonEvidenceStore(path)
    tickers = _seed_closed_attempts(store, 5)
    matrix = CryptoHorizonEvidenceMatrix(store=store, now_fn=lambda: AS_OF)
    first_calls: list[str] = []
    first = matrix.reconcile_settlements(
        lambda ticker: first_calls.append(ticker) or {"result": "yes"},
        as_of=AS_OF,
        max_tickers=2,
        time_budget_seconds=10,
    )
    assert first_calls == tickers[:2]
    assert first["status"] == "RECONCILIATION_PARTIAL"
    assert first["deferred_in_sweep"] == 3
    assert first["settlements_recorded"] == 2
    assert first["cursor"]["after"] == tickers[1]
    assert first["authority"] == AUTHORITY
    matrix.close()

    reopened = CryptoHorizonEvidenceStore(path)
    resumed_matrix = CryptoHorizonEvidenceMatrix(
        store=reopened,
        now_fn=lambda: AS_OF,
    )
    second_calls: list[str] = []
    second = resumed_matrix.reconcile_settlements(
        lambda ticker: second_calls.append(ticker) or {"result": "no"},
        as_of=AS_OF,
        max_tickers=2,
        time_budget_seconds=10,
    )
    assert second_calls == tickers[2:4]
    assert second["cursor"]["before"] == tickers[1]
    assert second["deferred_in_sweep"] == 1

    final_calls: list[str] = []
    final = resumed_matrix.reconcile_settlements(
        lambda ticker: final_calls.append(ticker) or {"result": "yes"},
        as_of=AS_OF,
        max_tickers=2,
        time_budget_seconds=10,
    )
    assert final_calls == tickers[4:]
    assert final["status"] == "RECONCILIATION_SWEEP_COMPLETE"
    assert final["unresolved_eligible_tickers"] == 0
    resumed_matrix.close()


def test_reconciliation_deadline_defers_and_advances_only_attempted_work(
    tmp_path,
) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    tickers = _seed_closed_attempts(store, 3)
    clock = iter([0.0, 0.0, 2.0])
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        now_fn=lambda: AS_OF,
        monotonic_fn=lambda: next(clock),
    )
    calls: list[str] = []
    result = matrix.reconcile_settlements(
        lambda ticker: calls.append(ticker) or {},
        as_of=AS_OF,
        max_tickers=3,
        time_budget_seconds=1,
    )
    assert calls == tickers[:1]
    assert result["deadline_reached"] is True
    assert result["deferred_in_sweep"] == 2
    assert result["cursor"]["after"] == tickers[0]
    assert result["sweep_complete"] is False
    matrix.close()


def _raw_market(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "title": ticker,
        "status": "open",
        "close_time": (AS_OF + timedelta(hours=1)).isoformat(),
        "yes_bid": 45,
        "yes_ask": 47,
        "no_bid": 53,
        "no_ask": 55,
        "volume": 100,
        "liquidity": 1_000,
    }


def test_scan_series_and_markets_resume_round_robin_without_network(tmp_path) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    pages = {
        "S1": {"markets": [_raw_market("KXBTC15M-A"), _raw_market("KXBTC15M-B")]},
        "S2": {"markets": [_raw_market("KXETH15M-A"), _raw_market("KXETH15M-B")]},
        "S3": {"markets": [_raw_market("KXSOL15M-A"), _raw_market("KXSOL15M-B")]},
    }
    first_markets, first, updates = _scan_series_market_batch(
        store,
        fetch_series=lambda series: pages[series],
        watchlist=["S1", "S2", "S3"],
        max_series=2,
        max_markets=3,
        time_budget_seconds=10,
        monotonic_fn=lambda: 0.0,
    )
    assert first["attempted_series"] == ["S1", "S2"]
    assert [market.ticker for market in first_markets] == [
        "KXBTC15M-A", "KXETH15M-A", "KXBTC15M-B"
    ]
    assert first["status"] == "SCAN_PARTIAL"
    assert first["series_deferred"] == 1
    assert first["authority"]["execution_authority"] is False
    _commit_cursor_updates(store, updates, updated_at=AS_OF.isoformat())

    second_markets, second, _updates = _scan_series_market_batch(
        store,
        fetch_series=lambda series: pages[series],
        watchlist=["S1", "S2", "S3"],
        max_series=2,
        max_markets=3,
        time_budget_seconds=10,
        monotonic_fn=lambda: 0.0,
    )
    assert second["attempted_series"] == ["S3", "S1"]
    assert [market.ticker for market in second_markets] == [
        "KXSOL15M-A", "KXBTC15M-A", "KXSOL15M-B"
    ]
    store.close()


def test_scan_time_budget_stops_between_series_without_advancing_unattempted(
    tmp_path,
) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    clock = iter([0.0, 0.0, 2.0])
    calls: list[str] = []
    _markets, report, updates = _scan_series_market_batch(
        store,
        fetch_series=lambda series: calls.append(series) or {"markets": []},
        watchlist=["S1", "S2", "S3"],
        max_series=3,
        max_markets=3,
        time_budget_seconds=1,
        monotonic_fn=lambda: next(clock),
    )
    assert calls == ["S1"]
    assert report["deadline_reached"] is True
    assert report["series_deferred"] == 2
    assert report["series_cursor"]["after"] == "S1"
    assert updates[0]["cursor"] == "S1"
    store.close()


def test_cli_defaults_are_explicitly_bounded() -> None:
    args = build_parser().parse_args([])
    assert args.max_settlement_tickers == DEFAULT_MAX_SETTLEMENT_TICKERS
    assert args.max_scan_series == DEFAULT_MAX_SCAN_SERIES
    assert args.max_cycle_markets == DEFAULT_MAX_CYCLE_MARKETS
    assert args.max_settlement_tickers > 0
    assert args.max_scan_series > 0
    assert args.max_cycle_markets > 0


def test_empty_cycle_does_not_start_public_source_hooks(tmp_path) -> None:
    calls: list[str] = []

    class Source:
        name = "must_not_start"

        def on_cycle_start(self) -> None:
            calls.append("network_hook")

    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        sources=[Source()],
        now_fn=lambda: AS_OF,
    )
    report = matrix.run_cycle([], as_of=AS_OF)
    assert calls == []
    assert report["markets_seen"] == 0
    assert report["authority"] == AUTHORITY
    matrix.close()


def test_bounded_report_discloses_unscored_rows_and_keeps_no_authority(
    tmp_path,
) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    tickers = _seed_closed_attempts(store, 3)
    for ticker in tickers:
        assert store.settle_ticker(ticker, True, AS_OF) == 1
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        sources=[object()],
        now_fn=lambda: AS_OF,
    )
    report = matrix.run_cycle([], as_of=AS_OF, report_max_settled_rows=2)
    coverage = report["settled_evidence"]["coverage"]
    assert coverage == {
        "rows_available": 3,
        "rows_scored": 2,
        "rows_deferred": 1,
        "partial": True,
        "selection": "most_recent_settled_rows",
    }
    assert report["status"] == "CYCLE_PARTIAL"
    assert store.settled_row_count() == 3
    assert report["authority"] == AUTHORITY
    assert report["matrix_version"] == MATRIX_VERSION
    matrix.close()
