"""Fill-conditioned loss deconstruction (WS-A1).

The loss engine's fill-batch mode localizes where the FILLED (adversely
selected) trades lose, over the witnessed / would-have-filled subset only.
These tests assert the subset restriction, the pooled small-sample headline,
determinism, the runner's ``--fills`` entrypoint, and the no-mutation safety
property that the whole loss engine is built around.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.loss_engine import (
    build_fill_loss_attribution,
    build_loss_attribution,
    filled_market_tickers,
)
from autonomy.strategy_miner import MinedRow
from autonomy.taxonomy import grading_scope

REPO_ROOT = Path(__file__).resolve().parent.parent
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _row(index: int, *, filled: bool, probability_yes: float, result_yes: bool) -> MinedRow:
    # Each row is its own event cluster; the filled/unfilled split is by ticker
    # prefix so filled_market_tickers-style membership is unambiguous.
    prefix = "KXFILLED" if filled else "KXUNFILL"
    ticker = f"{prefix}{index:04d}-26JAN{index:04d}-100"
    features = {"setup_score": float(index % 9), "market_type": "winner", "sport": "mlb"}
    when = (START + timedelta(hours=index)).isoformat()
    source = "mlb_structural_winner"
    return MinedRow(
        source=source, ticker=ticker, event_cluster=ticker.rsplit("-", 1)[0],
        created_at=when, probability_yes=probability_yes, market_probability=0.5,
        result_yes=result_yes, features=features,
        scope=grading_scope(source, ticker, features),
    )


def _rows() -> tuple[list[MinedRow], set[str]]:
    """Filled rows bleed (confidently wrong); unfilled rows are sharp."""
    rows: list[MinedRow] = []
    filled_tickers: set[str] = set()
    for i in range(16):
        row = _row(i, filled=True, probability_yes=0.9, result_yes=False)
        rows.append(row)
        filled_tickers.add(row.ticker)
    for i in range(16, 32):
        rows.append(_row(i, filled=False, probability_yes=0.9, result_yes=True))
    return rows, filled_tickers


def test_fill_attribution_restricts_to_filled_subset():
    rows, filled_tickers = _rows()
    attribution = build_fill_loss_attribution(
        rows, filled_tickers, now_iso="2026-07-16T00:00:00+00:00",
    )
    assert attribution["selection"] == "witnessed_or_would_have_filled_markets"
    assert attribution["filled_markets"] == 16
    assert attribution["fill_settled_rows"] == 16
    # Only the filled (bleeding) rows drive the pass; the sharp unfilled rows
    # are excluded, so the pooled edge is negative.
    assert attribution["pooled_cluster_edge"] < 0.0
    assert attribution["pooled_event_clusters"] == 16
    lower, upper = attribution["pooled_cluster_edge_ci95"]
    assert lower is not None and upper is not None
    assert lower <= attribution["pooled_cluster_edge"] <= upper


def test_fill_attribution_differs_from_full_attribution():
    rows, filled_tickers = _rows()
    full = build_loss_attribution(rows, now_iso="2026-07-16T00:00:00+00:00")
    fills = build_fill_loss_attribution(
        rows, filled_tickers, now_iso="2026-07-16T00:00:00+00:00",
    )
    # The full pass sees 32 settled rows; the fill pass sees only the 16 filled.
    assert full["settled_rows"] == 32
    assert fills["settled_rows"] == 16


def test_fill_attribution_deterministic():
    rows, filled_tickers = _rows()
    first = build_fill_loss_attribution(rows, filled_tickers, now_iso="2026-07-16T00:00:00+00:00")
    second = build_fill_loss_attribution(rows, filled_tickers, now_iso="2026-07-16T00:00:00+00:00")
    assert first == second


def test_empty_filled_set_is_well_formed():
    rows, _ = _rows()
    attribution = build_fill_loss_attribution(rows, set(), now_iso="2026-07-16T00:00:00+00:00")
    assert attribution["filled_markets"] == 0
    assert attribution["fill_settled_rows"] == 0
    assert attribution["pooled_cluster_edge"] is None
    assert attribution["scopes"] == []


# ----------------------------------------------------------------- ledger query


def _seed_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT, market_ticker TEXT,
            kind TEXT, fill_count INTEGER DEFAULT 0
        );
        """
    )
    conn.executemany(
        "INSERT INTO outcomes(decision_id, market_ticker, kind, fill_count) VALUES (?,?,?,?)",
        [
            ("d1", "KXA-1", "SHADOW", 0),
            ("d1", "KXA-1", "FILLED", 1),
            ("d2", "KXB-1", "SHADOW", 0),
            ("d2", "KXB-1", "EXPIRED", 0),
            ("d3", "KXC-1", "PARTIALLY_FILLED", 2),
        ],
    )
    conn.commit()
    return conn


def test_filled_market_tickers_finds_only_filled_markets():
    conn = _seed_conn()
    try:
        assert filled_market_tickers(conn) == {"KXA-1", "KXC-1"}
    finally:
        conn.close()


# ----------------------------------------------------------------- runner


def _build_file_ledger(path: Path) -> None:
    from autonomy.ledger import AutonomyLedger
    from autonomy.ontology import OutcomeKind, Signal, TradeOutcome

    ledger = AutonomyLedger(db_path=path)
    try:
        for i in range(20):
            filled = i < 10
            prefix = "KXFILLED" if filled else "KXUNFILL"
            ticker = f"{prefix}{i:04d}-26JAN{i:04d}-100"
            when = (START + timedelta(hours=i)).isoformat()
            ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                        probability_yes=0.5, uncertainty=0.1,
                                        rationale="", created_at=when))
            ledger.record_signal(Signal(
                source="mlb_structural_winner", market_ticker=ticker,
                probability_yes=0.9, uncertainty=0.1, rationale="",
                features={"market_type": "winner", "sport": "mlb", "setup_score": float(i % 9)},
                created_at=when))
            ledger.record_settlement(ticker, result_yes=not filled)
            if filled:
                ledger.record_outcome(TradeOutcome(
                    decision_id=f"d{i}", market_ticker=ticker, kind=OutcomeKind.FILLED,
                    order_id=f"shadow-d{i}", fill_count=1, fill_price_cents=48,
                    pnl_cents=None, broker_contacted=False, created_at=when))
    finally:
        ledger.close()


def _load_script_module():
    script_path = REPO_ROOT / "scripts" / "run_dummy_loss_engine.py"
    spec = importlib.util.spec_from_file_location("run_dummy_loss_engine_fills_under_test", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_fills_mode_writes_fill_artifact(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.db"
    _build_file_ledger(db_path)
    out_path = tmp_path / "loss_attribution_fills.json"

    module = _load_script_module()
    monkeypatch.setattr(
        sys, "argv",
        ["run_dummy_loss_engine.py", "--db", str(db_path), "--out", str(out_path),
         "--fills", "--no-narration"],
    )
    rc = module.main()
    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["selection"] == "witnessed_or_would_have_filled_markets"
    assert payload["filled_markets"] == 10
    assert "pooled_cluster_edge" in payload


def _hash_source_tree() -> dict[str, str | None]:
    digests: dict[str, str | None] = {}
    for path in sorted((REPO_ROOT / "autonomy").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digests[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    promotions_path = REPO_ROOT / "runtime" / "autonomy" / "promotions.json"
    digests[str(promotions_path)] = (
        hashlib.sha256(promotions_path.read_bytes()).hexdigest()
        if promotions_path.exists() else None
    )
    return digests


def test_fills_run_mutates_no_source_or_promotions(tmp_path):
    """The fill-batch runner is a propose-only artifact writer, exactly like
    the full loss engine: an end-to-end ``--fills`` run must leave every
    autonomy/*.py and promotions.json byte-identical."""
    before = _hash_source_tree()
    db_path = tmp_path / "ledger.db"
    _build_file_ledger(db_path)
    out_path = tmp_path / "loss_attribution_fills.json"
    script = REPO_ROOT / "scripts" / "run_dummy_loss_engine.py"
    result = subprocess.run(
        [sys.executable, str(script), "--db", str(db_path), "--out", str(out_path),
         "--fills", "--no-narration"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert out_path.exists()
    assert _hash_source_tree() == before
