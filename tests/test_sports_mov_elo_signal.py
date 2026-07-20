"""MOV-Elo challenger signal: prices from the lake, fail-closed."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_mov_elo import SportsMovEloSignal
from autonomy.sports.espn import Game
from autonomy.sports.history_store import SportsHistoryStore


class FakeEspn:
    def __init__(self, status="pre"):
        self._status = status

    def find_matchup(self, league, subject, opponent, dates=None):
        return Game(game_id="m", league=league, home="AAA", away="BBB",
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
    for i in range(5):
        st.upsert_game({"game_id": f"g{i}", "league": "nfl", "season": 2025,
                        "start_time": f"2025-09-0{i + 1}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 35, "away_score": 10, "status": "final", "source": "t"})
    return st


def test_prices_the_stronger_team(tmp_path):
    sig = SportsMovEloSignal(espn=FakeEspn(), store=_store(tmp_path), seasons=AllInSeason())
    m = _market("KXNFLGAME-25SEP10AAABBB-AAA")
    assert sig.applicable(m)
    s = sig.generate(m)
    assert s is not None and s.source == "sports_mov_elo"
    assert s.probability_yes > 0.5
    assert s.features["subject_rating"] > s.features["opponent_rating"]


def test_abstains_mid_game(tmp_path):
    sig = SportsMovEloSignal(espn=FakeEspn(status="in"), store=_store(tmp_path), seasons=AllInSeason())
    assert sig.generate(_market("KXNFLGAME-25SEP10AAABBB-AAA")) is None
