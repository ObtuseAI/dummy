"""Derived source-reported availability unlocks retro seasons honestly."""
from __future__ import annotations

from datetime import datetime, timezone

from autonomy.ingest.provenance import (
    AVAILABILITY_BASIS,
    stamp_retro_source_reported,
)
from autonomy.sports.history_store import SportsHistoryStore


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _row(**overrides):
    row = {
        "game_id": "g1", "league": "nba", "season": 2023,
        "start_time": "2023-11-06T00:00Z", "status": "final",
        "home": "BOS", "away": "NYK", "home_score": 101, "away_score": 99,
        "source": "sportsdataverse",
    }
    row.update(overrides)
    return row


def test_completed_retro_row_gets_source_reported_bound():
    row = _row()
    assert stamp_retro_source_reported([row], now=NOW) == 1
    assert row["provenance_quality"] == "source_reported"
    assert row["result_available_at"] == "2023-11-06T12:00:00+00:00"
    assert row["received_at"] == NOW.isoformat()
    assert row["extra"]["availability_basis"] == AVAILABILITY_BASIS


def test_unparseable_or_naive_start_time_stays_unknown():
    rows = [_row(start_time="2023-11-06"), _row(start_time="garbage")]
    assert stamp_retro_source_reported(rows, now=NOW) == 0
    for row in rows:
        assert "provenance_quality" not in row


def test_incomplete_or_recent_rows_stay_unknown():
    rows = [
        _row(status="scheduled", home_score=None, away_score=None),
        _row(start_time="2026-07-22T05:00Z"),  # bound would land in the future
    ]
    assert stamp_retro_source_reported(rows, now=NOW) == 0
    for row in rows:
        assert "result_available_at" not in row


def test_existing_availability_is_never_overwritten():
    row = _row(
        result_available_at="2023-11-06T03:00:00+00:00",
        received_at="2023-11-06T03:00:00+00:00",
        provenance_quality="observed_at_receipt",
    )
    assert stamp_retro_source_reported([row], now=NOW) == 0
    assert row["provenance_quality"] == "observed_at_receipt"


def test_stamped_rows_become_evaluation_eligible(tmp_path):
    store = SportsHistoryStore(tmp_path / "lake.db")
    row = _row()
    stamp_retro_source_reported([row], now=NOW)
    store.upsert_games([row])
    eligible = store.evaluation_games("nba")
    assert [g["game_id"] for g in eligible] == ["g1"]


def test_observed_at_receipt_outranks_derived_backfill(tmp_path):
    store = SportsHistoryStore(tmp_path / "lake.db")
    observed = _row(
        result_available_at="2023-11-06T02:41:00+00:00",
        received_at="2023-11-06T02:41:00+00:00",
        provenance_quality="observed_at_receipt",
        source="espn",
    )
    store.upsert_games([observed])

    derived = _row()
    stamp_retro_source_reported([derived], now=NOW)
    store.upsert_games([derived])

    stored = store.conn.execute(
        "SELECT provenance_quality, result_available_at, received_at"
        " FROM games WHERE game_id='g1'"
    ).fetchone()
    assert stored["provenance_quality"] == "observed_at_receipt"
    assert stored["result_available_at"] == "2023-11-06T02:41:00+00:00"
    assert stored["received_at"] == "2023-11-06T02:41:00+00:00"
