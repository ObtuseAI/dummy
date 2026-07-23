"""PBP knowledge lake: folding, aggregation, artifact, and fail-closed reads."""
from __future__ import annotations

import gzip
import io
import json

from autonomy.ingest.pbp_lake import (
    aggregate_league_season,
    fold_pbp_rows,
    ingest_pbp_seasons,
    lead_bucket,
    merge_seasons,
    stream_pbp_rows,
    write_pbp_artifact,
)
from autonomy.sports.pbp_params import in_game_home_win_prior, load_pbp_params


def _row(game, seq, period, home, away, shooting=False):
    return {
        "game_id": game, "sequence_number": seq, "period_number": period,
        "home_score": home, "away_score": away,
        "scoring_play": False, "shooting_play": shooting,
    }


def _synthetic_game(game_id, quarter_scores, flip_final=False):
    """Rows for one game from cumulative (home, away) quarter ends."""
    rows = []
    seq = 0
    for period, (home, away) in enumerate(quarter_scores, start=1):
        seq += 10
        rows.append(_row(game_id, seq, period, home, away, shooting=True))
    if flip_final:
        rows.append(_row(game_id, seq + 1, len(quarter_scores),
                         quarter_scores[-1][1], quarter_scores[-1][0]))
    return rows


def test_fold_takes_latest_sequence_per_period_and_game():
    rows = [
        _row("g1", 5, 1, 10, 8),
        _row("g1", 3, 1, 6, 4),          # earlier row must not win
        _row("g1", 20, 2, 30, 25),
        _row("g1", 40, 4, 80, 70),
    ]
    games = fold_pbp_rows(rows)
    fold = games["g1"]
    assert (fold.home, fold.away) == (80, 70)
    assert fold.period_end[1][1:] == (10, 8)
    assert fold.period_end[2][1:] == (30, 25)


def test_aggregate_builds_margin_total_periods_and_comeback():
    rows = []
    # 30 identical games: home leads 25-20 after Q1 and wins 100-90.
    for i in range(30):
        rows += _synthetic_game(
            f"g{i}", [(25, 20), (50, 45), (75, 70), (100, 90)],
        )
    block = aggregate_league_season(fold_pbp_rows(rows), regulation_periods=4)
    assert block["games"] == 30
    assert block["margin"]["mean"] == 10.0
    assert block["margin"]["sigma"] == 0.0
    assert block["total"]["mean"] == 190.0
    assert block["ot_rate"] == 0.0
    assert block["period_profile"]["1"] == {"home_mean": 25.0, "away_mean": 20.0}
    cell = block["comeback"]["after_period_1"][lead_bucket(5)]
    assert cell == {"n": 30, "home_win_rate": 1.0}


def test_lead_buckets_are_stable_and_total():
    assert lead_bucket(-40) == "<-15"
    assert lead_bucket(-3) == "[-3,-1)"
    assert lead_bucket(0) == "[-1,1)"
    assert lead_bucket(4) == "[3,6)"
    assert lead_bucket(40) == ">=15"


def test_merge_seasons_pools_with_total_variance():
    a = aggregate_league_season(
        fold_pbp_rows(sum((_synthetic_game(f"a{i}", [(25, 20), (50, 40), (75, 60), (100, 80)])
                           for i in range(20)), [])),
        regulation_periods=4,
    )
    b = aggregate_league_season(
        fold_pbp_rows(sum((_synthetic_game(f"b{i}", [(20, 25), (40, 50), (60, 75), (80, 100)])
                           for i in range(20)), [])),
        regulation_periods=4,
    )
    merged = merge_seasons({2021: a, 2022: b})
    assert merged["games"] == 40
    assert merged["margin"]["mean"] == 0.0
    assert merged["margin"]["sigma"] == 20.0  # two point masses at ±20


def test_stream_parses_gzip_espn_schema(tmp_path):
    header = (
        "game_id,sequence_number,period_number,home_score,away_score,"
        "scoring_play,shooting_play,text"
    )
    body = "\n".join([
        header,
        "401,4,1,2,0,TRUE,TRUE,bucket",
        "401,9,1,2,3,TRUE,TRUE,three",
    ])
    payload = gzip.compress(body.encode("utf-8"))

    def opener(_url):
        return io.BytesIO(payload)

    rows = list(stream_pbp_rows("wnba", 2022, opener=opener, sleep=lambda _s: None))
    assert rows[0]["game_id"] == "401"
    assert rows[1]["home_score"] == 2 and rows[1]["away_score"] == 3
    assert rows[0]["shooting_play"] is True


def test_ingest_writes_artifact_and_reader_round_trips(tmp_path):
    header = (
        "game_id,sequence_number,period_number,home_score,away_score,"
        "scoring_play,shooting_play"
    )
    lines = [header]
    for game in range(35):
        for period, (home, away) in enumerate(
            [(25, 20), (50, 45), (75, 70), (100, 90)], start=1,
        ):
            lines.append(f"g{game},{period * 10},{period},{home},{away},TRUE,TRUE")
    payload = gzip.compress("\n".join(lines).encode("utf-8"))
    artifact = tmp_path / "sports_pbp_params.json"

    report = ingest_pbp_seasons(
        "wnba", [2022],
        opener=lambda _url: io.BytesIO(payload),
        sleep=lambda _s: None,
        artifact_path=artifact,
    )
    assert report["ok"] is True and report["games"] == 35

    document = json.loads(artifact.read_text(encoding="utf-8"))
    assert document["authority"] == {
        "execution": False, "promotion": False, "fusion": False,
    }

    block = load_pbp_params("wnba", path=artifact)
    assert block["games"] == 35
    prior = in_game_home_win_prior(
        "wnba", period_completed=1, home_lead=5, path=artifact,
    )
    assert prior["home_win_rate"] == 1.0 and prior["n"] == 35
    assert prior["authority"] == "research_prior_only"


def test_reader_fails_closed(tmp_path):
    missing = tmp_path / "absent.json"
    assert load_pbp_params("wnba", path=missing) is None
    assert in_game_home_win_prior(
        "wnba", period_completed=1, home_lead=3, path=missing,
    ) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{\"artifact_version\": \"other\"}", encoding="utf-8")
    assert load_pbp_params("wnba", path=bad) is None


def test_artifact_merge_preserves_other_leagues(tmp_path):
    artifact = tmp_path / "sports_pbp_params.json"
    write_pbp_artifact({"nba": {"games": 5, "seasons": [2023]}}, path=artifact)
    write_pbp_artifact({"wnba": {"games": 7, "seasons": [2022]}}, path=artifact)
    document = json.loads(artifact.read_text(encoding="utf-8"))
    assert set(document["leagues"]) == {"nba", "wnba"}
