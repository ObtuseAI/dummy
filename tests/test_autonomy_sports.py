"""Tests for the sports Elo signal, model, and ESPN adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_elo import SportsEloSignal, parse_game_ticker
from autonomy.sports.elo import BASE_RATING, EloModel, win_probability
from autonomy.sports.espn import EspnClient, Game, parse_scoreboard


# ---------------------------------------------------------------- Elo model


def test_win_probability_symmetry():
    assert abs(win_probability(1500, 1500) - 0.5) < 1e-9
    assert win_probability(1700, 1500) > 0.5
    assert abs(win_probability(1700, 1500) + win_probability(1500, 1700) - 1.0) < 1e-9


def test_elo_update_moves_ratings_toward_winner():
    model = EloModel(league="nba")
    model.update("LAL", "BOS", home_won=True, game_id="g1")
    assert model.rating("LAL") > BASE_RATING
    assert model.rating("BOS") < BASE_RATING
    assert model.games_seen == 1


def test_elo_update_idempotent_per_game():
    model = EloModel(league="mlb")
    model.update("NYY", "BOS", home_won=True, game_id="g1")
    r1 = model.rating("NYY")
    model.update("NYY", "BOS", home_won=True, game_id="g1")  # replay same game
    assert model.rating("NYY") == r1
    assert model.games_seen == 1


def test_elo_home_edge_favors_home():
    model = EloModel(league="nba")  # 100-pt home edge
    assert model.predict("A", "B") > 0.5  # equal ratings, home wins bump
    assert model.predict_team("A", "B", subject_home=True) > 0.5
    assert model.predict_team("A", "B", subject_home=False) < 0.5
    assert abs(model.predict_team("A", "B", subject_home=None) - 0.5) < 1e-9


def test_elo_persistence_roundtrip(tmp_path):
    model = EloModel(league="nhl")
    model.update("EDM", "CGY", home_won=True, game_id="g1")
    path = tmp_path / "elo_nhl.json"
    model.save(path)
    loaded = EloModel.load("nhl", path)
    assert loaded.rating("EDM") == model.rating("EDM")
    assert loaded.games_seen == 1
    assert "g1" in loaded.processed_game_ids


# ---------------------------------------------------------------- ticker parse


def test_parse_mlb_game_ticker():
    parsed = parse_game_ticker("KXMLBGAME-26JUL111810PHIDET-PHI")
    assert parsed["league"] == "mlb"
    assert parsed["date_yyyymmdd"] == "20260711"
    assert parsed["subject"] == "PHI"
    assert parsed["opponent"] == "DET"


def test_parse_nfl_game_ticker_suffix_subject():
    parsed = parse_game_ticker("KXNFLGAME-26AUG15DALSEA-SEA")
    assert parsed["subject"] == "SEA"
    assert parsed["opponent"] == "DAL"
    assert parsed["date_yyyymmdd"] == "20260815"


def test_parse_rejects_non_game_and_unknown_league():
    assert parse_game_ticker("KXNBA-27-WAS") is None
    assert parse_game_ticker("KXHIGHNY-26JUL10-T85") is None
    assert parse_game_ticker("KXCRICKETGAME-26JUL10ABCXYZ-ABC") is None


# ---------------------------------------------------------------- ESPN parse


def _scoreboard(events):
    return {"events": events}


def _event(gid, home, away, state, home_winner=None, away_winner=None, date="2026-07-11T22:10Z"):
    return {
        "id": gid, "date": date,
        "competitions": [{
            "status": {"type": {"state": state}},
            "competitors": [
                {"homeAway": "home", "team": {"abbreviation": home}, "winner": home_winner},
                {"homeAway": "away", "team": {"abbreviation": away}, "winner": away_winner},
            ],
        }],
    }


def test_parse_scoreboard_resolves_winner():
    games = parse_scoreboard("mlb", _scoreboard([
        _event("1", "DET", "PHI", "post", home_winner=True, away_winner=False),
        _event("2", "NYY", "BOS", "pre"),
    ]))
    assert len(games) == 2
    post = [g for g in games if g.game_id == "1"][0]
    assert post.home == "DET" and post.away == "PHI" and post.home_won is True
    pre = [g for g in games if g.game_id == "2"][0]
    assert pre.status == "pre" and pre.home_won is None


def test_parse_scoreboard_preserves_completed_tie_instead_of_home_win():
    event = _event("tie", "NYG", "WAS", "post", home_winner=False, away_winner=False)
    competitors = event["competitions"][0]["competitors"]
    competitors[0]["score"] = "20"
    competitors[1]["score"] = "20"

    game = parse_scoreboard("nfl", _scoreboard([event]))[0]

    assert game.status == "post"
    assert game.home_score == game.away_score == 20
    assert game.home_won is None
    assert game.is_tie is True


def test_find_matchup_ignores_order():
    client = EspnClient(fetch_scoreboard=lambda l, d: _scoreboard([_event("1", "DET", "PHI", "pre")]))
    game = client.find_matchup("mlb", "PHI", "DET")
    assert game is not None and game.home == "DET"


# ---------------------------------------------------------------- signal


def _market(ticker="KXMLBGAME-26JUL111810PHIDET-PHI"):
    return MarketView(
        ticker=ticker, title="Philadelphia vs Detroit Winner?", vertical=Vertical.SPORTS,
        status="active", close_time=(datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        yes_bid=45, yes_ask=55, no_bid=45, no_ask=55, volume=200, liquidity=500,
    )


def test_sports_signal_uses_home_edge(tmp_path):
    # DET is home; equal ratings -> DET (opponent) favored, so PHI (subject, away) < 0.5.
    client = EspnClient(fetch_scoreboard=lambda l, d: _scoreboard([_event("1", "DET", "PHI", "pre")]))
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)
    result = signal.generate(_market())
    assert result is not None
    assert result.probability_yes < 0.5
    assert result.source == "sports_elo"


def test_sports_signal_skips_started_game(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda l, d: _scoreboard([_event("1", "DET", "PHI", "in")]))
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)
    assert signal.generate(_market()) is None


def test_sports_signal_neutral_when_game_not_found(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda l, d: _scoreboard([]))
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)
    result = signal.generate(_market())
    assert result is not None
    assert abs(result.probability_yes - 0.5) < 1e-6  # neutral, untrained
    assert result.uncertainty > 0.2  # penalized for unknown venue + coldness


def test_sports_signal_reflects_trained_ratings(tmp_path):
    client = EspnClient(fetch_scoreboard=lambda l, d: _scoreboard([_event("1", "DET", "PHI", "pre")]))
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)
    model = signal._model("mlb")
    for _ in range(30):
        model.update("PHI", "DET", home_won=True, game_id=None)  # PHI dominant
    result = signal.generate(_market())
    # PHI is away here but much stronger; strength should overcome DET's home edge.
    assert result.probability_yes > 0.5


def test_warmup_replays_completed_games(tmp_path):
    events = [
        _event("1", "DET", "PHI", "post", home_winner=True, date="2026-07-01T00:00Z"),
        _event("2", "PHI", "DET", "post", home_winner=True, date="2026-07-02T00:00Z"),
        _event("3", "NYY", "BOS", "pre", date="2026-07-11T00:00Z"),
    ]
    client = EspnClient(fetch_scoreboard=lambda l, d: _scoreboard(events))
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)
    model = signal.warmup("mlb", ["20260701-20260710"])
    assert model.games_seen == 2  # only the two 'post' games
    assert (tmp_path / "elo_mlb.json").exists()
