"""Tests for pitcher-aware MLB Elo adjustment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_elo import SportsEloSignal
from autonomy.sports.elo import (
    LEAGUE_AVG_ERA,
    PITCHER_ELO_CLAMP,
    EloModel,
    pitcher_elo_adjustment,
)
from autonomy.sports.espn import EspnClient, parse_scoreboard


# ---------------------------------------------------------------- adjustment


def test_pitcher_adjustment_direction_and_clamp():
    assert pitcher_elo_adjustment(LEAGUE_AVG_ERA) == 0.0
    assert pitcher_elo_adjustment(2.5) > 0  # ace, below-average ERA
    assert pitcher_elo_adjustment(6.0) < 0  # struggling starter
    assert pitcher_elo_adjustment(0.01) <= PITCHER_ELO_CLAMP  # clamped
    assert pitcher_elo_adjustment(None) == 0.0
    assert pitcher_elo_adjustment(0) == 0.0


def test_predict_team_pitcher_swings_probability():
    model = EloModel(league="mlb")  # equal ratings, small home edge (24)
    # Subject away, but has an ace vs a weak opposing starter.
    p_ace = model.predict_team("PHI", "DET", subject_home=False,
                               subject_pitcher_era=2.0, opponent_pitcher_era=5.5)
    p_even = model.predict_team("PHI", "DET", subject_home=False)
    assert p_ace > p_even
    assert p_ace > 0.5  # strong pitcher edge overcomes the road home penalty


def test_predict_team_backward_compatible_without_pitchers():
    model = EloModel(league="mlb")
    # No pitcher args -> identical to the plain home/away prediction.
    assert abs(model.predict_team("A", "B", None) - 0.5) < 1e-9
    assert model.predict_team("A", "B", True) > 0.5


# ---------------------------------------------------------------- ESPN parse


def _event_with_probables(home, away, home_era, away_era, state="pre"):
    def comp(abbr, ha, era, name):
        c = {"homeAway": ha, "team": {"abbreviation": abbr}, "winner": None}
        if era is not None:
            c["probables"] = [{
                "displayName": name,
                "athlete": {"displayName": name},
                "statistics": [{"name": "wins", "displayValue": "5"},
                               {"name": "ERA", "displayValue": str(era)}],
            }]
        return c

    return {
        "id": "1", "date": "2026-07-09T22:10Z",
        "competitions": [{
            "status": {"type": {"state": state}},
            "competitors": [comp(home, "home", home_era, "HomeSP"),
                            comp(away, "away", away_era, "AwaySP")],
        }],
    }


def test_parse_scoreboard_extracts_pitcher_era():
    games = parse_scoreboard("mlb", {"events": [_event_with_probables("SF", "TOR", 3.86, 2.56)]})
    g = games[0]
    assert g.home_pitcher_era == 3.86
    assert g.away_pitcher_era == 2.56
    assert g.away_pitcher == "AwaySP"


def test_parse_scoreboard_handles_missing_probables():
    games = parse_scoreboard("mlb", {"events": [_event_with_probables("SF", "TOR", None, None)]})
    g = games[0]
    assert g.home_pitcher_era is None
    assert g.away_pitcher_era is None


# ---------------------------------------------------------------- signal


def _market(ticker="KXMLBGAME-26JUL091810TORSF-TOR"):
    return MarketView(
        ticker=ticker, title="TOR vs SF", vertical=Vertical.SPORTS, status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        yes_bid=45, yes_ask=55, no_bid=45, no_ask=55, volume=200, liquidity=500,
    )


def test_signal_incorporates_pitcher_edge(tmp_path):
    # SF home (Webb 3.86), TOR away (Cease 2.56 ace). TOR is the subject.
    scoreboard = {"events": [_event_with_probables("SF", "TOR", 3.86, 2.56)]}
    client = EspnClient(fetch_scoreboard=lambda l, d: scoreboard)
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)

    with_pitcher = signal.generate(_market())
    assert with_pitcher is not None
    assert with_pitcher.features["subject_pitcher_era"] == 2.56
    assert with_pitcher.features["opponent_pitcher_era"] == 3.86
    assert "SP" in with_pitcher.rationale

    # Compare to the same matchup with no probables: the ace should lift TOR.
    no_prob = {"events": [_event_with_probables("SF", "TOR", None, None)]}
    client2 = EspnClient(fetch_scoreboard=lambda l, d: no_prob)
    signal2 = SportsEloSignal(espn=client2, elo_dir=tmp_path)
    without_pitcher = signal2.generate(_market())
    assert with_pitcher.probability_yes > without_pitcher.probability_yes
    # Pitcher info tightens uncertainty.
    assert with_pitcher.uncertainty < without_pitcher.uncertainty


def test_signal_pitcher_only_affects_baseball(tmp_path):
    # A non-baseball ticker never carries probables -> unaffected path.
    scoreboard = {"events": [_event_with_probables("BOS", "NYK", None, None)]}
    client = EspnClient(fetch_scoreboard=lambda l, d: scoreboard)
    signal = SportsEloSignal(espn=client, elo_dir=tmp_path)
    nba = signal.generate(MarketView(
        ticker="KXNBAGAME-26JUL09BOSNYK-BOS", title="", vertical=Vertical.SPORTS, status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        yes_bid=45, yes_ask=55, no_bid=45, no_ask=55, volume=100, liquidity=100))
    assert nba is not None
    assert nba.features["subject_pitcher_era"] is None
