"""Pythagenpat challenger signal: prices from the lake, fail-closed."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_pythagorean import SportsPythagoreanSignal
from autonomy.sports.espn import Game
from autonomy.sports.history_store import SportsHistoryStore


class FakeEspn:
    def __init__(self, home="AAA", away="BBB", status="pre"):
        self._home, self._away, self._status = home, away, status

    def find_matchup(self, league, subject, opponent, dates=None):
        return Game(game_id="m", league=league, home=self._home, away=self._away,
                    status=self._status, home_won=None, date="2025-09-10T00:00Z")

    def clear_cache(self):
        pass


class AllInSeason:
    def active(self, league):
        return True


def _market(ticker):
    return MarketView(ticker=ticker, title="t", vertical=Vertical.SPORTS, status="active",
                      close_time="2025-09-11T00:00:00Z", yes_bid=40, yes_ask=44,
                      no_bid=56, no_ask=60, volume=100, liquidity=1000)


def _store(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    # AAA blows BBB out repeatedly -> high Pythagorean strength.
    for i in range(5):
        st.upsert_game({"game_id": f"g{i}", "league": "nfl", "season": 2025,
                        "start_time": f"2025-09-0{i + 1}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 38, "away_score": 10, "status": "final", "source": "t"})
    return st


def test_prices_the_dominant_team(tmp_path):
    sig = SportsPythagoreanSignal(espn=FakeEspn(home="AAA", away="BBB"), store=_store(tmp_path), seasons=AllInSeason())
    m = _market("KXNFLGAME-25SEP10AAABBB-AAA")
    assert sig.applicable(m)
    s = sig.generate(m)
    assert s is not None and s.source == "sports_pythagorean"
    assert s.probability_yes > 0.6
    assert s.features["subject_strength"] > s.features["opponent_strength"]
    assert s.features["challenger_only"] is True
    assert s.features["promotion_eligible"] is True
    assert s.features["point_in_time"] is True
    assert s.features["public_read_only"] is True
    assert s.features["sport"] == "nfl"
    assert s.features["market_type"] == "winner"


def test_abstains_mid_game(tmp_path):
    sig = SportsPythagoreanSignal(espn=FakeEspn(status="in"), store=_store(tmp_path), seasons=AllInSeason())
    assert sig.generate(_market("KXNFLGAME-25SEP10AAABBB-AAA")) is None
