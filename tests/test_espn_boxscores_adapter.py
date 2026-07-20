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
                           min_interval=0, sleep=lambda s: None)
    assert res["games"] == 3 and res["rows"] == 12 and len(calls) == 3
    # resumable: a second run fetches nothing (all games now have boxscores)
    calls.clear()
    res2 = ingest_boxscores(st, "wnba", fetch_summary=fake_fetch, parse=fake_parse,
                            min_interval=0, sleep=lambda s: None)
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
