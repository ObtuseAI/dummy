"""EPA challenger signal: prices from lake EPA, fail-closed + self-scoping."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.sports_epa import SportsEpaSignal
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


def _box(gid, team, off_per, def_per):
    return {"game_id": gid, "team": team,
            "stats": {"off_epa": off_per * 65, "off_plays": 65, "def_epa": def_per * 63, "def_plays": 63}}


def _store(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    for i in range(6):
        gid = f"g{i}"
        st.upsert_game({"game_id": gid, "league": "nfl", "season": 2025,
                        "start_time": f"2025-09-{i + 1:02d}T00:00:00Z", "home": "AAA", "away": "BBB",
                        "home_score": 31, "away_score": 17, "status": "final", "source": "t"})
        st.record_team_boxscores([_box(gid, "AAA", 0.15, -0.05), _box(gid, "BBB", 0.00, 0.10)])
    return st


def test_prices_more_efficient_team(tmp_path):
    sig = SportsEpaSignal(espn=FakeEspn(), store=_store(tmp_path), seasons=AllInSeason())
    m = _market("KXNFLGAME-25SEP10AAABBB-AAA")
    assert sig.applicable(m)
    s = sig.generate(m)
    assert s is not None and s.source == "sports_epa" and s.probability_yes > 0.5


def test_abstains_without_epa(tmp_path):
    st = SportsHistoryStore(tmp_path / "empty.db")
    sig = SportsEpaSignal(espn=FakeEspn(), store=st, seasons=AllInSeason())
    assert sig.generate(_market("KXNFLGAME-25SEP10AAABBB-AAA")) is None
