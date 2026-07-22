"""Strategy miner: planted edges are found, noise is rejected, honesty holds."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import autonomy.strategy_miner as strategy_miner
from autonomy.strategy_miner import (
    MinedRow,
    Predicate,
    Rule,
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
    CREATE TABLE decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_ticker TEXT NOT NULL, created_at TEXT NOT NULL
    );
    """)


def _insert_signal(
    conn,
    source,
    ticker,
    probability,
    features,
    created_at,
    *,
    mode="live",
    ingested_at=None,
):
    conn.execute(
        "INSERT INTO signals (source, market_ticker, probability_yes, uncertainty,"
        " rationale, features, created_at, mode, ingested_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (source, ticker, probability, 0.1, "t", json.dumps(features),
         created_at, mode, ingested_at or created_at),
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


def test_load_settled_rows_never_uses_a_future_prior():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    ticker = "KXMLBGAME-26JUN01AAABBB-AAA"
    past = START.isoformat()
    signal_time = (START + timedelta(minutes=5)).isoformat()
    future = (START + timedelta(minutes=6)).isoformat()
    settled = (START + timedelta(minutes=20)).isoformat()
    _insert_signal(conn, "market_prior", ticker, 0.41, {}, past)
    _insert_signal(conn, "test_model", ticker, 0.63, {}, signal_time)
    # This prior is closer in wall-clock time, but it did not exist when the
    # model emitted. The old nearest-neighbor join incorrectly selected it.
    _insert_signal(conn, "market_prior", ticker, 0.91, {}, future)
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (ticker, 1, settled),
    )

    future_only = "KXMLBGAME-26JUN01CCCDDD-CCC"
    _insert_signal(conn, "test_model", future_only, 0.62, {}, signal_time)
    _insert_signal(conn, "market_prior", future_only, 0.88, {}, future)
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (future_only, 1, settled),
    )
    conn.commit()

    rows = load_settled_rows(conn)
    assert [(row.ticker, row.market_probability) for row in rows] == [
        (ticker, 0.41),
    ]


def test_load_settled_rows_quarantines_late_retro_and_post_decision_rows():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    settled = (START + timedelta(minutes=20)).isoformat()

    late = "KXMLBGAME-26JUN01LATEAAA-LATE"
    _insert_signal(conn, "market_prior", late, 0.43, {}, START.isoformat())
    _insert_signal(
        conn,
        "test_model",
        late,
        0.64,
        {},
        (START + timedelta(minutes=2)).isoformat(),
        ingested_at=(START + timedelta(minutes=21)).isoformat(),
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (late, 1, settled),
    )

    retro = "KXMLBGAME-26JUN01RETROA-RETRO"
    _insert_signal(conn, "market_prior", retro, 0.44, {}, START.isoformat())
    _insert_signal(
        conn,
        "test_model",
        retro,
        0.65,
        {},
        (START + timedelta(minutes=2)).isoformat(),
        mode="retro",
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (retro, 1, settled),
    )

    retro_prior = "KXMLBGAME-26JUN01RETROP-RETROP"
    _insert_signal(
        conn, "market_prior", retro_prior, 0.45, {}, START.isoformat(), mode="retro",
    )
    _insert_signal(
        conn,
        "test_model",
        retro_prior,
        0.66,
        {},
        (START + timedelta(minutes=2)).isoformat(),
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (retro_prior, 1, settled),
    )

    decided = "KXMLBGAME-26JUN01DECIDE-DECIDE"
    _insert_signal(conn, "market_prior", decided, 0.40, {}, START.isoformat())
    _insert_signal(
        conn,
        "test_model",
        decided,
        0.55,
        {},
        (START + timedelta(minutes=1)).isoformat(),
    )
    conn.execute(
        "INSERT INTO decisions (market_ticker, created_at) VALUES (?,?)",
        (decided, (START + timedelta(minutes=5)).isoformat()),
    )
    _insert_signal(
        conn,
        "market_prior",
        decided,
        0.70,
        {},
        (START + timedelta(minutes=6)).isoformat(),
    )
    _insert_signal(
        conn,
        "test_model",
        decided,
        0.85,
        {},
        (START + timedelta(minutes=7)).isoformat(),
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (decided, 1, settled),
    )
    conn.commit()

    rows = load_settled_rows(conn)
    assert len(rows) == 1
    assert rows[0].ticker == decided
    assert rows[0].probability_yes == 0.55
    assert rows[0].market_probability == 0.40


def test_load_settled_rows_canonicalizes_duplicates_per_horizon():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    ticker = "KXBTCD-26JUN01-T70000"
    source = "crypto_structure_swing"
    _insert_signal(conn, "market_prior", ticker, 0.40, {}, START.isoformat())
    _insert_signal(
        conn,
        source,
        ticker,
        0.55,
        {"hours_to_close": 24.0},
        (START + timedelta(minutes=1)).isoformat(),
    )
    _insert_signal(
        conn,
        "market_prior",
        ticker,
        0.42,
        {},
        (START + timedelta(minutes=2)).isoformat(),
    )
    _insert_signal(
        conn,
        source,
        ticker,
        0.58,
        {"hours_to_close": 12.0},
        (START + timedelta(minutes=3)).isoformat(),
    )
    _insert_signal(
        conn,
        "market_prior",
        ticker,
        0.44,
        {},
        (START + timedelta(minutes=4)).isoformat(),
    )
    _insert_signal(
        conn,
        source,
        ticker,
        0.61,
        {"hours_to_close": 1.0},
        (START + timedelta(minutes=5)).isoformat(),
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (ticker, 1, (START + timedelta(minutes=20)).isoformat()),
    )
    conn.commit()

    rows = load_settled_rows(conn)
    assert len(rows) == 2
    by_horizon = {row.scope.rsplit("|", 1)[-1]: row for row in rows}
    assert set(by_horizon) == {"daily+", "hourly"}
    assert by_horizon["daily+"].probability_yes == 0.58
    assert by_horizon["daily+"].market_probability == 0.42
    assert by_horizon["hourly"].probability_yes == 0.61
    assert by_horizon["hourly"].market_probability == 0.44


def test_load_settled_rows_quarantines_malformed_provenance_and_outcomes():
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    settled = (START + timedelta(minutes=20)).isoformat()

    malformed_decision = "KXMLBGAME-26JUN01BADTIME-BADTIME"
    _insert_signal(
        conn, "market_prior", malformed_decision, 0.41, {}, START.isoformat(),
    )
    _insert_signal(
        conn,
        "test_model",
        malformed_decision,
        0.61,
        {},
        (START + timedelta(minutes=1)).isoformat(),
    )
    conn.execute(
        "INSERT INTO decisions (market_ticker, created_at) VALUES (?,?)",
        (malformed_decision, "not-a-timestamp"),
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (malformed_decision, 1, settled),
    )

    invalid_outcome = "KXMLBGAME-26JUN01BADRESULT-BADRESULT"
    _insert_signal(
        conn, "market_prior", invalid_outcome, 0.42, {}, START.isoformat(),
    )
    _insert_signal(
        conn,
        "test_model",
        invalid_outcome,
        0.62,
        {},
        (START + timedelta(minutes=1)).isoformat(),
    )
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (invalid_outcome, 2, settled),
    )

    naive_time = "KXMLBGAME-26JUN01NAIVE-NAIVE"
    _insert_signal(conn, "market_prior", naive_time, 0.43, {}, "2026-06-01T00:00:00")
    _insert_signal(conn, "test_model", naive_time, 0.63, {}, "2026-06-01T00:01:00")
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at)"
        " VALUES (?,?,?)",
        (naive_time, 1, settled),
    )
    conn.commit()

    assert load_settled_rows(conn) == []


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
    assert top["one_sided_p_value"] <= top["fdr_q_value"] <= 0.05
    assert top["fdr_rejected_null"] is True
    assert top["n_train"] >= 30 and top["n_test"] >= 20


def test_miner_rejects_pure_noise_and_reports_real_fdr_control():
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
    assert "expected_false_positives" not in report
    assert report["rules_tested"] == report["multiple_testing"]["family_size"]
    assert report["multiple_testing"]["method"] == "benjamini_hochberg"
    assert report["multiple_testing"]["target_fdr_q"] == 0.05
    assert report["multiple_testing"]["discoveries"] == 0
    assert report["multiple_testing"]["test_fold_role"] == "out_of_sample_verdict_only"


def test_fdr_keeps_one_planted_edge_and_rejects_large_null_family(monkeypatch):
    null_count = 200
    rules = [Rule((Predicate("planted", ">", 0.5),))]
    rules.extend(
        Rule((Predicate(f"null_{index}", ">", 0.5),))
        for index in range(null_count)
    )
    monkeypatch.setattr(strategy_miner, "candidate_rules", lambda _train: rules)
    rows: list[MinedRow] = []
    for index in range(150):
        in_train = index < 90
        local_test_index = index - 90
        result_yes = index < 45 if in_train else local_test_index < 30
        features = {"planted": 1.0 if result_yes else 0.0}
        null_match = (
            index < 10
            if in_train
            else local_test_index < 5 or 30 <= local_test_index < 35
        )
        features.update({
            f"null_{null_index}": 1.0 if null_match else 0.0
            for null_index in range(null_count)
        })
        rows.append(MinedRow(
            source="adversarial_fixture",
            ticker=f"KXTEST-26JUL{index:04d}-A",
            event_cluster=f"event-{index:04d}",
            created_at=(START + timedelta(hours=index)).isoformat(),
            probability_yes=0.70,
            market_probability=0.50,
            result_yes=result_yes,
            features=features,
        ))
    evidence, family_size = mine_rules(
        rows,
        min_train=10,
        min_test=10,
        min_test_clusters=10,
        top_k=500,
    )
    assert family_size == null_count + 1
    discoveries = [item for item in evidence if item.fdr_rejected_null]
    candidates = [item for item in evidence if item.verdict == "candidate"]
    assert [item.rule for item in discoveries] == ["planted > 0.5"]
    assert [item.rule for item in candidates] == ["planted > 0.5"]
    assert candidates[0].one_sided_p_value < 0.05 / family_size
    assert candidates[0].fdr_q_value < 0.05
    assert all(
        item.verdict == "rejected"
        for item in evidence if item.rule.startswith("null_")
    )


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
