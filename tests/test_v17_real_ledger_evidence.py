from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from archive.report_scripts.generate_v17_reports import (
    build_real_calibration_reports,
    build_v17_context,
    generate_v17_report_bundle,
)


def _create_ledger(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE decisions (
            decision_id TEXT PRIMARY KEY,
            market_ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            probability_yes REAL NOT NULL,
            forecast_uncertainty REAL NOT NULL,
            market_implied_yes REAL,
            sources_used TEXT NOT NULL,
            abstain_reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE settlements (
            market_ticker TEXT PRIMARY KEY,
            result_yes INTEGER NOT NULL,
            settled_at TEXT NOT NULL
        );
        """
    )
    connection.commit()
    return connection


def _insert_evidence(
    connection: sqlite3.Connection,
    *,
    decision_id: str,
    ticker: str,
    probability: float,
    market_probability: float | None,
    result: int,
    created_at: str = "2026-07-20T12:00:00+00:00",
    settled_at: str = "2026-07-21T12:00:00+00:00",
    action: str = "BUY",
    sources: object | None = None,
    abstain_reason: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO decisions(
            decision_id, market_ticker, action, probability_yes,
            forecast_uncertainty, market_implied_yes, sources_used,
            abstain_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            ticker,
            action,
            probability,
            0.2,
            market_probability,
            json.dumps(sources if sources is not None else {"market_prior": 1.0}),
            abstain_reason,
            created_at,
        ),
    )
    connection.execute(
        "INSERT OR REPLACE INTO settlements VALUES (?, ?, ?)",
        (ticker, result, settled_at),
    )
    connection.commit()


def test_empty_real_ledger_is_insufficient_and_never_uses_demo_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    _create_ledger(path).close()

    context = build_v17_context(path)
    reports = generate_v17_report_bundle(context, ledger_path=path)

    assert context.evidence_status == "INSUFFICIENT_DATA"
    assert context.evidence_reason == "no_eligible_real_rows"
    assert context.forecasts == []
    assert context.outcomes == []
    assert reports["outcome_ledger_report_v1.json"]["verdict"] == "INSUFFICIENT_DATA"
    assert reports["calibration_report_v1.json"]["verdict"] == "INSUFFICIENT_DATA"
    assert reports["calibration_report_v1.json"]["brier_score"] is None
    assert reports["bloodline_truth_score_report_v1.json"]["sample_count"] == 0
    assert reports["bloodline_truth_score_report_v1.json"]["verdict"] == "INSUFFICIENT_DATA"
    assert reports["baseline_forecast_replay_report_v1.json"]["baseline_scores"] == {}
    assert reports["dummy_mission_state_report_v17.json"]["verdict"] == "INSUFFICIENT_DATA"
    operational_payload = json.dumps(
        {
            name: report
            for name, report in reports.items()
            if name in {
                "outcome_ledger_report_v1.json",
                "forecast_snapshot_ledger_report_v1.json",
                "outcome_attribution_report_v1.json",
                "bloodline_truth_score_report_v1.json",
                "baseline_forecast_replay_report_v1.json",
            }
        }
    )
    assert "KXDEMO-TRUTH" not in operational_payload
    assert "fixture-source" not in operational_payload


def test_real_ledger_drives_v17_forecasts_calibration_and_baselines(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    connection = _create_ledger(path)
    _insert_evidence(
        connection,
        decision_id="real-1",
        ticker="KXMLBGAME-26JUL22NYYBOS-NYY",
        probability=0.8,
        market_probability=0.6,
        result=1,
        sources={"sports_elo": 0.7, "market_prior": 0.3},
    )
    # A later repeat must not replace the point-in-time earliest decision.
    connection.execute(
        """
        INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "real-1-late",
            "KXMLBGAME-26JUL22NYYBOS-NYY",
            "BUY",
            0.1,
            0.2,
            0.6,
            json.dumps({"sports_elo": 1.0}),
            "",
            "2026-07-20T13:00:00+00:00",
        ),
    )
    _insert_evidence(
        connection,
        decision_id="real-2",
        ticker="KXBTCD-26JUL2217-T100000",
        probability=0.2,
        market_probability=0.4,
        result=0,
        sources={"crypto_spot_vol": 1.0},
    )
    _insert_evidence(
        connection,
        decision_id="real-3",
        ticker="KXNFLGAME-26SEP01KCBDEN-KC",
        probability=0.7,
        market_probability=0.55,
        result=0,
        action="ABSTAIN",
        abstain_reason="LOW_CONFIDENCE",
        sources={"sports_glicko": 1.0},
    )
    connection.commit()
    connection.close()

    context = build_v17_context(path)
    reports = generate_v17_report_bundle(context, ledger_path=path)

    assert context.evidence_status == "AVAILABLE"
    assert len(context.forecasts) == 3
    assert len(context.outcomes) == 3
    probabilities = {item.market_id: item.probability for item in context.forecasts}
    assert probabilities["KXMLBGAME-26JUL22NYYBOS-NYY"] == pytest.approx(0.8)
    assert context.no_trade_record_id is not None
    calibration = reports["calibration_report_v1.json"]
    assert calibration["fixture_data_used"] is False
    assert calibration["source"]["kind"] == "runtime_autonomy_sqlite"
    assert calibration["sample_size"] == 3
    assert calibration["brier_score"] == pytest.approx(0.19)
    assert calibration["verdict"] == "PARTIAL"
    baseline = reports["baseline_forecast_replay_report_v1.json"]
    assert baseline["baseline_scores"]["dummy_forecast"]["sample_size"] == 3
    assert baseline["baseline_scores"]["dummy_forecast"]["brier_score"] == pytest.approx(0.19)
    assert baseline["baseline_scores"]["market_implied_baseline"]["brier_score"] == pytest.approx(0.2075)
    assert reports["bloodline_truth_score_report_v1.json"]["sample_count"] == 3
    assert reports["bloodline_truth_score_report_v1.json"]["verdict"] == "PARTIAL"
    source_names = {
        item["source_name"]
        for item in reports["outcome_backed_source_bloodline_report_v1.json"]["bloodlines"]
    }
    assert {"sports_elo", "market_prior", "crypto_spot_vol", "sports_glicko"} <= source_names


def test_fixture_post_settlement_non_target_and_bad_provenance_are_quarantined(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.db"
    connection = _create_ledger(path)
    _insert_evidence(
        connection,
        decision_id="real-good",
        ticker="KXMLBGAME-26JUL22LADSF-LAD",
        probability=0.6,
        market_probability=0.5,
        result=1,
    )
    _insert_evidence(
        connection,
        decision_id="fixture-row",
        ticker="KXDEMO-TRUTH-1",
        probability=0.99,
        market_probability=0.5,
        result=1,
        sources={"fixture-source": 1.0},
    )
    _insert_evidence(
        connection,
        decision_id="future-row",
        ticker="KXNFLGAME-26SEP02NYJBUF-NYJ",
        probability=0.99,
        market_probability=0.5,
        result=1,
        created_at="2026-07-22T12:00:00+00:00",
        settled_at="2026-07-21T12:00:00+00:00",
    )
    _insert_evidence(
        connection,
        decision_id="weather-row",
        ticker="KXHIGHNY-26JUL22-T90",
        probability=0.99,
        market_probability=0.5,
        result=1,
    )
    _insert_evidence(
        connection,
        decision_id="bad-source-row",
        ticker="KXMLBGAME-26JUL22CHCSTL-CHC",
        probability=0.99,
        market_probability=0.5,
        result=1,
        sources="not-a-source-mapping",
    )
    connection.close()

    context = build_v17_context(path)
    calibration = build_real_calibration_reports(ledger_path=path)

    assert [item.market_id for item in context.forecasts] == [
        "KXMLBGAME-26JUL22LADSF-LAD"
    ]
    diagnostics = context.source_metadata
    assert diagnostics["excluded_fixture_row_count"] == 1
    assert diagnostics["excluded_post_settlement_count"] == 1
    assert diagnostics["excluded_non_target_vertical_count"] == 1
    assert diagnostics["excluded_invalid_source_provenance_count"] == 1
    assert calibration["calibration_report_v1.json"]["sample_size"] == 1
    assert calibration["calibration_report_v1.json"]["verdict"] == "INSUFFICIENT_DATA"


def test_missing_or_locked_ledger_fails_closed_without_creating_evidence(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.db"
    missing_context = build_v17_context(missing)
    assert missing_context.evidence_reason == "ledger_missing"
    assert missing_context.evidence_status == "INSUFFICIENT_DATA"
    assert not missing.exists()

    path = tmp_path / "locked.db"
    lock = _create_ledger(path)
    lock.execute("BEGIN EXCLUSIVE")
    try:
        locked_context = build_v17_context(path)
    finally:
        lock.rollback()
        lock.close()
    assert locked_context.evidence_status == "INSUFFICIENT_DATA"
    assert locked_context.evidence_reason == "ledger_read_failed"
    assert locked_context.source_metadata["ledger_error_type"] == "OperationalError"
