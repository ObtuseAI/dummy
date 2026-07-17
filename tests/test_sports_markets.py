"""Wave-10: per-game sports-market registry + classifier.

Every ticker below is a REAL open Kalshi market pulled live from
/markets?series_ticker=... on 2026-07-17 (LAD@NYY / STL@AZ / TB@BOS slates),
so this pins the classifier to actual Kalshi shapes, not invented ones.
"""
from __future__ import annotations

from autonomy.ontology import MarketView, Vertical
from autonomy.sports.espn import canonical_team
from autonomy.sports_markets import (
    SPREAD,
    TEAM_TOTAL,
    TOTAL,
    WINNER,
    YRFI,
    classify,
    discovery_series,
    is_known_sports_market,
    registered_series,
    spec_for,
)


def _mkt(ticker: str, title: str, *, floor=None, vertical=Vertical.SPORTS) -> MarketView:
    raw = {}
    if floor is not None:
        raw["floor_strike"] = floor
    return MarketView(
        ticker=ticker, title=title, vertical=vertical, status="open",
        close_time="2026-07-17T23:00:00+00:00", yes_bid=40, yes_ask=42,
        no_bid=58, no_ask=60, volume=10, liquidity=10, raw=raw)


# ---- game lines ---------------------------------------------------------------

def test_winner_full_game():
    info = classify(_mkt("KXMLBGAME-26JUL191920LADNYY-NYY",
                         "Los Angeles D vs New York Y Winner?"))
    assert info is not None
    assert (info.league, info.market_type, info.segment) == ("mlb", WINNER, "full")
    assert info.subject == canonical_team("mlb", "NYY")
    assert info.date_yyyymmdd == "20260719"
    assert info.is_tie is False and info.three_way is False


def test_spread_full_game_reads_strike():
    info = classify(_mkt("KXMLBSPREAD-26JUL171335TBBOSG1-BOS11",
                         "Red Sox wins by over 10.5 runs?", floor=10.5))
    assert info.market_type == SPREAD and info.segment == "full"
    assert info.subject == canonical_team("mlb", "BOS")
    assert info.threshold == 10.5
    assert info.date_yyyymmdd == "20260717"       # doubleheader G1 suffix tolerated


def test_total_full_game():
    info = classify(_mkt("KXMLBTOTAL-26JUL181610STLAZ-9",
                         "St. Louis vs Arizona Total Runs?", floor=8.5))
    assert info.market_type == TOTAL and info.threshold == 8.5
    assert info.subject is None                    # totals have no subject team


def test_team_total_has_subject_and_line():
    info = classify(_mkt("KXMLBTEAMTOTAL-26JUL181610STLAZ-STL8",
                         "Will St. Louis score over 7.5 runs?", floor=7.5))
    assert info.market_type == TEAM_TOTAL
    assert info.subject == canonical_team("mlb", "STL")
    assert info.threshold == 7.5


def test_yrfi():
    info = classify(_mkt("KXMLBRFI-26JUL191920LADNYY",
                         "Los Angeles D vs New York Y First Inning Run?"))
    assert info.market_type == YRFI and info.segment == "full"


# ---- first five innings (the F5 gameline sub-options) -------------------------

def test_f5_winner_is_three_way_tie_leg():
    info = classify(_mkt("KXMLBF5-26JUL181610STLAZ-TIE",
                         "St. Louis vs Arizona first 5 innings tie?"))
    assert (info.market_type, info.segment) == (WINNER, "f5")
    assert info.three_way is True and info.is_tie is True
    assert info.subject == "TIE"


def test_f5_winner_team_leg():
    info = classify(_mkt("KXMLBF5-26JUL181610STLAZ-STL",
                         "St. Louis vs Arizona first 5 innings winner?"))
    assert info.segment == "f5" and info.three_way is True
    assert info.is_tie is False
    assert info.subject == canonical_team("mlb", "STL")


def test_f5_spread_and_total():
    sp = classify(_mkt("KXMLBF5SPREAD-26JUL181610STLAZ-STL3",
                       "St. Louis wins first 5 innings by over 2.5 runs?", floor=2.5))
    assert (sp.market_type, sp.segment, sp.threshold) == (SPREAD, "f5", 2.5)
    assert sp.subject == canonical_team("mlb", "STL")
    tot = classify(_mkt("KXMLBF5TOTAL-26JUL181610STLAZ-7",
                        "St. Louis vs Arizona first 5 innings runs?", floor=6.5))
    assert (tot.market_type, tot.segment, tot.threshold) == (TOTAL, "f5", 6.5)


# ---- player props -------------------------------------------------------------

def test_home_run_prop_reads_player_and_line():
    info = classify(_mkt("KXMLBHR-26JUL171335TBBOSG1-TBYDIAZ2-2",
                         "Yandy Diaz: 2+ home runs?", floor=1.5))
    assert info.is_prop is True and info.stat == "home_runs"
    assert info.subject == "Yandy Diaz"            # subject carries the player
    assert info.threshold == 1.5
    assert info.event_ticker == "KXMLBHR-26JUL171335TBBOSG1"


def test_total_bases_prop():
    info = classify(_mkt("KXMLBTB-26JUL171335TBBOSG1-TBYDIAZ2-6",
                         "Yandy Diaz: 6+ total bases?", floor=5.5))
    assert info.is_prop and info.stat == "total_bases" and info.subject == "Yandy Diaz"


# ---- registry hygiene ---------------------------------------------------------

def test_non_sports_and_unknown_series_return_none():
    assert classify(_mkt("KXBTC15M-26JUL1712-B120000", "BTC?", vertical=Vertical.CRYPTO)) is None
    assert classify(_mkt("KXMLBWORLD-26-LAD", "World Series?")) is None  # futures, not per-game
    assert is_known_sports_market("KXMLBWORLD-26-LAD") is False


def test_discovery_is_subset_of_registered_and_has_the_new_types():
    disc = set(discovery_series())
    reg = set(registered_series())
    assert disc <= reg
    # The Wave-10 additions are all discoverable now.
    for s in ["KXMLBTEAMTOTAL", "KXMLBF5", "KXMLBF5SPREAD", "KXMLBF5TOTAL",
              "KXMLBHR", "KXMLBKS", "KXMLBTB", "KXMLBSB",
              "KXWNBAGAME", "KXWNBASPREAD", "KXWNBATOTAL",
              "KXNBASPREAD", "KXNFLTEAMTOTAL", "KXNHLSPREAD"]:
        assert s in disc, s
    # Segment lines are registered but staged (not yet discovered).
    assert "KXNFL1QTOTAL" in reg and "KXNFL1QTOTAL" not in disc
    assert spec_for("KXMLBF5").three_way is True


def test_scanner_watchlist_covers_the_registry_surface():
    """Discovery is registry-derived: every discoverable series is on the
    scanner watchlist, and the merge introduces no duplicates."""
    from autonomy.scanner import WATCHLIST_SERIES

    assert len(WATCHLIST_SERIES) == len(set(WATCHLIST_SERIES))
    watch = set(WATCHLIST_SERIES)
    for s in discovery_series():
        assert s in watch, s
