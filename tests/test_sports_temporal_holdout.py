"""Leakage and authority invariants for Sports Temporal Holdout Gate v2."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.temporal_holdout import (
    HoldoutAlreadyConsumed,
    HoldoutIntegrityError,
    MANIFEST_VERSION,
    _game_manifest_hashes,
    _metrics,
    run_temporal_holdout_gate,
)
from autonomy.sports.walk_forward import glicko_prediction_records


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _game(
    game_id: str, season: int, start: datetime, home: str = "AAA", away: str = "BBB",
    home_score: int = 30, away_score: int = 17, *, available_hours: float = 3.0,
) -> dict:
    available = start + timedelta(hours=available_hours)
    received = available + timedelta(minutes=5)
    return {
        "game_id": game_id,
        "league": "nfl",
        "season": season,
        "start_time": _iso(start),
        "status": "final",
        "home": home,
        "away": away,
        "home_score": home_score,
        "away_score": away_score,
        "source": "test-source",
        "provenance_url": f"https://example.test/{game_id}",
        "result_available_at": _iso(available),
        "received_at": _iso(received),
        "provenance_quality": "source_reported",
    }


def test_unknown_or_invalid_availability_is_fail_closed(tmp_path):
    store = SportsHistoryStore(tmp_path / "history.db")
    start = datetime(2025, 9, 1, 10, tzinfo=timezone.utc)
    unknown = _game("unknown", 2025, start)
    unknown.pop("result_available_at")
    unknown.pop("received_at")
    unknown.pop("provenance_quality")
    impossible = _game("impossible", 2025, start + timedelta(days=1))
    impossible["result_available_at"] = _iso(start)  # before this game starts
    known = _game("known", 2025, start + timedelta(days=2))
    store.upsert_games([unknown, impossible, known])

    assert [game["game_id"] for game in store.evaluation_games("nfl")] == ["known"]
    audit = store.evaluation_eligibility("nfl")
    assert audit["eligible"] == 1
    assert audit["rejection_reasons"] == {
        "invalid_timestamp_order": 1,
        "unknown_availability": 1,
    }
    before_receipt = known["received_at"]
    assert store.games_before(
        before_receipt, league="nfl", require_known_availability=True,
    ) == []
    after_receipt = _iso(datetime.fromisoformat(before_receipt) + timedelta(seconds=1))
    assert [game["game_id"] for game in store.games_before(
        after_receipt, league="nfl", require_known_availability=True,
    )] == ["known"]
    store.close()


def test_overlapping_unresolved_games_never_update_the_next_prediction(tmp_path):
    store = SportsHistoryStore(tmp_path / "history.db")
    day = datetime(2025, 9, 1, tzinfo=timezone.utc)
    # g1 has started but is not received when g2 begins. Both are available
    # before g3, so only g3 may learn from them.
    store.upsert_games([
        _game("g1", 2025, day + timedelta(hours=10), available_hours=4),
        _game("g2", 2025, day + timedelta(hours=12), away="CCC", available_hours=3),
        _game("g3", 2025, day + timedelta(hours=16), away="CCC", available_hours=3),
    ])
    records = {
        record["game_id"]: record
        for record in glicko_prediction_records(
            store, "nfl", home_advantage=0.0, include_training_ids=True,
        )
    }

    assert records["g1"]["training_game_ids"] == []
    assert records["g2"]["training_game_ids"] == []
    assert records["g2"]["probability"] == pytest.approx(0.5)
    assert records["g3"]["training_game_ids"] == ["g1", "g2"]
    assert records["g3"]["probability"] > 0.5
    store.close()


def _seed_three_seasons(store: SportsHistoryStore) -> None:
    for season in (2023, 2024, 2025):
        base = datetime(season, 9, 1, tzinfo=timezone.utc)
        for index in range(9):
            if index % 3 == 0:
                home, away, scores = "AAA", "BBB", (31, 17)
            elif index % 3 == 1:
                home, away, scores = "BBB", "CCC", (27, 20)
            else:
                home, away, scores = "AAA", "CCC", (35, 14)
            store.upsert_game(_game(
                f"{season}-{index}", season, base + timedelta(days=index),
                home=home, away=away, home_score=scores[0], away_score=scores[1],
            ))


def test_sealed_holdout_is_disjoint_one_shot_and_has_no_live_authority(tmp_path):
    store = SportsHistoryStore(tmp_path / "history.db")
    _seed_three_seasons(store)
    authority = tmp_path / "sports_champions.json"
    authority.write_text('{"sentinel":"unchanged"}', encoding="utf-8")
    authority_before = authority.read_bytes()
    artifact = tmp_path / "sports_temporal_holdout.json"

    report = run_temporal_holdout_gate(
        store,
        league="nfl",
        holdout_season=2025,
        artifact_path=artifact,
        confirm_completed_season=True,
        generated_at="2026-07-21T12:00:00+00:00",
        bootstrap_samples=200,
        seed=7,
    )

    assert report["status"] == "EVALUATED_RESEARCH_ONLY"
    assert report["split"]["all_splits_disjoint"] is True
    assert report["split"]["overlap_counts"] == {
        "train_validation": 0,
        "train_holdout": 0,
        "validation_holdout": 0,
    }
    assert report["candidate_selection"]["input_seasons"] == [2023, 2024]
    assert report["candidate_selection"]["holdout_season_present_in_selection"] is False
    assert report["sealed_holdout"]["used_for_candidate_selection"] is False
    assert report["sealed_holdout"]["consumed"] is True
    assert report["sealed_holdout"]["metrics"]["n"] == 9
    assert report["research_only"] is True
    assert report["execution_authority"] is False
    assert report["promotion_authority"] is False
    assert report["live_authority_mutated"] is False
    assert authority.read_bytes() == authority_before
    assert json.loads(artifact.read_text(encoding="utf-8")) == report

    claim = store.research_holdout_claim(report["sealed_holdout"]["seal_key"])
    sealed = report["sealed_holdout"]
    selection = report["candidate_selection"]
    assert sealed["manifest_version"] == MANIFEST_VERSION
    assert selection["manifest_version"] == MANIFEST_VERSION
    for key in ("game_ids_sha256", "manifest_sha256", "content_sha256", "outcomes_sha256"):
        assert _is_sha256(sealed[key])
    for key in (
        "input_game_ids_sha256",
        "input_manifest_sha256",
        "input_content_sha256",
        "input_outcomes_sha256",
    ):
        assert _is_sha256(selection[key])
    assert claim["manifest_version"] == MANIFEST_VERSION
    assert claim["holdout_manifest_hash"] == sealed["manifest_sha256"]
    assert claim["holdout_content_hash"] == sealed["content_sha256"]
    assert claim["holdout_outcomes_hash"] == sealed["outcomes_sha256"]
    assert claim["selection_manifest_hash"] == selection["input_manifest_sha256"]
    assert claim["selection_content_hash"] == selection["input_content_sha256"]
    assert claim["selection_outcomes_hash"] == selection["input_outcomes_sha256"]
    assert claim["execution_authority"] == 0
    assert claim["promotion_authority"] == 0
    with pytest.raises(HoldoutAlreadyConsumed):
        run_temporal_holdout_gate(
            store,
            league="nfl",
            holdout_season=2025,
            artifact_path=tmp_path / "second-look.json",
            confirm_completed_season=True,
            candidate_home_advantages=(5.0, 95.0),
            generated_at="2026-07-21T13:00:00+00:00",
            bootstrap_samples=100,
        )
    assert not (tmp_path / "second-look.json").exists()
    store.close()


@pytest.mark.parametrize("mutation", ("late_added_game", "corrected_outcome"))
def test_changed_holdout_manifest_cannot_reopen_consumed_scope(tmp_path, mutation):
    store = SportsHistoryStore(tmp_path / "history.db")
    _seed_three_seasons(store)
    first_artifact = tmp_path / "first.json"
    first = run_temporal_holdout_gate(
        store,
        league="nfl",
        holdout_season=2025,
        artifact_path=first_artifact,
        confirm_completed_season=True,
        generated_at="2026-07-21T12:00:00+00:00",
        bootstrap_samples=100,
    )
    claim_before = store.research_holdout_claim(first["sealed_holdout"]["seal_key"])

    if mutation == "late_added_game":
        store.upsert_game(_game(
            "2025-late",
            2025,
            datetime(2025, 10, 1, tzinfo=timezone.utc),
            home="DDD",
            away="EEE",
            home_score=24,
            away_score=21,
        ))
    else:
        store.upsert_game(_game(
            "2025-0",
            2025,
            datetime(2025, 9, 1, tzinfo=timezone.utc),
            home="AAA",
            away="BBB",
            home_score=17,
            away_score=31,
        ))

    current_holdout = [
        game for game in store.evaluation_games(league="nfl")
        if int(game["season"]) == 2025
    ]
    current_manifest = _game_manifest_hashes(current_holdout)
    sealed = first["sealed_holdout"]
    assert current_manifest["manifest_sha256"] != sealed["manifest_sha256"]
    assert current_manifest["outcomes_sha256"] != sealed["outcomes_sha256"]
    if mutation == "corrected_outcome":
        assert current_manifest["game_ids_sha256"] == sealed["game_ids_sha256"]
        assert current_manifest["content_sha256"] == sealed["content_sha256"]
    else:
        assert current_manifest["game_ids_sha256"] != sealed["game_ids_sha256"]
        assert current_manifest["content_sha256"] != sealed["content_sha256"]

    retry_artifact = tmp_path / f"{mutation}-retry.json"
    with pytest.raises(HoldoutAlreadyConsumed, match="scope already consumed"):
        run_temporal_holdout_gate(
            store,
            league="nfl",
            holdout_season=2025,
            artifact_path=retry_artifact,
            confirm_completed_season=True,
            generated_at="2026-07-21T13:00:00+00:00",
            bootstrap_samples=100,
        )
    assert not retry_artifact.exists()
    assert store.conn.execute(
        "SELECT COUNT(*) FROM research_holdout_consumptions"
    ).fetchone()[0] == 1
    assert store.research_holdout_claim(
        first["sealed_holdout"]["seal_key"]
    ) == claim_before
    store.close()


def test_legacy_scope_conflicts_are_preserved_immutable_and_fail_closed(tmp_path):
    db_path = tmp_path / "legacy-history.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE research_holdout_consumptions(
            seal_key TEXT PRIMARY KEY,
            league TEXT NOT NULL, holdout_season INTEGER NOT NULL,
            model TEXT NOT NULL, holdout_ids_hash TEXT NOT NULL,
            selection_ids_hash TEXT NOT NULL, consumed_at TEXT NOT NULL,
            execution_authority INTEGER NOT NULL DEFAULT 0,
            promotion_authority INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    connection.executemany(
        """INSERT INTO research_holdout_consumptions(
               seal_key,league,holdout_season,model,holdout_ids_hash,
               selection_ids_hash,consumed_at
           ) VALUES(?,?,?,?,?,?,?)""",
        (
            ("a" * 64, "nfl", 2025, "glicko", "c" * 64, "d" * 64, "2026-01-01"),
            ("b" * 64, "NFL", 2025, "GLICKO", "e" * 64, "f" * 64, "2026-01-02"),
        ),
    )
    connection.commit()
    connection.close()

    store = SportsHistoryStore(db_path)
    claims = store.research_holdout_claims_for_scope(
        league="nfl", holdout_season=2025, model="glicko",
    )
    assert len(claims) == 2
    assert {claim["seal_key"] for claim in claims} == {"a" * 64, "b" * 64}
    assert all(claim["manifest_version"] is None for claim in claims)
    assert store.claim_research_holdout(
        seal_key="1" * 64,
        league="nfl",
        holdout_season=2025,
        model="glicko",
        holdout_ids_hash="2" * 64,
        selection_ids_hash="3" * 64,
        manifest_version=MANIFEST_VERSION,
        holdout_manifest_hash="4" * 64,
        holdout_content_hash="5" * 64,
        holdout_outcomes_hash="6" * 64,
        selection_manifest_hash="7" * 64,
        selection_content_hash="8" * 64,
        selection_outcomes_hash="9" * 64,
        consumed_at="2026-02-01",
    ) is False
    with pytest.raises(sqlite3.IntegrityError, match="complete SHA-256 manifests"):
        store.conn.execute(
            """INSERT INTO research_holdout_consumptions(
                   seal_key,league,holdout_season,model,holdout_ids_hash,
                   selection_ids_hash,consumed_at
               ) VALUES(?,?,?,?,?,?,?)""",
            ("1" * 64, "nfl", 2026, "glicko", "2" * 64, "3" * 64, "2026-02-02"),
        )
    store.conn.rollback()
    for statement in (
        "UPDATE research_holdout_consumptions SET consumed_at='changed'",
        "DELETE FROM research_holdout_consumptions",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.conn.execute(statement)
        store.conn.rollback()
    assert store.conn.execute(
        "SELECT COUNT(*) FROM research_holdout_consumptions"
    ).fetchone()[0] == 2
    store.close()


def test_unknown_history_writes_blocked_artifact_without_consuming_holdout(tmp_path):
    store = SportsHistoryStore(tmp_path / "history.db")
    for season in (2023, 2024, 2025):
        game = _game(
            f"legacy-{season}", season,
            datetime(season, 9, 1, tzinfo=timezone.utc),
        )
        for field in ("result_available_at", "received_at", "provenance_quality"):
            game.pop(field)
        store.upsert_game(game)
    artifact = tmp_path / "blocked.json"

    report = run_temporal_holdout_gate(
        store,
        league="nfl",
        holdout_season=2025,
        artifact_path=artifact,
        confirm_completed_season=True,
        generated_at="2026-07-21T12:00:00+00:00",
    )

    assert report["status"] == "BLOCKED_INSUFFICIENT_POINT_IN_TIME_SEASONS"
    assert report["data_quality"]["rejection_reasons"] == {"unknown_availability": 3}
    assert report["sealed_holdout"]["consumed"] is False
    claims = store.conn.execute("SELECT COUNT(*) FROM research_holdout_consumptions").fetchone()[0]
    assert claims == 0
    assert report["execution_authority"] is False
    store.close()


def test_uncertainty_resamples_whole_dependency_event_clusters() -> None:
    # Ten correlated rows share one event cluster while one independent event
    # is an outlier. Row-wise resampling would almost never produce a Brier of
    # 1.0; a correct two-cluster bootstrap does when it draws the outlier twice.
    records = [
        {
            "game_id": f"correlated-{index}",
            "event_cluster": "event-a",
            "probability": 1.0,
            "outcome": 1,
        }
        for index in range(10)
    ]
    records.append({
        "game_id": "outlier",
        "event_cluster": "event-b",
        "probability": 1.0,
        "outcome": 0,
    })

    metrics = _metrics(records, bootstrap_samples=1000, seed=11)

    assert metrics["uncertainty"] == {
        "method": "dependency_event_cluster_bootstrap_95",
        "resampling_unit": "event_cluster",
        "event_clusters": 2,
        "correlated_records": 11,
        "resamples": 1000,
    }
    assert metrics["brier_ci95"] == {"lower": 0.0, "upper": 1.0}


def test_uncertainty_fails_closed_without_dependency_identity() -> None:
    with pytest.raises(HoldoutIntegrityError, match="requires an event_cluster"):
        _metrics([{"probability": 0.6, "outcome": 1}], bootstrap_samples=100)


def test_one_strict_season_remains_blocked_and_does_not_consume_holdout(tmp_path):
    store = SportsHistoryStore(tmp_path / "history.db")
    base = datetime(2025, 9, 1, tzinfo=timezone.utc)
    store.upsert_games([
        _game(f"only-{index}", 2025, base + timedelta(days=index))
        for index in range(9)
    ])
    artifact = tmp_path / "one-season-block.json"

    report = run_temporal_holdout_gate(
        store,
        league="nfl",
        holdout_season=2025,
        artifact_path=artifact,
        confirm_completed_season=True,
        generated_at="2026-07-22T12:00:00+00:00",
    )

    assert report["status"] == "BLOCKED_INSUFFICIENT_POINT_IN_TIME_SEASONS"
    assert report["available_strict_seasons"] == [2025]
    assert report["sealed_holdout"] == {"consumed": False, "metrics": None}
    assert store.conn.execute(
        "SELECT COUNT(*) FROM research_holdout_consumptions"
    ).fetchone()[0] == 0
    assert json.loads(artifact.read_text(encoding="utf-8")) == report
    store.close()
