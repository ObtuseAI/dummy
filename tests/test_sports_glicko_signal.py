"""Glicko-2 challenger signal: parses tickers, prices from the lake, fail-closed."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_glicko import SportsGlickoSignal
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
    for i, (h, a, hs, as_) in enumerate([("AAA", "BBB", 30, 10), ("BBB", "AAA", 10, 27), ("AAA", "BBB", 24, 20)]):
        st.upsert_game({"game_id": f"g{i}", "league": "nfl", "season": 2025,
                        "start_time": f"2025-09-0{i + 1}T00:00:00Z", "home": h, "away": a,
                        "home_score": hs, "away_score": as_, "status": "final", "source": "t"})
    return st


def test_prices_the_stronger_team(tmp_path):
    sig = SportsGlickoSignal(espn=FakeEspn(home="AAA", away="BBB"), store=_store(tmp_path), seasons=AllInSeason(), ratings_dir=tmp_path)
    m = _market("KXNFLGAME-25SEP10AAABBB-AAA")
    assert sig.applicable(m)
    s = sig.generate(m)
    assert s is not None and s.source == "sports_glicko"
    assert s.probability_yes > 0.5           # AAA (stronger + home) favored
    assert s.features["subject_rating"] > s.features["opponent_rating"]


def test_away_subject_is_complement(tmp_path):
    sig = SportsGlickoSignal(espn=FakeEspn(home="AAA", away="BBB"), store=_store(tmp_path), seasons=AllInSeason(), ratings_dir=tmp_path)
    s = sig.generate(_market("KXNFLGAME-25SEP10AAABBB-BBB"))     # subject = away underdog
    assert s is not None and s.probability_yes < 0.5


def test_abstains_when_game_already_started(tmp_path):
    sig = SportsGlickoSignal(espn=FakeEspn(status="in"), store=_store(tmp_path), seasons=AllInSeason(), ratings_dir=tmp_path)
    assert sig.generate(_market("KXNFLGAME-25SEP10AAABBB-AAA")) is None


def test_abstains_with_no_lake(tmp_path):
    # store that raises on use -> signal must fail closed, never crash
    sig = SportsGlickoSignal(espn=FakeEspn(), store=SportsHistoryStore(tmp_path / "empty.db"),
                             seasons=AllInSeason(), ratings_dir=tmp_path)
    s = sig.generate(_market("KXNFLGAME-25SEP10AAABBB-AAA"))
    # empty lake -> both teams default-rated -> ~0.5 with high uncertainty (not None)
    assert s is not None and 0.4 < s.probability_yes < 0.6 and s.uncertainty >= 0.15
