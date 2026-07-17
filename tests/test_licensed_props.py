"""Wave-10: licensed player-prop signal (MLB, per-event de-vig)."""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.licensed_props import STAT_TO_MARKET_KEY, LicensedPlayerPropSignal
from autonomy.signals.mlb_segments import _teams_from_ticker
from autonomy.sports.espn import Game


class _Espn:
    def __init__(self, game):
        self._game = game

    def clear_cache(self):
        pass

    def find_matchup(self, league, a, b, dates=None):
        return self._game


class _Client:
    """Stub OddsApiClient: armed, serves a fixed events list + per-event props."""

    def __init__(self, events, event_odds, available=True):
        self._events = events
        self._event_odds = event_odds
        self.available = available
        self.event_calls = []

    def list_events(self, sport_key):
        return self._events, "cache"

    def event_player_props(self, sport_key, event_id, markets):
        self.event_calls.append((event_id, markets))
        return self._event_odds, "live"


def _pre_game():
    return Game(game_id="g", league="mlb", home="NYY", away="LAD", status="pre",
                home_won=None, date="2026-07-17",
                home_name="New York Yankees", away_name="Los Angeles Dodgers")


def _events():
    return [{"id": "E1", "home_team": "New York Yankees", "away_team": "Los Angeles Dodgers"}]


def _event_odds(over=150, under=-180, player="Aaron Judge", point=0.5, key="batter_home_runs"):
    return {
        "id": "E1", "home_team": "New York Yankees", "away_team": "Los Angeles Dodgers",
        "bookmakers": [
            {"key": "dk", "markets": [{"key": key, "outcomes": [
                {"name": "Over", "description": player, "price": over, "point": point},
                {"name": "Under", "description": player, "price": under, "point": point}]}]},
            {"key": "fd", "markets": [{"key": key, "outcomes": [
                {"name": "Over", "description": player, "price": over + 10, "point": point},
                {"name": "Under", "description": player, "price": under - 10, "point": point}]}]},
        ],
    }


def _prop_mkt(ticker, title, floor):
    return MarketView(ticker=ticker, title=title, vertical=Vertical.SPORTS,
                      status="open", close_time="2026-07-17T23:00:00+00:00",
                      yes_bid=35, yes_ask=37, no_bid=63, no_ask=65, volume=8,
                      liquidity=8, raw={"floor_strike": floor})


def _signal(client=None, game=None):
    return LicensedPlayerPropSignal(espn=_Espn(game or _pre_game()),
                                    client=client or _Client(_events(), _event_odds()))


def test_prices_matched_home_run_prop_as_challenger():
    sig = _signal()
    out = sig.generate(_prop_mkt("KXMLBHR-26JUL171905LADNYY-NYYAJUDGE1-1",
                                 "Aaron Judge: 1+ home runs?", 0.5))
    assert out is not None
    assert out.source == "licensed_prop_home_runs"
    assert out.features["challenger_only"] is True and out.features["prop"] is True
    assert out.features["book_count"] == 2
    # devig of (150 / -180) ~ 0.38 P(over); averaged with the second book.
    assert 0.33 < out.probability_yes < 0.45


def test_inert_when_slot_unarmed():
    client = _Client(_events(), _event_odds(), available=False)
    sig = _signal(client=client)
    mkt = _prop_mkt("KXMLBHR-26JUL171905LADNYY-NYYAJUDGE1-1", "Aaron Judge: 1+ home runs?", 0.5)
    assert sig.applicable(mkt) is False
    assert sig.generate(mkt) is None
    assert client.event_calls == []          # never touches the network


def test_abstains_when_no_matching_line():
    # Book offers point 0.5; Kalshi market asks 1.5 ("2+") -> no match -> abstain.
    sig = _signal()
    out = sig.generate(_prop_mkt("KXMLBHR-26JUL171905LADNYY-NYYAJUDGE2-2",
                                 "Aaron Judge: 2+ home runs?", 1.5))
    assert out is None


def test_abstains_when_player_absent_from_book():
    sig = _signal()
    out = sig.generate(_prop_mkt("KXMLBHR-26JUL171905LADNYY-NYYSTANTON1-1",
                                 "Giancarlo Stanton: 1+ home runs?", 0.5))
    assert out is None


def test_fails_closed_once_game_started():
    live = Game(game_id="g", league="mlb", home="NYY", away="LAD", status="in",
                home_won=None, date="2026-07-17",
                home_name="New York Yankees", away_name="Los Angeles Dodgers")
    out = _signal(game=live).generate(
        _prop_mkt("KXMLBHR-26JUL171905LADNYY-NYYAJUDGE1-1", "Aaron Judge: 1+ home runs?", 0.5))
    assert out is None


def test_strikeouts_map_to_pitcher_market_key():
    assert STAT_TO_MARKET_KEY["strikeouts"] == "pitcher_strikeouts"
    assert STAT_TO_MARKET_KEY["home_runs"] == "batter_home_runs"
    client = _Client(_events(), _event_odds(player="Gerrit Cole", point=6.5, key="pitcher_strikeouts"))
    out = _signal(client=client).generate(
        _prop_mkt("KXMLBKS-26JUL171905LADNYY-NYYGCOLE7-7", "Gerrit Cole: 7+ strikeouts?", 6.5))
    assert out is not None and out.source == "licensed_prop_strikeouts"
    assert client.event_calls == [("E1", "pitcher_strikeouts")]


def test_teams_from_ticker_strips_doubleheader_suffix():
    assert _teams_from_ticker("KXMLBHR-26JUL171335TBBOSG1-TBYDIAZ2-2") == ("TB", "BOS")
