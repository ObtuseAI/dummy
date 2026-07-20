"""Scoring-model spread/total challenger signal: prices lines, fail-closed."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_scoring import SportsScoringSignal
from autonomy.sports.espn import Game
from autonomy.sports.history_store import SportsHistoryStore


class FakeEspn:
    def __init__(self, home="AAA", away="BBB", status="pre"):
        self._home, self._away, self._status = home, away, status

    def find_matchup(self, league, a, b, dates=None):
        return Game(game_id="m", league=league, home=self._home, away=self._away,
                    status=self._status, home_won=None, date="2025-01-15T00:00Z")

    def clear_cache(self):
        pass


class AllInSeason:
    def active(self, league):
        return True


def _market(ticker, title, floor_strike):
    return MarketView(ticker=ticker, title=title, vertical=Vertical.SPORTS, status="active",
                      close_time="2025-01-16T00:00:00Z", yes_bid=45, yes_ask=49,
                      no_bid=51, no_ask=55, volume=100, liquidity=1000,
                      raw={"floor_strike": floor_strike})


def _store(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    day = 1
    for wk in range(12):
        st.upsert_game({"game_id": f"a{wk}", "league": "nba", "season": 2025,
                        "start_time": f"2025-01-{day:02d}T00:00:00Z", "home": "AAA", "away": "CCC",
                        "home_score": 118, "away_score": 96, "status": "final", "source": "t"})
        day += 1
        st.upsert_game({"game_id": f"c{wk}", "league": "nba", "season": 2025,
                        "start_time": f"2025-01-{day:02d}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 110, "away_score": 100, "status": "final", "source": "t"})
        day += 1
    return st


def test_prices_spread_and_total(tmp_path):
    st = _store(tmp_path)
    sig = SportsScoringSignal(espn=FakeEspn("AAA", "BBB"), store=st, seasons=AllInSeason())
    # spread: AAA (home, strong) to cover -3.5 -> likely
    m_spread = _market("KXNBASPREAD-25JAN15AAABBB-AAA3", "AAA vs BBB Spread", 3.5)
    assert sig.applicable(m_spread)
    s = sig.generate(m_spread)
    assert s is not None and s.source == "sports_scoring"
    assert s.probability_yes > 0.4 and s.features["market_type"] == "spread"
    assert s.features["expected_margin"] is not None
    # total: over a low line -> likely over
    m_total = _market("KXNBATOTAL-25JAN15AAABBB-180", "AAA vs BBB Total Points", 180.0)
    st2 = sig.generate(m_total)
    assert st2 is not None and st2.features["market_type"] == "total"
    assert st2.probability_yes > 0.5     # expected total (~215) well over 180
    st.close()


def test_abstains_on_winner_market(tmp_path):
    sig = SportsScoringSignal(espn=FakeEspn(), store=_store(tmp_path), seasons=AllInSeason())
    m = _market("KXNBAGAME-25JAN15AAABBB-AAA", "AAA vs BBB Winner?", None)
    assert sig.applicable(m) is False and sig.generate(m) is None
