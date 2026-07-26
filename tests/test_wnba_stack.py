"""Wave-12: WNBA v1 -- generic score-model stack, in-season evidence now.

WNBA rides the league-config-driven generic path end to end: one
LeagueScoreConfig entry, the three series maps, specialist registration,
reliability enrollment, and the taxonomy self-map. No bespoke engine yet
(that is a league-parity buildout item); everything prices off
TeamScoreModel exactly like a cold NBA market would.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_intelligence import TeamSportsIntelligenceSignal
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel

NOW = datetime(2026, 7, 17, 16, 0, tzinfo=timezone.utc)


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


class _AlwaysActive:
    def active(self, _league):
        return True


def _signal(tmp_path, game):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("wnba", "20260717")] = [game] if game else []
    models = {key: TeamScoreModel(key) for key in LEAGUE_SCORE_CONFIGS}
    return TeamSportsIntelligenceSignal(
        espn=client, models=models, model_dir=tmp_path, seasons=_AlwaysActive(),
    )


def _game(status="pre"):
    return Game("w1", "wnba", "LVA", "NYL", status, None, "2026-07-17T23:00Z",
                home_name="Las Vegas Aces", away_name="New York Liberty")


def test_wnba_config_registered_with_sane_scoring_environment():
    config = LEAGUE_SCORE_CONFIGS["wnba"]
    assert 75.0 < config.prior_team_score < 90.0
    assert 0.0 < config.home_edge_points < 5.0
    assert config.total_sigma > 0 and config.margin_sigma > 0


def test_wnba_score_model_learns_from_finals():
    model = TeamScoreModel("wnba")
    final = Game("w0", "wnba", "LVA", "NYL", "post", True, "2026-07-15T23:00Z",
                 home_score=95, away_score=80)
    assert model.update(final) is True
    assert model.update(final) is False       # idempotent by game id
    prediction = model.predict(_game())
    assert prediction.expected_home_score > prediction.expected_away_score
    assert 0.5 < prediction.home_win_probability < 1.0


def test_wnba_signal_prices_winner_total_spread_challenger_only(tmp_path):
    signal = _signal(tmp_path, _game())

    winner = signal.generate(_market(
        "KXWNBAGAME-26JUL17LVANYL-LVA", "Aces vs Liberty Winner?"))
    assert winner is not None
    assert winner.source == "wnba_structural_winner"
    assert winner.features["challenger_only"] is True
    # Cold model: home edge only, so the home side is a mild favorite.
    assert 0.5 < winner.probability_yes < 0.65

    total = signal.generate(_market(
        "KXWNBATOTAL-26JUL17LVANYL-T164", "Las Vegas Aces vs New York Liberty Total?",
        floor_strike=164.5))
    assert total is not None
    assert total.source == "wnba_game_total"
    assert 0.0 < total.probability_yes < 1.0

    spread = signal.generate(_market(
        "KXWNBASPREAD-26JUL17LVANYL-LVA5", "Las Vegas Aces vs New York Liberty Spread?",
        floor_strike=4.5))
    assert spread is not None
    assert spread.features["challenger_only"] is True
    assert 0.0 < spread.probability_yes < 0.5   # cold model: 4.5 is a big ask


def test_wnba_signal_fail_closed_without_matchup(tmp_path):
    no_game = _signal(tmp_path, None)
    assert no_game.generate(_market(
        "KXWNBAGAME-26JUL17LVANYL-LVA", "Aces vs Liberty Winner?")) is None


def test_wnba_started_game_abstains_without_live_model(tmp_path):
    # WNBA has no score/period/clock-conditioned live branch.  Reusing its
    # pregame model after tipoff would emit stale in-play evidence, so every
    # currently supported WNBA surface must fail closed.
    started = _signal(tmp_path, _game(status="in"))
    markets = (
        _market("KXWNBAGAME-26JUL17LVANYL-LVA", "Aces vs Liberty Winner?"),
        _market(
            "KXWNBATOTAL-26JUL17LVANYL-T164",
            "Las Vegas Aces vs New York Liberty Total?",
            floor_strike=164.5,
        ),
        _market(
            "KXWNBASPREAD-26JUL17LVANYL-LVA5",
            "Las Vegas Aces vs New York Liberty Spread?",
            floor_strike=4.5,
        ),
    )
    assert all(started.generate(market) is None for market in markets)


def test_wnba_enrolled_in_specialists_reliability_and_taxonomy():
    from autonomy.reliability import SPORTS_CALIBRATED_SOURCES
    from autonomy.specialists.factory import TEAM_LEAGUES
    from autonomy.taxonomy import specialist_for

    assert "wnba" in TEAM_LEAGUES
    assert "wnba_structural_winner" in SPORTS_CALIBRATED_SOURCES
    assert "wnba_game_total" in SPORTS_CALIBRATED_SOURCES
    assert specialist_for("wnba") == "wnba"
    assert specialist_for("wnba_structural_winner") == "wnba"
    assert specialist_for("wnba_game_total") == "wnba"
