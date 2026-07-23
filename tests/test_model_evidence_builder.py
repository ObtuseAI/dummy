"""Panel->authority on-ramp: real evidence, but provably no self-granted authority."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from forecasting.model_evidence_builder import (
    DEBATE_SOURCE,
    build_and_write,
)
from forecasting.model_probability_authority import (
    ModelProbabilityAuthorityRegistry,
    MODEL_PANEL_SOURCE,
)


NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def _seed(path, *, n_clusters: int, sharp: bool) -> str:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE signals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, market_ticker TEXT, probability_yes REAL,
            uncertainty REAL, rationale TEXT, created_at TEXT, mode TEXT,
            features TEXT, ingested_at TEXT, ingest_version INTEGER
        );
        CREATE TABLE settlements(market_ticker TEXT PRIMARY KEY, result_yes INTEGER);
        """
    )
    scope = None
    for i in range(n_clusters):
        # Distinct crypto event per cluster; 1h horizon -> known axis.
        ticker = f"KXBTC1H-26JUL{i:03d}1500-15"
        result = i % 2 == 0
        debate_p = (0.9 if result else 0.1) if sharp else 0.5
        market_p = 0.55 if result else 0.45
        features = {"market_category": "CRYPTO", "close_time": "2026-07-01T16:00:00+00:00"}
        for source, prob in (
            (DEBATE_SOURCE, debate_p), ("market_prior", market_p),
        ):
            conn.execute(
                "INSERT INTO signals(source, market_ticker, probability_yes,"
                " uncertainty, rationale, features, created_at, mode, ingested_at,"
                " ingest_version) VALUES (?,?,?,0.1,'',?,?, 'live','',2)",
                (source, ticker, prob, json.dumps(features), "2026-06-15T00:00:00+00:00"),
            )
        conn.execute(
            "INSERT INTO settlements(market_ticker, result_yes) VALUES (?,?)",
            (ticker, 1 if result else 0),
        )
    conn.commit()
    conn.close()
    return scope


def test_builder_writes_inert_evidence_and_eligibility(tmp_path):
    db = tmp_path / "ledger.db"
    _seed(str(db), n_clusters=40, sharp=True)
    artifact = tmp_path / "evidence.json"
    report_path = tmp_path / "eligibility.json"
    report = build_and_write(
        db, now=NOW, artifact_path=artifact, report_path=report_path,
    )
    assert report["dossier_authored"] is False
    doc = json.loads(artifact.read_text(encoding="utf-8"))
    assert doc["promotion_authority"] is False
    assert doc["scopes"], "expected at least one scope row"
    # 40 clusters is below the 300 bar -> not governance-eligible.
    assert report["governance_eligible_scopes"] == []
    (row,) = [s for s in report["scopes"] if s["independent_event_clusters"] == 40]
    assert any("below_300" in b for b in row["blockers"])


def test_evidence_artifact_alone_grants_no_authority(tmp_path):
    """The safety proof: even a fully-qualified evidence artifact grants ZERO
    authority, because authority requires a dossier the builder never writes."""
    db = tmp_path / "ledger.db"
    _seed(str(db), n_clusters=320, sharp=True)
    artifact = tmp_path / "evidence.json"
    report_path = tmp_path / "eligibility.json"
    report = build_and_write(
        db, now=NOW, artifact_path=artifact, report_path=report_path,
    )
    # This scope DID clear 300 clusters with positive edge...
    assert report["governance_eligible_scopes"], "expected an eligible scope"
    scope = report["governance_eligible_scopes"][0]
    assert scope.startswith(MODEL_PANEL_SOURCE)

    # ...yet the registry (which reads the DOSSIER, absent here) still blocks.
    registry = ModelProbabilityAuthorityRegistry(
        path=tmp_path / "model_probability_authority.json",
    )
    decision = registry.evaluate(scope, now=NOW)
    assert decision.authorized is False
    assert decision.weight == 0 or float(decision.weight) == 0.0


def test_unknown_scope_rows_are_excluded(tmp_path):
    db = tmp_path / "ledger.db"
    # sports market with no phase -> unknown axis -> excluded from evidence.
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE signals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, market_ticker TEXT,
            probability_yes REAL, uncertainty REAL, rationale TEXT, created_at TEXT,
            mode TEXT, features TEXT, ingested_at TEXT, ingest_version INTEGER
        );
        CREATE TABLE settlements(market_ticker TEXT PRIMARY KEY, result_yes INTEGER);
        """
    )
    for i in range(20):
        ticker = f"KXMLBGAME-26JUL{i:02d}AAABBB-AAA"
        for source, prob in ((DEBATE_SOURCE, 0.8), ("market_prior", 0.5)):
            conn.execute(
                "INSERT INTO signals(source, market_ticker, probability_yes,"
                " uncertainty, rationale, features, created_at, mode, ingested_at,"
                " ingest_version) VALUES (?,?,?,0.1,'','{}',?, 'live','',2)",
                (source, ticker, prob, "2026-06-15T00:00:00+00:00"),
            )
        conn.execute("INSERT INTO settlements VALUES (?,?)", (ticker, 1))
    conn.commit()
    conn.close()
    report = build_and_write(
        db, now=NOW,
        artifact_path=tmp_path / "e.json", report_path=tmp_path / "r.json",
    )
    # No known-axis scope -> no scopes at all (sports with unknown phase dropped).
    assert report["scopes"] == []
