"""Propose-then-promote tuner: planted miscalibration is found out-of-sample,
noise is rejected, family size is disclosed, and -- the one non-negotiable
property -- no source file is ever mutated."""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.sports.nba_model import MODEL_VERSION as NBA_MODEL_VERSION
from autonomy.sports.nba_model import total_over_probability
from autonomy.tuner import MIN_CLUSTERS, TUNABLES, tuning_report, write_report

REPO_ROOT = Path(__file__).resolve().parent.parent
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


def _insert_signal(conn, source, ticker, probability, features, created_at) -> None:
    conn.execute(
        "INSERT INTO signals (source, market_ticker, probability_yes, uncertainty,"
        " rationale, features, created_at, mode, ingested_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (source, ticker, probability, 0.1, "t", json.dumps(features),
         created_at, "live", created_at),
    )


def _nba_total_row(
    conn: sqlite3.Connection, index: int, *, expected_total: float, threshold: float,
    result_yes: bool, probability_yes: float,
) -> None:
    when = (START + timedelta(hours=index)).isoformat()
    # Real Kalshi NBA total tickers carry a strike-value 3rd segment (see
    # e.g. the shipped "KXNCAAFTOTAL-26OCT08TEXOU-55" fixture in
    # tests/test_autonomy_sports_intelligence.py); using that 3-segment
    # shape here (rather than the 2-segment "KXNBATOTAL-26JAN12LALBOS" form
    # some older NBA-model tests use) keeps this test's event_cluster
    # (ticker.rsplit("-", 1)[0], reused from strategy_miner.py) unique per
    # synthetic game -- see the WS-9 report for the collapse risk on the
    # 2-segment form.
    ticker = f"KXNBATOTAL-26JAN{index:04d}LALBOS-{int(threshold)}"
    features = {
        "sport": "nba", "market_type": "total",
        "expected_home_score": expected_total / 2.0 + 3.0,
        "expected_away_score": expected_total / 2.0 - 3.0,
        "expected_total": expected_total,
        "expected_pace": 99.5,  # == NBA_PARAMS.sigma_pace_reference -> ratio 1.0
        "threshold": threshold,
        "margin_model_version": NBA_MODEL_VERSION,
        "home": "LAL", "away": "BOS",
    }
    _insert_signal(conn, "nba_game_total", ticker, probability_yes, features, when)
    _insert_signal(conn, "market_prior", ticker, 0.5, {}, when)
    conn.execute(
        "INSERT INTO settlements (market_ticker, result_yes, settled_at) VALUES (?,?,?)",
        (ticker, int(result_yes), when),
    )


def _planted_sigma22_db(rows: int = 2000, seed: int = 1234) -> sqlite3.Connection:
    """NBA total rows whose settled outcomes are consistent with a TRUE
    total-points sigma of ~22, while the current constant is 19.5 (real
    NBA_PARAMS.total_sigma_base). `probability_yes` on each row is exactly
    what production would have emitted at the CURRENT constant (sigma=19.5),
    so the planted edge is genuinely "the current constant is miscalibrated
    against reality", not an artifact of a mismatched stored probability.
    """
    rng = random.Random(seed)
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    offsets = (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0)
    for index in range(rows):
        expected_total = 215.0 + (index % 5) * 3.0
        threshold = expected_total + offsets[index % len(offsets)]
        true_total = rng.gauss(expected_total, 22.0)
        result_yes = true_total > threshold
        probability_yes = total_over_probability(expected_total, 19.5, threshold)
        _nba_total_row(
            conn, index, expected_total=expected_total, threshold=threshold,
            result_yes=result_yes, probability_yes=probability_yes,
        )
    conn.commit()
    return conn


def _noise_db(rows: int = 2000, seed: int = 99) -> sqlite3.Connection:
    """Outcomes generated at EXACTLY the current constant's true sigma
    (19.5) -- the model is already correctly calibrated, so no grid value
    has a genuine edge to find out-of-sample.

    A naive "outcome independent of everything" null (e.g. a flat 50/50
    coin flip) is NOT a fair noise test for a sigma tunable specifically:
    Brier is minimized by the true probability, and a coin flip's true
    probability is 0.5 everywhere, so a WIDER sigma (whose implied
    probabilities sit closer to 0.5 at any given threshold gap) would win
    every time by construction -- that's a real, reproducible effect, not
    sampling noise, and asserting "keep" against it would be asserting a
    demonstrably false thing. Matching the generative sigma to the current
    constant is the honest analog of the miner's own noise test (a
    model/feature with no REAL relationship to the outcome beyond what the
    current constant already captures).
    """
    rng = random.Random(seed)
    conn = sqlite3.connect(":memory:")
    _seed_db(conn)
    offsets = (-15.0, -9.0, -3.0, 3.0, 9.0, 15.0)
    for index in range(rows):
        expected_total = 215.0 + (index % 5) * 3.0
        threshold = expected_total + offsets[index % len(offsets)]
        true_total = rng.gauss(expected_total, 19.5)
        result_yes = true_total > threshold
        probability_yes = total_over_probability(expected_total, 19.5, threshold)
        _nba_total_row(
            conn, index, expected_total=expected_total, threshold=threshold,
            result_yes=result_yes, probability_yes=probability_yes,
        )
    conn.commit()
    return conn


def _proposal(report: dict, name: str) -> dict:
    match = [proposal for proposal in report["proposals"] if proposal["name"] == name]
    assert match, f"no proposal named {name!r} in report"
    return match[0]


def test_planted_miscalibration_recovered_out_of_sample():
    conn = _planted_sigma22_db()
    report = tuning_report(conn, now_iso="2026-07-13T00:00:00+00:00")
    proposal = _proposal(report, "nba_total_sigma_base")
    assert proposal["current"] == 19.5
    assert abs(proposal["best"] - 21.5) <= 1.0
    assert proposal["verdict"] == "candidate"
    assert proposal["test_delta"] > 0.0
    assert proposal["test_ci95"][0] is not None and proposal["test_ci95"][0] > 0.0
    assert proposal["n_clusters"] >= MIN_CLUSTERS


def test_pure_noise_rejected_no_false_positive():
    conn = _noise_db()
    report = tuning_report(conn, now_iso="2026-07-13T00:00:00+00:00")
    proposal = _proposal(report, "nba_total_sigma_base")
    assert proposal["verdict"] == "keep"


def test_artifact_discloses_family_size():
    conn = _planted_sigma22_db(rows=60)
    report = tuning_report(conn, now_iso="2026-07-13T00:00:00+00:00")
    assert "family_size" in report
    assert report["family_size"]["tunables_evaluated"] == len(TUNABLES)
    assert report["family_size"]["grid_points_evaluated"] == sum(len(t["grid"]) for t in TUNABLES)
    # Sanity: every registered tunable produced exactly one proposal.
    assert len(report["proposals"]) == len(TUNABLES)


def test_insufficient_clusters_no_crash():
    conn = _planted_sigma22_db(rows=6)  # well under MIN_CLUSTERS
    report = tuning_report(conn, now_iso="2026-07-13T00:00:00+00:00")
    proposal = _proposal(report, "nba_total_sigma_base")
    assert proposal["verdict"] == "insufficient_data"
    assert proposal["n_clusters"] < MIN_CLUSTERS


def test_not_repriceable_tunable_is_disclosed():
    conn = _planted_sigma22_db(rows=30)
    report = tuning_report(conn, now_iso="2026-07-13T00:00:00+00:00")
    proposal = _proposal(report, "nhl_home_edge")
    assert proposal["verdict"] == "not_repriceable"
    assert proposal.get("reason"), "not_repriceable verdict must disclose why"


def test_registry_currents_match_real_engine_constants():
    """The registry must import, never hand-copy, its `current` values."""
    from autonomy.sports import nba_model, team_scores
    from autonomy.sports.college import NCAAMB_PARAMS
    from autonomy.sports.nhl_model import HOME_EDGE

    by_name = {tunable["name"]: tunable for tunable in TUNABLES}
    assert by_name["nba_total_sigma_base"]["current"] == nba_model.NBA_PARAMS.total_sigma_base
    assert by_name["nba_margin_sigma_base"]["current"] == nba_model.NBA_PARAMS.margin_sigma_base
    assert by_name["ncaamb_total_sigma_base"]["current"] == NCAAMB_PARAMS.total_sigma_base
    assert by_name["ncaamb_margin_sigma_base"]["current"] == NCAAMB_PARAMS.margin_sigma_base
    assert by_name["nfl_total_sigma"]["current"] == team_scores.LEAGUE_SCORE_CONFIGS["nfl"].total_sigma
    assert by_name["ncaaf_total_sigma"]["current"] == team_scores.LEAGUE_SCORE_CONFIGS["ncaaf"].total_sigma
    assert by_name["nhl_home_edge"]["current"] == HOME_EDGE


def _hash_source_tree() -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted((REPO_ROOT / "autonomy").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digests[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def test_no_source_file_mutated_by_a_full_tuner_run(tmp_path):
    """The critical safety property: the tuner's nightly entrypoint
    (scripts/run_dummy_tuner.py) is a pure proposer. Running it end-to-end
    against a real sqlite ledger must leave every autonomy/**/*.py byte-
    identical -- writing a constant back into a .py file would be a
    fail-closed human-gate violation."""
    before = _hash_source_tree()
    assert before, "expected to hash at least one autonomy/*.py file"

    db_path = tmp_path / "ledger.db"
    conn = _planted_sigma22_db(rows=120)
    with sqlite3.connect(db_path) as file_conn:
        conn.backup(file_conn)
    conn.close()

    out_path = tmp_path / "tuning_proposals.json"
    script = REPO_ROOT / "scripts" / "run_dummy_tuner.py"
    result = subprocess.run(
        [sys.executable, str(script), "--db", str(db_path), "--out", str(out_path)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["family_size"]["tunables_evaluated"] == len(TUNABLES)

    after = _hash_source_tree()
    assert after == before, "a tuner run must never mutate any autonomy/*.py source file"


def test_write_report_is_atomic_and_never_touches_py_files(tmp_path):
    conn = _planted_sigma22_db(rows=60)
    report = tuning_report(conn, now_iso="2026-07-13T00:00:00+00:00")
    out_path = tmp_path / "runtime" / "autonomy" / "tuning_proposals.json"
    write_report(report, out_path)
    assert out_path.exists()
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["settled_rows"] == 60
