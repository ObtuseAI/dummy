"""Performance-shape regressions for full-ledger backtest evidence scans."""
from __future__ import annotations

from datetime import datetime, timezone

from autonomy.backtest import _crypto_fill_diagnostics
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.retention import enforce_retention


def _insert_decision(
    ledger: AutonomyLedger,
    decision_id: str,
    ticker: str,
    created_at: str,
    *,
    probability: float = 0.6,
) -> None:
    ledger._conn.execute(  # noqa: SLF001 - exact ledger fixture
        """
        INSERT INTO decisions(
            decision_id,market_ticker,action,side,price_cents,count,ev_cents,
            kelly,notional_cents,probability_yes,market_implied_yes,sources_used,
            created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            decision_id, ticker, "BUY", "yes", 40, 1, 10.0, 0.1, 40,
            probability, 0.5, "{}", created_at,
        ),
    )


def _insert_outcome(
    ledger: AutonomyLedger,
    decision_id: str,
    ticker: str,
    kind: str,
    created_at: str,
    *,
    fill_count: int,
    pnl_cents: int | None = None,
) -> None:
    ledger._conn.execute(  # noqa: SLF001 - exact ledger fixture
        """
        INSERT INTO outcomes(
            decision_id,market_ticker,kind,fill_count,fill_price_cents,
            pnl_cents,broker_contacted,detail,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            decision_id, ticker, kind, fill_count,
            40 if fill_count else None, pnl_cents, 0, "{}", created_at,
        ),
    )


def test_multi_lane_calibration_uses_one_history_statement_and_keeps_lanes_separate(
    tmp_path,
):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ticker = "MODE-SPLIT"
        ledger.record_signal(Signal(
            "market_prior", ticker, 0.55, 0.1, "live",
            created_at="2026-01-01T00:00:01+00:00",
        ))
        ledger.record_signal(Signal(
            "market_prior", ticker, 0.85, 0.1, "retro",
            created_at="2026-01-01T00:00:02+00:00",
        ), mode="retro")
        ledger._conn.execute(  # noqa: SLF001 - exact receipt-time fixture
            "UPDATE signals SET ingested_at=created_at WHERE mode='live'"
        )
        ledger.record_settlement(ticker, True)

        statements: list[str] = []
        ledger._conn.set_trace_callback(statements.append)  # noqa: SLF001
        lanes = ledger.calibration_signals_for_settled_by_mode([ticker])
        ledger._conn.set_trace_callback(None)  # noqa: SLF001

        assert lanes["live"][ticker][0]["probability_yes"] == 0.55
        assert lanes["retro"][ticker][0]["probability_yes"] == 0.85
        batch_statements = [
            statement for statement in statements
            if "WITH EARLIEST_DECISION AS" in statement.upper()
            and "FROM MAIN.SIGNALS SH" in statement.upper()
        ]
        assert len(batch_statements) == 1
        assert "SH.MODE IN ('LIVE','RETRO')" in batch_statements[0].upper()
        assert "SH.PROBABILITY_YES" not in batch_statements[0].upper()
        assert "SH.FEATURES" not in batch_statements[0].upper()
        assert any(
            "FROM TEMP.BACKTEST_CHOSEN_SIGNAL_IDS CHOSEN" in statement.upper()
            and "CROSS JOIN MAIN.SIGNALS SH" in statement.upper()
            for statement in statements
        )
    finally:
        ledger.close()


def test_calibration_chosen_id_fetch_preserves_selection_across_hot_archive_boundary(
    tmp_path,
):
    db_path = tmp_path / "ledger.db"
    ticker = "HOT-ARCHIVE"
    ledger = AutonomyLedger(db_path)
    try:
        ledger.record_signal(Signal(
            "source", ticker, 0.1, 0.1, "archived earliest",
            created_at="2026-01-01T00:00:01+00:00",
        ))
        ledger._conn.execute(  # noqa: SLF001 - exact receipt-time fixture
            "UPDATE signals SET ingested_at=created_at"
        )
        ledger.record_settlement(ticker, True)
        ledger._conn.execute(  # noqa: SLF001 - historical retention fixture
            "UPDATE settlements SET settled_at=? WHERE market_ticker=?",
            ("2026-01-02T00:00:00+00:00", ticker),
        )
        ledger._conn.commit()  # noqa: SLF001
    finally:
        ledger.close()

    archived = enforce_retention(
        db_path,
        retention_days=7,
        apply=True,
        now=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    assert archived.archived_rows == 1

    ledger = AutonomyLedger(db_path)
    try:
        ledger.record_signal(Signal(
            "source", ticker, 0.9, 0.1, "hot latest",
            created_at="2026-01-01T00:00:02+00:00",
        ))
        ledger._conn.execute(  # noqa: SLF001 - exact receipt-time fixture
            "UPDATE main.signals SET ingested_at=created_at"
        )
        _insert_decision(
            ledger, "cross-store", ticker, "2026-01-01T00:00:03+00:00",
            probability=0.9,
        )
        ledger._conn.commit()  # noqa: SLF001

        batch = ledger.calibration_signals_for_settled_by_mode(
            [ticker], evidence_modes=("live",),
        )["live"]
        assert batch[ticker][0]["probability_yes"] == 0.9
        assert batch[ticker][0]["features"] == {}
    finally:
        ledger.close()


def test_crypto_source_snapshots_are_one_set_query_and_match_each_decision_cutoff(
    tmp_path,
):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXBTCD-26JAN01-T100000"
    try:
        for source, probability, created_at in (
            ("market_prior", 0.50, "2026-01-01T00:00:01+00:00"),
            ("model", 0.20, "2026-01-01T00:00:02+00:00"),
            ("model", 0.80, "2026-01-01T00:00:04+00:00"),
            # Future relative to both decisions: it must never leak backward.
            ("model", 0.99, "2026-01-01T00:00:06+00:00"),
        ):
            ledger.record_signal(Signal(
                source, ticker, probability, 0.1, "fixture", created_at=created_at,
            ))
        # Direct historical fixture permits the duplicate grain so we can pin
        # the legacy created_at/id tie-break independently of intake quarantine.
        ledger._conn.execute(  # noqa: SLF001
            """
            INSERT INTO signals(
                source,market_ticker,probability_yes,uncertainty,rationale,
                created_at,mode,features,ingested_at,ingest_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "model", ticker, 0.70, 0.1, "fixture",
                "2026-01-01T00:00:04+00:00", "live", "{}",
                "2026-01-01T00:00:04+00:00", 2,
            ),
        )
        ledger._conn.execute(  # noqa: SLF001 - exact receipt-time fixture
            "UPDATE signals SET ingested_at=created_at WHERE market_ticker=?",
            (ticker,),
        )
        ledger.record_signal(Signal(
            "model", ticker, 0.01, 0.1, "retro must not grade",
            created_at="2026-01-01T00:00:04.5+00:00",
        ), mode="retro")
        ledger._conn.execute(  # noqa: SLF001 - late-receipt negative fixture
            """
            INSERT INTO signals(
                source,market_ticker,probability_yes,uncertainty,rationale,
                created_at,mode,features,ingested_at,ingest_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "model", ticker, 0.01, 0.1, "late receipt",
                "2026-01-01T00:00:02.5+00:00", "live", "{}",
                "2026-01-01T00:00:06+00:00", 2,
            ),
        )
        _insert_decision(
            ledger, "crypto-early", ticker, "2026-01-01T00:00:03+00:00",
            probability=0.2,
        )
        _insert_decision(
            ledger, "crypto-late", ticker, "2026-01-01T00:00:05+00:00",
            probability=0.7,
        )
        ledger.record_settlement(ticker, True)
        _insert_outcome(
            ledger, "crypto-early", ticker, "FILLED",
            "2026-01-01T00:00:03.1+00:00", fill_count=1,
        )
        _insert_outcome(
            ledger, "crypto-early", ticker, "SETTLED_WIN",
            "2026-01-01T00:00:07+00:00", fill_count=1, pnl_cents=60,
        )
        _insert_outcome(
            ledger, "crypto-late", ticker, "FILLED",
            "2026-01-01T00:00:05.1+00:00", fill_count=1,
        )
        _insert_outcome(
            ledger, "crypto-late", ticker, "SETTLED_WIN",
            "2026-01-01T00:00:07+00:00", fill_count=1, pnl_cents=60,
        )
        ledger._conn.commit()  # noqa: SLF001

        statements: list[str] = []
        ledger._conn.set_trace_callback(statements.append)  # noqa: SLF001
        report = _crypto_fill_diagnostics(ledger._conn)  # noqa: SLF001
        ledger._conn.set_trace_callback(None)  # noqa: SLF001

        assert report["filled_settled_decisions"] == 2
        assert report["source_brier"]["model"] == {"n": 2, "brier": 0.365}
        snapshot_statements = [
            statement for statement in statements
            if "WITH FILLED_DECISIONS AS MATERIALIZED" in statement.upper()
            and "ROW_NUMBER() OVER" in statement.upper()
        ]
        assert len(snapshot_statements) == 1
        assert not any(
            "FROM SIGNAL_HISTORY WHERE MARKET_TICKER=" in statement.upper()
            for statement in statements
        )
    finally:
        ledger.close()


def test_signal_quality_uses_fixed_set_scans_not_one_archive_probe_per_decision(
    tmp_path,
):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ticker = "QUALITY"
        ledger.record_signal(Signal(
            "source", ticker, 0.6, 0.1, "fixture",
            created_at="2026-01-01T00:00:01+00:00",
        ))
        _insert_decision(
            ledger, "before-signal", ticker, "2026-01-01T00:00:00+00:00",
        )
        _insert_decision(
            ledger, "after-signal", ticker, "2026-01-01T00:00:02+00:00",
        )
        ledger._conn.commit()  # noqa: SLF001

        statements: list[str] = []
        ledger._conn.set_trace_callback(statements.append)  # noqa: SLF001
        quality = ledger.signal_quality_summary()
        ledger._conn.set_trace_callback(None)  # noqa: SLF001

        assert quality["signals_stored"] == 1
        assert quality["decisions_without_prior_signal"] == 1
        history_statements = [
            statement for statement in statements
            if "SIGNAL_HISTORY" in statement.upper()
        ]
        assert len(history_statements) == 5
        assert any(
            "MIN(CREATED_AT) AS FIRST_SIGNAL_AT" in statement.upper()
            for statement in history_statements
        )
        assert not any("NOT EXISTS" in statement.upper() for statement in history_statements)
    finally:
        ledger.close()
