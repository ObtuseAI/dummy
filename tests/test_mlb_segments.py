"""Wave-10: MLB team-total + first-five (F5) segment markets."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.mlb_segments import MlbSegmentSignal, _teams_from_ticker
from autonomy.sports.baseball import (
    BaseballPrediction,
    BaseballRunModel,
    poisson_over_probability,
    poisson_three_way,
)
from autonomy.sports.espn import Game

_PRED = BaseballPrediction(
    home_win_probability=0.58, expected_home_runs=5.0, expected_away_runs=4.0,
    expected_total_runs=9.0, yrfi_probability=0.5, winner_uncertainty=0.10,
    total_uncertainty=0.12, first_inning_uncertainty=0.13, sample_games=50,
    pitchers_available=True, park_factor=1.0)


# ---- model math ---------------------------------------------------------------

def test_team_total_is_poisson_on_team_mean():
    m = BaseballRunModel()
    # Home team mean 5.0 -> P(>3.5) == P(Poisson(5) >= 4).
    assert abs(m.team_total_probability(_PRED, True, 3.5)
               - poisson_over_probability(5.0, 3.5)) < 1e-9
    # Away mean 4.0 is lower, so its over-3.5 prob is lower than home's.
    assert m.team_total_probability(_PRED, False, 3.5) < m.team_total_probability(_PRED, True, 3.5)


def test_f5_three_way_sums_to_one_and_orders_correctly():
    m = BaseballRunModel()
    p_home, p_tie, p_away = m.f5_outcome_probabilities(_PRED)
    assert abs(p_home + p_tie + p_away - 1.0) < 1e-9
    assert p_home > p_away          # home is the stronger side
    assert 0.10 < p_tie < 0.30      # F5 ties are common but not dominant


def test_f5_total_uses_five_ninths_share():
    m = BaseballRunModel()
    # F5 total mean = 9.0 * 5/9 = 5.0.
    assert abs(m.f5_total_probability(_PRED, 4.5) - poisson_over_probability(5.0, 4.5)) < 1e-9


def test_poisson_three_way_symmetry():
    a, tie, b = poisson_three_way(3.0, 3.0)
    assert abs(a - b) < 1e-9 and abs(a + tie + b - 1.0) < 1e-9


# ---- ticker team recovery -----------------------------------------------------

def test_teams_from_ticker_handles_time_and_doubleheader():
    assert _teams_from_ticker("KXMLBF5-26JUL171905LADNYY-LAD") == ("LAD", "NYY")


# ---- the signal ---------------------------------------------------------------

class _FixedModel(BaseballRunModel):
    def predict(self, game):
        return _PRED


class _Espn:
    def __init__(self, game):
        self._game = game

    def clear_cache(self):
        pass

    def find_matchup(self, league, a, b, dates=None):
        return self._game


def _pre_game():
    return Game(game_id="g1", league="mlb", home="NYY", away="LAD",
                status="pre", home_won=None, date="2026-07-17")


def _mkt(ticker, title, floor=None):
    raw = {"floor_strike": floor} if floor is not None else {}
    return MarketView(ticker=ticker, title=title, vertical=Vertical.SPORTS,
                      status="open", close_time="2026-07-17T23:00:00+00:00",
                      yes_bid=45, yes_ask=47, no_bid=53, no_ask=55, volume=9,
                      liquidity=9, raw=raw)


def _signal(game=None):
    return MlbSegmentSignal(espn=_Espn(game or _pre_game()), model=_FixedModel())


def test_signal_prices_team_total():
    sig = _signal()
    out = sig.generate(_mkt("KXMLBTEAMTOTAL-26JUL171905LADNYY-NYY8",
                            "Will New York Y score over 4.5 runs?", floor=4.5))
    assert out is not None and out.source == "mlb_team_total"
    assert out.features["challenger_only"] is True
    # NYY is home (mean 5.0): P(>4.5) around 0.56.
    assert 0.50 < out.probability_yes < 0.62


def test_signal_prices_f5_winner_three_legs_coherently():
    sig = _signal()
    home = sig.generate(_mkt("KXMLBF5-26JUL171905LADNYY-NYY", "LAD vs NYY first 5 innings winner?"))
    away = sig.generate(_mkt("KXMLBF5-26JUL171905LADNYY-LAD", "LAD vs NYY first 5 innings winner?"))
    tie = sig.generate(_mkt("KXMLBF5-26JUL171905LADNYY-TIE", "LAD vs NYY first 5 innings tie?"))
    assert {home.source, away.source, tie.source} == {"mlb_f5_winner"}
    total = home.probability_yes + away.probability_yes + tie.probability_yes
    assert abs(total - 1.0) < 0.02        # three legs partition the outcome
    assert home.probability_yes > away.probability_yes


def test_signal_prices_f5_total_and_spread():
    sig = _signal()
    tot = sig.generate(_mkt("KXMLBF5TOTAL-26JUL171905LADNYY-5",
                            "LAD vs NYY first 5 innings runs?", floor=4.5))
    assert tot.source == "mlb_f5_total"
    sp = sig.generate(_mkt("KXMLBF5SPREAD-26JUL171905LADNYY-NYY2",
                           "New York Y wins first 5 innings by over 1.5 runs?", floor=1.5))
    assert sp.source == "mlb_f5_spread"


def test_signal_fails_closed_once_underway():
    live = Game(game_id="g1", league="mlb", home="NYY", away="LAD",
                status="in", home_won=None, date="2026-07-17")
    out = _signal(live).generate(_mkt("KXMLBF5-26JUL171905LADNYY-NYY",
                                      "LAD vs NYY first 5 innings winner?"))
    assert out is None


def test_signal_ignores_full_game_moneyline():
    # The full-game winner belongs to BaseballIntelligenceSignal, not this one.
    out = _signal().generate(_mkt("KXMLBGAME-26JUL171905LADNYY-NYY",
                                  "LAD vs NYY Winner?"))
    assert out is None
