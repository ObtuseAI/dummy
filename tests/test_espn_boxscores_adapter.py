"""Phase 1: ESPN boxscore adapter -> lake (no network; injected fetch/parse)."""
from __future__ import annotations

from dataclasses import dataclass

from autonomy.ingest.espn_boxscores import ingest_boxscores
from autonomy.sports.history_store import SportsHistoryStore


@dataclass
class _Box:
    game_id: str
    team: str
    stats: dict


def _seed_games(st):
    for i in range(3):
        st.upsert_game({"game_id": f"g{i}", "league": "wnba", "season": 2025,
                        "start_time": f"2025-06-0{i + 1}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 88, "away_score": 74, "status": "final", "source": "t"})


def test_ingests_missing_and_is_resumable(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    _seed_games(st)
    calls = []

    def fake_fetch(league, gid):
        calls.append(gid)
        return {"id": gid}

    def fake_parse(league, summary):
        gid = summary["id"]
        return [_Box(gid, "AAA", {"fieldGoalsMade": 40, "fieldGoalsAttempted": 85}),
                _Box(gid, "BBB", {"fieldGoalsMade": 33, "fieldGoalsAttempted": 85})]

    res = ingest_boxscores(st, "wnba", fetch_summary=fake_fetch, parse=fake_parse,
                           min_interval=0, sleep=lambda s: None,
                           received_at="2025-06-10T00:00:00Z")
    assert res["games"] == 3 and res["rows"] == 12 and len(calls) == 3
    envelope = st.conn.execute(
        "SELECT DISTINCT source_available_at, received_at FROM boxscores",
    ).fetchall()
    assert [tuple(row) for row in envelope] == [
        ("2025-06-10T00:00:00Z", "2025-06-10T00:00:00Z"),
    ]
    # resumable: a second run fetches nothing (all games now have boxscores)
    calls.clear()
    res2 = ingest_boxscores(st, "wnba", fetch_summary=fake_fetch, parse=fake_parse,
                            min_interval=0, sleep=lambda s: None,
                            received_at="2025-06-11T00:00:00Z")
    assert res2["queued"] == 0 and calls == []
    st.close()


def test_bad_summary_is_skipped(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    _seed_games(st)

    def boom(league, gid):
        raise RuntimeError("500")

    res = ingest_boxscores(st, "wnba", fetch_summary=boom, parse=lambda t, s: [],
                           min_interval=0, sleep=lambda s: None)
    assert res["errors"] == 3 and res["rows"] == 0
    st.close()


def test_an_ingest_that_fails_every_fetch_is_not_recorded_as_ok(tmp_path):
    """A run where nothing succeeded must not be logged as a success.

    Regression for an eight-day silent outage: 19 scheduled tasks ran on a
    venv with no httpx, so every fetch raised ModuleNotFoundError. The
    per-item except swallowed each one, and this function still recorded
    status "ok" -- producing
        {"games": 0, "errors": 102901, "queued": 102901}
    with status "ok" on 102,901 consecutive failures. The error count was
    right there in the payload and nothing acted on it.
    """
    st = SportsHistoryStore(tmp_path / "h.db")
    _seed_games(st)

    def dead_fetch(league, gid):
        raise RuntimeError("upstream down")

    result = ingest_boxscores(st, league="wnba", fetch_summary=dead_fetch)

    assert result["queued"] == 3
    assert result["games"] == 0
    assert result["errors"] == 3

    logged = st.conn.execute(
        "SELECT status FROM ingest_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert logged[0] != "ok", "an all-failed run must not report ok"
    assert "error" in logged[0]
    st.close()


def test_a_run_with_nothing_queued_still_reports_ok(tmp_path):
    """An empty work queue is success, not failure.

    The guard above must key on "attempted and all failed", not merely on
    zero rows -- an already-complete league legitimately ingests nothing.
    """
    st = SportsHistoryStore(tmp_path / "h.db")

    def unused_fetch(league, gid):  # pragma: no cover - must never be called
        raise AssertionError("nothing should be fetched")

    result = ingest_boxscores(st, league="wnba", fetch_summary=unused_fetch)

    assert result["queued"] == 0
    assert result["errors"] == 0
    logged = st.conn.execute(
        "SELECT status FROM ingest_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert logged[0] == "ok"
    st.close()
