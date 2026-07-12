"""Strategy miner: planted edges are found, noise is rejected, honesty holds."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from autonomy.strategy_miner import (
    MinedRow,
    load_settled_rows,
    mine_rules,
    mining_report,
)

START = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _seed_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL, market_ticker TEXT NOT NULL,
        probability_yes REAL NOT NULL, uncertainty REAL NOT NULL,
        rationale TEXT NOT NULL, features TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'live',
        ingested_at TEXT NOT NULL, ingest_version INTEGER NOT NULL DEFAULT 2
    );
    CREATE TABLE settlements (
        market_ticker TEXT PRIMARY KEY, result_yes INTEGER NOT NULL,
        settled_at TEXT NOT NULL
    );
    """)


def _insert_signal(conn, source, ticker, probability, features, created_at):
    conn.execute(
        "INSERT INTO signals (source, market_ticker, probability_yes, uncertainty,"
        " rationale, features, created_at, mode, ingested_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (source, ticker, probability, 0.1, "t", json.dumps(features),
         created_at, "live", created_at),
    )


def _planted_db(rows: int = 200) -> sqlite3.Connection:
    """Signals where setup_score > 0.3 predicts wins the market misprices.

    Planted edge: high-setup rows settle YES 90% of the time while the
    market says 50%; the model says 70% (sharper). Low-setup rows are pure
    coin flips the model also calls 50/50 (no edge anywhere).
    """
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    for index in range(rows):
        when = (START + timedelta(hours=index)).isoformat()
        ticker = f"KXBTCD-26JUN{index:04d}-T70000"
        high_setup = index % 2 == 0
        # Deterministic outcome pattern: 90% YES for high-setup, 50% for low.
        result_yes = (index % 10) < 9 if high_setup else (index % 2 == 0)
        features = {
            "setup_score": 0.6 if high_setup else 0.05,
            "mtf_alignment": 0.4 if high_setup else -0.1,
            "hours_to_close": 24.0,
        }
        model_probability = 0.70 if high_setup else 0.50
        _insert_signal(conn, "crypto_structure_swing", ticker,
                       model_probability, features, when)
        _insert_signal(conn, "market_prior", ticker, 0.50, {}, when)
        conn.execute(
            "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
            " VALUES (?,?,?)",
            (ticker, int(result_yes), when),
        )
    conn.commit()
    return conn


def test_load_settled_rows_joins_market_prior_point_in_time():
    conn = _planted_db(60)
    rows = load_settled_rows(conn)
    assert len(rows) == 60
    sample = rows[0]
    assert sample.source == "crypto_structure_swing"
    assert sample.market_probability == 0.50
    assert sample.features["setup_score"] in (0.6, 0.05)
    # A signal with no contemporaneous market prior is excluded outright.
    _insert_signal(conn, "crypto_structure_swing", "KXBTCD-26JUNORPHAN-T70000",
                   0.7, {}, (START + timedelta(days=90)).isoformat())
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at) VALUES (?,?,?)",
        ("KXBTCD-26JUNORPHAN-T70000", 1, (START + timedelta(days=91)).isoformat()),
    )
    conn.commit()
    assert len(load_settled_rows(conn)) == 60


def test_miner_finds_planted_setup_edge_out_of_sample():
    conn = _planted_db(240)
    report = mining_report(conn, now_iso="2026-07-12T00:00:00+00:00")
    assert report["settled_rows"] == 240
    assert report["candidate_count"] >= 1
    candidates = [rule for rule in report["rules"] if rule["verdict"] == "candidate"]
    assert any("setup_score >" in rule["rule"] for rule in candidates)
    top = candidates[0]
    assert top["test_brier_edge"] > 0
    assert top["test_ci95"][0] > 0
    assert top["n_train"] >= 30 and top["n_test"] >= 20


def test_miner_rejects_pure_noise_and_discloses_family_size():
    """Model disagrees with the market but has NO real relationship to the
    outcome: nothing may qualify, and the multiple-testing exposure must be
    disclosed in the artifact."""
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    for index in range(240):
        when = (START + timedelta(hours=index)).isoformat()
        ticker = f"KXETHD-26JUN{index:04d}-T3500"
        # Model alternates 0.6/0.4 on a cadence decoupled from both the
        # mined feature and the outcome pattern.
        model_probability = 0.6 if (index % 3) == 0 else 0.4
        _insert_signal(conn, "crypto_structure_swing", ticker, model_probability,
                       {"setup_score": (index % 7) / 7.0, "hours_to_close": 12.0},
                       when)
        _insert_signal(conn, "market_prior", ticker, 0.5, {}, when)
        conn.execute(
            "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
            " VALUES (?,?,?)", (ticker, (index // 5) % 2, when),
        )
    conn.commit()
    report = mining_report(conn, now_iso="2026-07-12T00:00:00+00:00")
    assert report["candidate_count"] == 0
    assert "rules_tested" in report and "expected_false_positives" in report
    assert report["expected_false_positives"] == round(report["rules_tested"] * 0.025, 2)


def test_walk_forward_kills_train_only_mirages():
    """An edge that exists ONLY early (regime that died) must not qualify."""
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    for index in range(240):
        when = (START + timedelta(hours=index)).isoformat()
        ticker = f"KXSOLD-26JUN{index:04d}-T160"
        early = index < 144  # the train window
        high = index % 2 == 0
        # Early: high-setup wins 90%. Late: the edge dies -- outcomes are
        # 50/50 for high-setup rows (index % 4 decouples from the parity
        # that defines "high", so half the even rows win and half lose).
        if early:
            result_yes = ((index % 10) < 9) if high else (index % 2 == 0)
        else:
            result_yes = (index % 4) < 2
        _insert_signal(conn, "crypto_structure_swing", ticker,
                       0.7 if high else 0.5,
                       {"setup_score": 0.6 if high else 0.05,
                        "hours_to_close": 24.0}, when)
        _insert_signal(conn, "market_prior", ticker, 0.5, {}, when)
        conn.execute(
            "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
            " VALUES (?,?,?)", (ticker, int(result_yes), when),
        )
    conn.commit()
    report = mining_report(conn, now_iso="2026-07-12T00:00:00+00:00")
    for rule in report["rules"]:
        if "setup_score >" in rule["rule"]:
            assert rule["verdict"] == "rejected"
    assert report["candidate_count"] == 0


def test_event_cluster_purging_drops_straddlers_and_keeps_fresh_clusters():
    # Clusters 0-4 span the whole window (straddle the split); clusters
    # named by index exist only in the late window and must SURVIVE purge.
    rows = [
        MinedRow(
            "s", f"KXBTCD-26JUL{index:03d}-T70000",
            f"KXBTCD-26JUL{index % 5:02d}" if index < 60 else f"KXBTCD-26JULLATE{index:03d}",
            (START + timedelta(hours=index)).isoformat(), 0.6, 0.5, True, {},
        )
        for index in range(100)
    ]
    from autonomy.strategy_miner import _purged_split

    train, test = _purged_split(rows)
    train_clusters = {row.event_cluster for row in train}
    assert test, "late-only clusters must be retained in the test fold"
    assert all(row.event_cluster not in train_clusters for row in test)
    assert all(row.event_cluster.startswith("KXBTCD-26JULLATE") for row in test)
