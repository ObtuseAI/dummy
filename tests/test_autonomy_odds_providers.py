"""Tests for the licensed sportsbook-odds provider (governance-gated)."""
from __future__ import annotations

from types import SimpleNamespace

from autonomy.odds_providers import (
    LicensedOddsProvider,
    devigged_home_probability,
    make_book_fn,
)


def _events(home_price, away_price, home="Houston Astros", away="Texas Rangers"):
    return [{
        "home_team": home, "away_team": away,
        "bookmakers": [
            {"key": "dk", "markets": [{"key": "h2h", "outcomes": [
                {"name": home, "price": home_price},
                {"name": away, "price": away_price},
            ]}]},
            {"key": "fd", "markets": [{"key": "h2h", "outcomes": [
                {"name": home, "price": home_price},
                {"name": away, "price": away_price},
            ]}]},
        ],
    }]


def test_devig_averages_books_and_removes_vig():
    # -150 home / +130 away. Raw implied: 0.60 and ~0.4348, sum 1.0348 (vig).
    p = devigged_home_probability(_events(-150, 130), "Houston Astros", "Texas Rangers")
    assert p is not None
    assert abs(p - (0.60 / (0.60 + 100.0 / 230.0))) < 1e-6
    assert 0.5 < p < 0.62  # favored home, vig removed


def test_devig_matches_on_nickname_or_abbrev_token():
    # Kalshi-style short tokens still resolve against full API names.
    p = devigged_home_probability(_events(-150, 130), "Astros", "Rangers")
    assert p is not None and p > 0.5


def test_devig_returns_none_for_unmatched_game():
    assert devigged_home_probability(_events(-150, 130), "New York Mets", "Chicago Cubs") is None


def test_devig_returns_none_when_no_h2h_prices():
    events = [{"home_team": "Houston Astros", "away_team": "Texas Rangers",
               "bookmakers": [{"key": "dk", "markets": [{"key": "spreads", "outcomes": []}]}]}]
    assert devigged_home_probability(events, "Houston Astros", "Texas Rangers") is None


def test_provider_is_inert_unless_armed():
    # No key / not enabled -> available False -> always None (even with a feed).
    disabled = LicensedOddsProvider(api_key=None, enabled=False,
                                    fetch_fn=lambda s, k: _events(-150, 130))
    assert disabled.available is False
    assert disabled.home_win_probability("Houston Astros", "Texas Rangers") is None

    enabled_no_key = LicensedOddsProvider(api_key=None, enabled=True,
                                          fetch_fn=lambda s, k: _events(-150, 130))
    assert enabled_no_key.available is False

    key_not_enabled = LicensedOddsProvider(api_key="sk", enabled=False,
                                           fetch_fn=lambda s, k: _events(-150, 130))
    assert key_not_enabled.available is False


def test_armed_provider_returns_devigged_probability():
    provider = LicensedOddsProvider(
        api_key="sk-test", enabled=True, fetch_fn=lambda s, k: _events(-150, 130))
    assert provider.available is True
    p = provider.home_win_probability("Houston Astros", "Texas Rangers")
    assert p is not None and 0.5 < p < 0.62


def test_armed_provider_is_fail_closed_on_fetch_error():
    def boom(_s, _k):
        raise RuntimeError("api down")
    provider = LicensedOddsProvider(api_key="sk", enabled=True, fetch_fn=boom)
    assert provider.home_win_probability("Houston Astros", "Texas Rangers") is None


def test_make_book_fn_flips_for_away_yes_side():
    provider = LicensedOddsProvider(
        api_key="sk", enabled=True, fetch_fn=lambda s, k: _events(-150, 130))
    home_market = SimpleNamespace(ticker="H")
    away_market = SimpleNamespace(ticker="A")

    def resolve(market):
        if market.ticker == "H":
            return ("Houston Astros", "Texas Rangers", True)   # YES = home
        return ("Houston Astros", "Texas Rangers", False)      # YES = away

    book_fn = make_book_fn(provider, resolve)
    p_home = book_fn(home_market)
    p_away = book_fn(away_market)
    assert abs((p_home + p_away) - 1.0) < 1e-9
    assert p_home > 0.5 > p_away


def test_make_book_fn_abstains_when_teams_unresolved():
    provider = LicensedOddsProvider(api_key="sk", enabled=True,
                                    fetch_fn=lambda s, k: _events(-150, 130))
    book_fn = make_book_fn(provider, lambda m: None)
    assert book_fn(SimpleNamespace(ticker="X")) is None
