"""Wave-83: the recal's out-of-sample gate.

The 6h recalibration derives trust weights in-sample; the gate scores the
freshly derived recipe against the incumbent live weights on a cluster-atomic
chronological holdout. Adoption requires a positive paired event-cluster
bootstrap lower bound. These tests drive _recal_oos_gate directly on synthetic
settlements.
"""
from __future__ import annotations

import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import autonomy.backtest as backtest
from autonomy.backtest import _recal_oos_adoption_valid, _recal_oos_gate
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _conn_with_settlements(rows: list[tuple[str, int, str]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE settlements("
        "market_ticker TEXT PRIMARY KEY, result_yes INTEGER, settled_at TEXT)"
    )
    conn.executemany("INSERT INTO settlements VALUES (?,?,?)", rows)
    return conn


def _signal(source: str, probability: float) -> dict:
    return {"source": source, "probability_yes": probability, "features": {},
            "created_at": "2026-07-01T00:00:00+00:00"}


def _build_case(good_in_holdout: bool):
    """20 markets: 'sharp' nails the train window; holdout behavior varies."""
    rows: list[tuple[str, int, str]] = []
    signals: dict[str, list[dict]] = {}
    settlements: dict[str, int] = {}
    for i in range(20):
        ticker = f"T{i:02d}"
        result = i % 2
        settled = f"2026-07-{i + 1:02d}T00:00:00+00:00"
        rows.append((ticker, result, settled))
        settlements[ticker] = result
        in_holdout = i >= 14  # fraction 0.3 of 20 -> last 6
        correct = 0.95 if result else 0.05
        wrong = 0.05 if result else 0.95
        sharp = correct if (not in_holdout or good_in_holdout) else wrong
        signals[ticker] = [
            _signal("market_prior", 0.5),
            _signal("sharp", sharp),
        ]
    return _conn_with_settlements(rows), signals, settlements


def test_better_recipe_is_adopted():
    conn, signals, settlements = _build_case(good_in_holdout=True)
    # Incumbent distrusts the sharp source; the derived recipe trusts it and
    # scores better on the holdout -> adopt.
    gate = _recal_oos_gate(
        conn, signals, settlements, {"sharp": 0.05},
        holdout_fraction=0.3, min_holdout=2, min_holdout_clusters=2,
    )
    repeated = _recal_oos_gate(
        conn, signals, settlements, {"sharp": 0.05},
        holdout_fraction=0.3, min_holdout=2, min_holdout_clusters=2,
    )
    assert gate == repeated
    assert gate["status"] == "OK"
    assert gate["adopted"] is True
    assert gate["held_out_improvement_verified"] is True
    assert gate["oos_brier_delta"] < 0.0
    assert gate["oos_brier_improvement"] > gate["minimum_improvement_required"]
    assert gate["holdout_markets"] == 6
    assert gate["holdout_event_clusters"] == 6
    assert gate["train_markets"] == 14
    interval = gate["paired_cluster_brier_improvement_ci95"]
    assert interval["lower"] > 0.0
    assert interval["method"] == backtest.RECAL_OOS_BOOTSTRAP_METHOD
    assert interval["resampling_unit"] == "equal_weight_event_cluster_mean"
    assert interval["resamples"] * interval["clusters"] <= interval[
        "maximum_bootstrap_draws"
    ]
    assert gate["execution_authority"] is False
    assert gate["capital_authority"] is False
    assert _recal_oos_adoption_valid(gate) is True


def test_worse_recipe_is_refused():
    conn, signals, settlements = _build_case(good_in_holdout=False)
    # The sharp source flips in the holdout: the train-derived recipe upweights
    # it, the neutral incumbent doesn't -> candidate grades worse -> refuse.
    gate = _recal_oos_gate(
        conn, signals, settlements, {},
        holdout_fraction=0.3, min_holdout=2, min_holdout_clusters=2,
    )
    assert gate["status"] == "OK"
    assert gate["adopted"] is False
    assert gate["held_out_improvement_verified"] is False
    assert gate["oos_brier_delta"] >= 0.0
    assert _recal_oos_adoption_valid(gate) is False


def test_small_history_skips_and_refuses_adoption():
    conn, signals, settlements = _build_case(good_in_holdout=True)
    gate = _recal_oos_gate(
        conn, signals, settlements, {},
        holdout_fraction=0.3, min_holdout=500, min_holdout_clusters=2,
    )
    assert gate["status"] == "SKIPPED"
    assert gate["adopted"] is False
    assert gate["held_out_improvement_verified"] is False
    assert "insufficient_holdout" in gate["reason"]


def test_no_scorable_holdout_refuses_adoption():
    conn, signals, settlements = _build_case(good_in_holdout=True)
    for index in range(14, 20):
        signals[f"T{index:02d}"] = []
    gate = _recal_oos_gate(
        conn, signals, settlements, {},
        holdout_fraction=0.3, min_holdout=2, min_holdout_clusters=2,
    )
    assert gate["status"] == "SKIPPED"
    assert gate["reason"] == "no_scorable_holdout_markets"
    assert gate["adopted"] is False
    assert _recal_oos_adoption_valid(gate) is False


def test_partially_scorable_holdout_must_still_meet_minimum():
    conn, signals, settlements = _build_case(good_in_holdout=True)
    for index in range(15, 20):
        signals[f"T{index:02d}"] = []
    gate = _recal_oos_gate(
        conn, signals, settlements, {},
        holdout_fraction=0.3, min_holdout=2, min_holdout_clusters=2,
    )
    assert gate["status"] == "SKIPPED"
    assert gate["reason"] == "insufficient_scorable_holdout:1<2"
    assert gate["adopted"] is False


def test_repeated_correlated_markets_cannot_manufacture_adoption():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[tuple[str, int, str]] = []
    signals: dict[str, list[dict]] = {}
    settlements: dict[str, int] = {}

    def add(
        ticker: str,
        result: int,
        settled_at: datetime,
        sharp_probability: float,
    ) -> None:
        rows.append((ticker, result, settled_at.isoformat()))
        settlements[ticker] = result
        signals[ticker] = [
            _signal("market_prior", 0.5),
            _signal("sharp", sharp_probability),
        ]

    # Independent training events teach the candidate to trust ``sharp``.
    for index in range(20):
        result = index % 2
        add(
            f"TRAIN{index:02d}-CONTRACT",
            result,
            start + timedelta(hours=index),
            0.95 if result else 0.05,
        )

    # Two independent future events expose that trust as harmful.
    add("BAD-A-CONTRACT", 1, start + timedelta(hours=20), 0.05)
    add("BAD-B-CONTRACT", 0, start + timedelta(hours=21), 0.95)

    # One later event has 100 correlated contracts on which the candidate wins.
    # A market-weighted point estimate is positive, but it remains one cluster.
    for index in range(100):
        add(
            f"CORRELATED-CONTRACT{index:03d}",
            1,
            start + timedelta(hours=22),
            0.95,
        )

    gate = _recal_oos_gate(
        _conn_with_settlements(rows),
        signals,
        settlements,
        {"sharp": 0.05},
        holdout_fraction=0.5,
        min_holdout=50,
        min_holdout_clusters=3,
    )

    assert gate["status"] == "OK"
    assert gate["market_weighted_oos_brier_improvement"] > 0.0
    assert gate["holdout_event_clusters"] == 3
    assert gate["paired_cluster_brier_improvement_ci95"]["lower"] <= 0.0
    assert gate["adopted"] is False
    assert _recal_oos_adoption_valid(gate) is False


def test_single_repeated_cluster_is_insufficient_independent_evidence():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        (f"ONLY-CONTRACT{index:03d}", index % 2, start.isoformat())
        for index in range(40)
    ]
    settlements = {ticker: result for ticker, result, _stamp in rows}
    signals = {
        ticker: [
            _signal("market_prior", 0.5),
            _signal("sharp", 0.95 if result else 0.05),
        ]
        for ticker, result, _stamp in rows
    }
    gate = _recal_oos_gate(
        _conn_with_settlements(rows),
        signals,
        settlements,
        {},
        holdout_fraction=0.5,
        min_holdout=10,
        min_holdout_clusters=2,
    )
    assert gate["status"] == "SKIPPED"
    assert gate["reason"].startswith(
        "insufficient_event_clusters_for_train_holdout"
    )
    assert gate["adopted"] is False


def test_malformed_cluster_identity_rejects_before_evaluation():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        ("", 1, start.isoformat()),
        ("VALID-A", 1, (start + timedelta(hours=1)).isoformat()),
        ("VALID-B", 0, (start + timedelta(hours=2)).isoformat()),
        ("VALID-C", 1, (start + timedelta(hours=3)).isoformat()),
    ]
    settlements = {ticker: result for ticker, result, _stamp in rows}
    signals = {
        ticker: [_signal("market_prior", 0.5)]
        for ticker, _result, _stamp in rows
    }
    gate = _recal_oos_gate(
        _conn_with_settlements(rows),
        signals,
        settlements,
        {},
        holdout_fraction=0.5,
        min_holdout=2,
        min_holdout_clusters=1,
    )
    assert gate["status"] == "INVALID"
    assert gate["reason"] == "invalid_event_cluster_identity"
    assert gate["adopted"] is False


def test_overlapping_cluster_interval_rejects_instead_of_crossing_cutoff():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        ("SHARED-A", 1, start.isoformat()),
        ("EVENT-B-X", 0, (start + timedelta(hours=1)).isoformat()),
        ("EVENT-C-X", 1, (start + timedelta(hours=2)).isoformat()),
        ("SHARED-B", 1, (start + timedelta(hours=3)).isoformat()),
    ]
    settlements = {ticker: result for ticker, result, _stamp in rows}
    signals = {
        ticker: [_signal("market_prior", 0.5)]
        for ticker, _result, _stamp in rows
    }
    gate = _recal_oos_gate(
        _conn_with_settlements(rows),
        signals,
        settlements,
        {},
        holdout_fraction=0.5,
        min_holdout=2,
        min_holdout_clusters=1,
    )
    assert gate["status"] == "SKIPPED"
    assert gate["reason"] == (
        "no_strictly_earlier_cluster_atomic_training_partition"
    )
    assert gate["adopted"] is False


def _valid_improvement_receipt() -> dict:
    return {
        "status": "OK",
        "adopted": True,
        "held_out_improvement_verified": True,
        "evidence_mode": "held_out_research_challenger",
        "authority": "weight_recalibration_only",
        "execution_authority": False,
        "capital_authority": False,
        "holdout_markets": 500,
        "minimum_holdout_required": 500,
        "train_markets": 3_000,
        "holdout_event_clusters": 500,
        "minimum_holdout_event_clusters": 20,
        "train_event_clusters": 3_000,
        "partition_holdout_event_clusters": 500,
        "cluster_overlap_count": 0,
        "cluster_identity_complete": True,
        "cluster_atomic_split": True,
        "cluster_identity_method": backtest.RECAL_OOS_CLUSTER_IDENTITY_METHOD,
        "split_method": backtest.RECAL_OOS_SPLIT_METHOD,
        "candidate_holdout_brier": 0.20,
        "incumbent_holdout_brier": 0.25,
        "oos_brier_delta": -0.05,
        "oos_brier_improvement": 0.05,
        "minimum_improvement_required": 0.0,
        "paired_cluster_brier_improvement_ci95": {
            "mean": 0.05,
            "lower": 0.04,
            "upper": 0.06,
            "confidence": 0.95,
            "method": backtest.RECAL_OOS_BOOTSTRAP_METHOD,
            "resampling_unit": "equal_weight_event_cluster_mean",
            "clusters": 500,
            "resamples": 1_000,
            "seed": backtest.RECAL_OOS_BOOTSTRAP_SEED,
            "maximum_bootstrap_draws": (
                backtest.RECAL_OOS_MAX_BOOTSTRAP_DRAWS
            ),
        },
    }


def test_writer_validator_requires_positive_cluster_ci_and_identity():
    nonpositive = _valid_improvement_receipt()
    nonpositive["paired_cluster_brier_improvement_ci95"]["lower"] = 0.0
    assert _recal_oos_adoption_valid(nonpositive) is False

    missing_identity = deepcopy(_valid_improvement_receipt())
    missing_identity.pop("cluster_identity_method")
    assert _recal_oos_adoption_valid(missing_identity) is False


def _ledger_with_weight_candidate(tmp_path) -> AutonomyLedger:
    ledger = AutonomyLedger(tmp_path / "recal.db")
    for index in range(8):
        ticker = f"RECAL-{index:02d}"
        result = index % 2 == 0
        ledger.record_signal(Signal(
            source="market_prior",
            market_ticker=ticker,
            probability_yes=0.50,
            uncertainty=0.10,
            rationale="",
        ))
        ledger.record_signal(Signal(
            source="sharp",
            market_ticker=ticker,
            probability_yes=0.90 if result else 0.10,
            uncertainty=0.10,
            rationale="",
        ))
        ledger.record_settlement(ticker, result)
    return ledger


def test_gate_exception_is_reported_and_cannot_write_weights(tmp_path, monkeypatch):
    ledger = _ledger_with_weight_candidate(tmp_path)
    writes: list[dict[str, float]] = []
    monkeypatch.setenv("DUMMY_DAEMON_ALERTS", "0")
    monkeypatch.setattr(ledger, "update_weights", lambda batch: writes.append(dict(batch)))

    def fail_gate(*_args, **_kwargs):
        raise RuntimeError("gate unavailable")

    monkeypatch.setattr(backtest, "_recal_oos_gate", fail_gate)
    try:
        report = backtest.run_backtest(
            ledger, bootstrap_weights=True, include_diagnostics=False,
        )
    finally:
        ledger.close()

    assert report["recal_oos_gate"]["status"] == "ERROR"
    assert report["recal_oos_gate"]["adopted"] is False
    assert report["weights_written"] is False
    assert writes == []


def test_disabled_gate_cannot_bypass_evidence_or_write_weights(tmp_path, monkeypatch):
    ledger = _ledger_with_weight_candidate(tmp_path)
    writes: list[dict[str, float]] = []
    monkeypatch.setenv("DUMMY_RECAL_OOS_GATE", "0")
    monkeypatch.setenv("DUMMY_DAEMON_ALERTS", "0")
    monkeypatch.setattr(ledger, "update_weights", lambda batch: writes.append(dict(batch)))
    monkeypatch.setattr(
        backtest,
        "_recal_oos_gate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled gate must not evaluate")
        ),
    )
    try:
        report = backtest.run_backtest(
            ledger, bootstrap_weights=True, include_diagnostics=False,
        )
    finally:
        ledger.close()

    assert report["recal_oos_gate"]["status"] == "DISABLED"
    assert report["recal_oos_gate"]["adopted"] is False
    assert report["weights_written"] is False
    assert writes == []


def test_malformed_positive_receipt_cannot_write_weights(tmp_path, monkeypatch):
    ledger = _ledger_with_weight_candidate(tmp_path)
    writes: list[dict[str, float]] = []
    monkeypatch.setenv("DUMMY_DAEMON_ALERTS", "0")
    monkeypatch.setattr(ledger, "update_weights", lambda batch: writes.append(dict(batch)))
    monkeypatch.setattr(
        backtest,
        "_recal_oos_gate",
        lambda *_args, **_kwargs: {"status": "OK", "adopted": True},
    )
    try:
        report = backtest.run_backtest(
            ledger, bootstrap_weights=True, include_diagnostics=False,
        )
    finally:
        ledger.close()

    assert report["recal_oos_gate"]["adopted"] is False
    assert report["recal_oos_gate"]["reason"] == (
        "invalid_or_non_improving_holdout_receipt"
    )
    assert report["weights_written"] is False
    assert writes == []


def test_complete_improvement_receipt_allows_only_weight_recalibration(
    tmp_path, monkeypatch,
):
    ledger = _ledger_with_weight_candidate(tmp_path)
    writes: list[dict[str, float]] = []
    monkeypatch.setattr(ledger, "update_weights", lambda batch: writes.append(dict(batch)))
    monkeypatch.setattr(
        backtest,
        "_recal_oos_gate",
        lambda *_args, **_kwargs: _valid_improvement_receipt(),
    )
    try:
        report = backtest.run_backtest(
            ledger, bootstrap_weights=True, include_diagnostics=False,
        )
    finally:
        ledger.close()

    assert report["recal_oos_gate"]["adopted"] is True
    assert report["recal_oos_gate"]["execution_authority"] is False
    assert report["recal_oos_gate"]["capital_authority"] is False
    assert report["weights_written"] is True
    assert len(writes) == 1
