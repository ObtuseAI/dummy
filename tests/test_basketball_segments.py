"""Wave-13: basketball first-half kernel + WNBA segment signal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.basketball_segments import BasketballSegmentSignal
from autonomy.sports.basketball_segments import (
    SHARE_1H,
    first_half_outcome_probabilities,
    first_half_spread_probability,
    first_half_total_probability,
)
from autonomy.sports.espn import EspnClient, Game
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScoreModel
from autonomy.sports_markets import spec_for

NOW = datetime(2026, 7, 17, 16, 0, tzinfo=timezone.utc)
SIGMA = LEAGUE_SCORE_CONFIGS["wnba"].margin_sigma


def _prediction(home=86.0, away=80.0):
    model = TeamScoreModel("wnba")
    game = Game("w1", "wnba", "PHX", "CONN", "pre", None, "2026-07-17T23:00Z")
    prediction = model.predict(game)
    # Rebuild with controlled expectations (dataclass is frozen).
    from dataclasses import replace

    return replace(
        prediction, expected_home_score=home, expected_away_score=away,
        expected_total=home + away)


# ------------------------------------------------------------------ kernel


def test_first_half_outcomes_form_a_distribution_with_a_real_tie_mass():
    p_home, p_tie, p_away = first_half_outcome_probabilities(_prediction(), SIGMA)
    assert p_home + p_tie + p_away == pytest.approx(1.0, abs=1e-9)
    assert p_home > p_away                    # 6-point favorite
    assert 0.01 < p_tie < 0.12                # a half ends level, sometimes


def test_first_half_tie_peaks_for_even_matchups():
    _, tie_even, _ = first_half_outcome_probabilities(_prediction(83.0, 83.0), SIGMA)
    _, tie_lopsided, _ = first_half_outcome_probabilities(_prediction(95.0, 70.0), SIGMA)
    assert tie_even > tie_lopsided


def test_first_half_total_monotone_in_line_and_centered_on_share():
    prediction = _prediction(86.0, 80.0)      # game total 166 -> 1H ~81.3
    mid = prediction.expected_total * SHARE_1H
    assert first_half_total_probability(prediction, mid - 0.5) > 0.5
    assert first_half_total_probability(prediction, mid + 0.5) < 0.5
    low = first_half_total_probability(prediction, 70.5)
    high = first_half_total_probability(prediction, 90.5)
    assert low > high


def test_first_half_spread_sides_are_complementary_at_the_same_line():
    prediction = _prediction(86.0, 80.0)
    # P(home margin > 2.5) and P(away margin > -2.5) = P(home margin < 2.5)
    # partition the continuous margin: the two sides of one line sum to 1.
    p_home_cover = first_half_spread_probability(prediction, True, 2.5, SIGMA)
    p_away_cover = first_half_spread_probability(prediction, False, -2.5, SIGMA)
    assert p_home_cover + p_away_cover == pytest.approx(1.0, abs=1e-9)
    # Favorite covers a small line more often than not.
    assert first_half_spread_probability(prediction, True, 0.5, SIGMA) > 0.5


# ------------------------------------------------------------------ signal


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(hours=6)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _signal(game):
    client = EspnClient(fetch_scoreboard=lambda _l, _d: {"events": []})
    client._cache[("wnba", "20260717")] = [game] if game else []
    return BasketballSegmentSignal(
        league="wnba", espn=client, model=TeamScoreModel("wnba"))


def _game(status="pre"):
    return Game("w1", "wnba", "PHX", "CONN", status, None, "2026-07-17T23:00Z",
                home_name="Phoenix Mercury", away_name="Connecticut Sun")


def test_wnba_1h_winner_three_legs_sum_to_one():
    signal = _signal(_game())
    legs = {}
    for suffix, title in (
        ("PHX", "Connecticut vs Phoenix: First Half Winner?"),
        ("CONN", "Connecticut vs Phoenix: First Half Winner?"),
        ("TIE", "Connecticut vs Phoenix: First Half Winner?"),
    ):
        market = _market(f"KXWNBA1HWINNER-26JUL17CONNPHX-{suffix}", title)
        assert signal.applicable(market) is True
        out = signal.generate(market)
        assert out is not None
        assert out.source == "wnba_1h_winner"
        assert out.features["challenger_only"] is True
        legs[suffix] = out.probability_yes
    assert sum(legs.values()) == pytest.approx(1.0, abs=0.02)   # clamped legs
    assert legs["TIE"] < min(legs["PHX"], legs["CONN"])
    # Cold model: home edge only -> home leg is the mild favorite.
    assert legs["PHX"] > legs["CONN"]


def test_wnba_1h_total_and_spread_price_off_the_half_share():
    signal = _signal(_game())
    total = signal.generate(_market(
        "KXWNBA1HTOTAL-26JUL17CONNPHX-84",
        "Connecticut vs Phoenix: First Half Total?", floor_strike=83.5))
    assert total is not None and total.source == "wnba_1h_total"
    # Cold model 1H expectation ~ 164.5*0.49 ~ 80.6 -> over 83.5 is < 0.5.
    assert total.probability_yes < 0.5

    spread = signal.generate(_market(
        "KXWNBA1HSPREAD-26JUL17CONNPHX-PHX3",
        "Will Phoenix win the 1H by over 2.5 points?", floor_strike=2.5))
    assert spread is not None and spread.source == "wnba_1h_spread"
    assert spread.features["subject_home"] is True
    assert spread.probability_yes < 0.5     # cold model: only a 2.5 home edge


def test_wnba_1h_fail_closed_on_started_or_missing_game():
    started = _signal(_game(status="in"))
    assert started.generate(_market(
        "KXWNBA1HTOTAL-26JUL17CONNPHX-84",
        "Connecticut vs Phoenix: First Half Total?", floor_strike=83.5)) is None

    missing = _signal(None)
    assert missing.generate(_market(
        "KXWNBA1HWINNER-26JUL17CONNPHX-PHX",
        "Connecticut vs Phoenix: First Half Winner?")) is None


def test_wnba_1h_series_discovered_and_three_way():
    assert spec_for("KXWNBA1HWINNER").discover is True
    assert spec_for("KXWNBA1HWINNER").three_way is True
    assert spec_for("KXWNBA1HSPREAD").discover is True
    assert spec_for("KXWNBA1HTOTAL").discover is True
    # Second-half + quarters stay staged.
    assert spec_for("KXWNBA2HWINNER").discover is False
    assert spec_for("KXWNBA1QTOTAL").discover is False


def test_segment_sources_have_a_taxonomy_home():
    from autonomy.taxonomy import specialist_for

    assert specialist_for("wnba_segments") == "wnba"
    assert specialist_for("wnba_1h_winner") == "wnba"
    assert specialist_for("wnba_1h_total") == "wnba"
    assert specialist_for("wnba_1h_spread") == "wnba"
