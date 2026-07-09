"""Tests for the Polymarket cross-venue divergence signal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.cross_venue import CrossVenueSignal, index_polymarket


def _pm_market(slug, outcomes, prices, bid=None, ask=None, liq=5000):
    return {
        "slug": slug,
        "outcomes": str(outcomes),
        "outcomePrices": str(prices).replace("'", '"'),
        "bestBid": bid,
        "bestAsk": ask,
        "liquidityNum": liq,
    }


def _market(ticker="KXMLBGAME-26JUL081810KCNYM-KC"):
    return MarketView(
        ticker=ticker, title="KC vs NYM", vertical=Vertical.SPORTS,
        status="active", close_time=(datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        yes_bid=45, yes_ask=55, no_bid=45, no_ask=55, volume=100, liquidity=100,
    )


def test_index_parses_slug_and_prices():
    idx = index_polymarket([
        _pm_market("mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.355", "0.645"], bid=0.35, ask=0.36),
        _pm_market("some-nonsports-market", ["Yes", "No"], ["0.5", "0.5"]),
    ])
    assert len(idx) == 1
    key = ("mlb", frozenset({"KC", "NYM"}), "20260708")
    assert key in idx
    assert idx[key]["prices"] == [0.355, 0.645]


def test_signal_extracts_subject_probability():
    fetch = lambda: [_pm_market("mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.355", "0.645"], 0.35, 0.36)]
    signal = CrossVenueSignal(fetch_markets=fetch)
    result = signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC"))
    assert result is not None
    assert abs(result.probability_yes - 0.355) < 1e-6

    # Subject = NYM -> the other price.
    result_nym = signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-NYM"))
    assert abs(result_nym.probability_yes - 0.645) < 1e-6


def test_signal_fail_closed_on_no_match():
    fetch = lambda: [_pm_market("mlb-lad-sf-2026-07-08", ["LAD", "SF"], ["0.6", "0.4"])]
    signal = CrossVenueSignal(fetch_markets=fetch)
    assert signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC")) is None


def test_signal_fail_closed_on_wrong_date():
    fetch = lambda: [_pm_market("mlb-kc-nym-2026-07-09", ["KC", "NYM"], ["0.4", "0.6"])]
    signal = CrossVenueSignal(fetch_markets=fetch)
    assert signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC")) is None


def test_alias_normalization_matches_wsh_was():
    fetch = lambda: [_pm_market("nba-wsh-bos-2026-07-08", ["WSH", "BOS"], ["0.3", "0.7"])]
    signal = CrossVenueSignal(fetch_markets=fetch)
    # Kalshi/ESPN uses WAS; alias maps WSH->WAS so the set matches.
    result = signal.generate(_market("KXNBAGAME-26JUL08WASBOS-WAS"))
    assert result is not None
    assert abs(result.probability_yes - 0.3) < 1e-6


def test_thin_liquidity_widens_uncertainty():
    thick = CrossVenueSignal(fetch_markets=lambda: [
        _pm_market("mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.4", "0.6"], 0.39, 0.41, liq=50000)])
    thin = CrossVenueSignal(fetch_markets=lambda: [
        _pm_market("mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.4", "0.6"], 0.30, 0.50, liq=200)])
    u_thick = thick.generate(_market()).uncertainty
    u_thin = thin.generate(_market()).uncertainty
    assert u_thin > u_thick


def test_index_failure_is_swallowed():
    def boom():
        raise RuntimeError("polymarket down")

    signal = CrossVenueSignal(fetch_markets=boom)
    signal.on_cycle_start()
    assert signal.generate(_market()) is None  # empty index, no crash
