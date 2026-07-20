"""Four Factors challenger signal: prices from boxscores, fail-closed + self-scoping."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_four_factors import SportsFourFactorsSignal
from autonomy.sports.espn import Game
from autonomy.sports.history_store import SportsHistoryStore

_GOOD = {"fieldGoalsMade": 45, "fieldGoalsAttempted": 85, "threePointFieldGoalsMade": 12,
         "freeThrowsMade": 18, "freeThrowsAttempted": 22, "offensiveRebounds": 12, "turnovers": 10}
_POOR = {"fieldGoalsMade": 33, "fieldGoalsAttempted": 85, "threePointFieldGoalsMade": 7,
         "freeThrowsMade": 12, "freeThrowsAttempted": 18, "offensiveRebounds": 7, "turnovers": 17}


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
    for i in range(6):
        gid = f"g{i}"
        st.upsert_game({"game_id": gid, "league": "wnba", "season": 2025,
                        "start_time": f"2025-06-0{i + 1}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 88, "away_score": 74, "status": "final", "source": "t"})
        st.record_team_boxscores([{"game_id": gid, "team": "AAA", "stats": _GOOD},
                                  {"game_id": gid, "team": "BBB", "stats": _POOR}])
    return st


def test_prices_the_more_efficient_team(tmp_path):
    sig = SportsFourFactorsSignal(espn=FakeEspn(), store=_store(tmp_path), seasons=AllInSeason())
    m = _market("KXWNBAGAME-25SEP10AAABBB-AAA")
    assert sig.applicable(m)
    s = sig.generate(m)
    assert s is not None and s.source == "sports_four_factors" and s.probability_yes > 0.5


def test_abstains_without_boxscores(tmp_path):
    # empty store -> no boxscores -> abstain (self-scoping / fail-closed)
    st = SportsHistoryStore(tmp_path / "empty.db")
    sig = SportsFourFactorsSignal(espn=FakeEspn(), store=st, seasons=AllInSeason())
    assert sig.generate(_market("KXWNBAGAME-25SEP10AAABBB-AAA")) is None
