"""Wave-83: the recal's out-of-sample gate.

The 6h recalibration derives trust weights in-sample; the gate scores the
freshly derived recipe against the incumbent live weights on a chronological
holdout and refuses the overwrite when the recipe grades worse. These tests
drive _recal_oos_gate directly on a synthetic settlements table.
"""
from __future__ import annotations

import sqlite3

from autonomy.backtest import _recal_oos_gate


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
        holdout_fraction=0.3, min_holdout=2,
    )
    assert gate["status"] == "OK"
    assert gate["adopted"] is True
    assert gate["oos_brier_delta"] <= gate["tolerance"]
    assert gate["holdout_markets"] == 6
    assert gate["train_markets"] == 14


def test_worse_recipe_is_refused():
    conn, signals, settlements = _build_case(good_in_holdout=False)
    # The sharp source flips in the holdout: the train-derived recipe upweights
    # it, the neutral incumbent doesn't -> candidate grades worse -> refuse.
    gate = _recal_oos_gate(
        conn, signals, settlements, {},
        holdout_fraction=0.3, min_holdout=2,
    )
    assert gate["status"] == "OK"
    assert gate["adopted"] is False
    assert gate["oos_brier_delta"] > gate["tolerance"]


def test_small_history_skips_and_adopts():
    conn, signals, settlements = _build_case(good_in_holdout=True)
    gate = _recal_oos_gate(
        conn, signals, settlements, {},
        holdout_fraction=0.3, min_holdout=500,
    )
    assert gate["status"] == "SKIPPED"
    assert gate["adopted"] is True
    assert "insufficient_holdout" in gate["reason"]
