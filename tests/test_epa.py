"""Phase 2: EPA aggregation + engine + walk-forward + adapter (no network)."""
from __future__ import annotations

from autonomy.ingest.nflfastr import aggregate_epa, ingest_nflfastr_epa
from autonomy.sports.epa import LakeEpa
from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.walk_forward import walk_forward_epa


def test_aggregate_epa_offense_and_defense():
    rows = [
        {"game_id": "g1", "posteam": "KC", "defteam": "BAL", "epa": "1.0"},
        {"game_id": "g1", "posteam": "KC", "defteam": "BAL", "epa": "0.0"},
        {"game_id": "g1", "posteam": "BAL", "defteam": "KC", "epa": "-0.5"},
        {"game_id": "g1", "posteam": "NA", "defteam": "KC", "epa": "9"},   # dropped
        {"game_id": "g1", "posteam": "KC", "defteam": "BAL", "epa": ""},    # dropped
    ]
    agg = {(a["game_id"], a["team"]): a["stats"] for a in aggregate_epa(rows)}
    kc = agg[("g1", "KC")]
    assert kc["off_epa"] == 1.0 and kc["off_plays"] == 2.0        # KC offense
    assert kc["def_epa"] == -0.5 and kc["def_plays"] == 1.0       # KC defense allowed
    bal = agg[("g1", "BAL")]
    assert bal["def_epa"] == 1.0 and bal["def_plays"] == 2.0      # BAL allowed KC's EPA


def _epa_box(gid, team, off_per, off_n, def_per, def_n, *, available_at=None):
    row = {"game_id": gid, "team": team,
           "stats": {"off_epa": off_per * off_n, "off_plays": off_n,
                     "def_epa": def_per * def_n, "def_plays": def_n}}
    if available_at is not None:
        row.update(source_available_at=available_at, received_at=available_at)
    return row


def _seed(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    for i in range(6):
        gid = f"g{i}"
        st.upsert_game({"game_id": gid, "league": "nfl", "season": 2025,
                        "start_time": f"2025-09-{i + 1:02d}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 31, "away_score": 17, "status": "final", "source": "t",
                        "result_available_at": f"2025-09-{i + 1:02d}T03:00:00Z",
                        "received_at": f"2025-09-{i + 1:02d}T03:05:00Z",
                        "provenance_quality": "source_reported"})
        available_at = f"2025-09-{i + 1:02d}T03:05:00Z"
        st.record_team_boxscores([
            _epa_box(gid, "AAA", 0.15, 65, -0.05, 63, available_at=available_at),
            _epa_box(gid, "BBB", 0.00, 62, 0.10, 66, available_at=available_at),
        ])
    return st


def test_lake_epa_strength_and_walk_forward(tmp_path):
    st = _seed(tmp_path)
    m = LakeEpa(st, league="nfl", min_plays=100, min_games=2)
    t = "2025-10-01T00:00:00Z"
    assert m.strength("AAA", t) > m.strength("BBB", t)
    assert m.matchup_prob("AAA", "BBB", t) > 0.5
    r = walk_forward_epa(st, league="nfl", min_games=2)
    assert r["n"] >= 3 and r["hit_rate"] >= 0.9
    st.close()


def test_ingest_nflfastr_epa_no_network(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game({"game_id": "2024_01_BAL_KC", "league": "nfl", "season": 2024,
                    "start_time": "2024-09-05T00:00:00Z", "home": "KC", "away": "BAL",
                    "home_score": 27, "away_score": 20, "status": "final", "source": "t"})
    csv = "game_id,posteam,defteam,epa\n2024_01_BAL_KC,KC,BAL,0.5\n2024_01_BAL_KC,BAL,KC,-0.2\n"
    res = ingest_nflfastr_epa(
        st, [2024], fetch=lambda s: csv, received_at="2024-09-06T00:00:00Z",
    )
    assert res["team_games"] == 2 and res["rows"] > 0
    sums = st.team_stat_sums_before("KC", "2024-12-01T00:00:00Z", "nfl")
    assert sums and sums["sums"]["off_epa"] == 0.5
    st.close()


def test_team_stat_sums_exclude_late_and_unknown_feature_arrivals(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game({
        "game_id": "g", "league": "nfl", "season": 2025,
        "start_time": "2025-09-01T00:00:00Z", "home": "AAA", "away": "BBB",
        "home_score": 21, "away_score": 14, "status": "final",
    })
    # Legacy/unknown arrival evidence is quarantined, even though as_of looks old.
    st.record_team_boxscores([{
        "game_id": "g", "team": "AAA", "stats": {"off_plays": 60},
        "as_of": "2025-09-01T03:00:00Z",
    }])
    assert st.team_stat_sums_before("AAA", "2025-09-10T00:00:00Z", "nfl") is None
    assert st.game_ids_missing_boxscores("nfl") == ["g"]

    # A correction observed after the decision cannot travel back into it.
    st.record_team_boxscores([{
        "game_id": "g", "team": "AAA", "stats": {"off_plays": 61},
        "source_available_at": "2025-09-12T00:00:00Z",
        "received_at": "2025-09-12T00:01:00Z",
    }])
    assert st.team_stat_sums_before("AAA", "2025-09-10T00:00:00Z", "nfl") is None
    later = st.team_stat_sums_before("AAA", "2025-09-13T00:00:00Z", "nfl")
    assert later == {"sums": {"off_plays": 61.0}, "games": 1}
    st.close()
