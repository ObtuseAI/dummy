"""Tests for the Polymarket cross-venue divergence signal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.cross_venue import CrossVenueSignal, index_polymarket


def _pm_market(slug, outcomes, prices, bid=None, ask=None, liq=5000, tokens=None):
    market = {
        "slug": slug,
        "outcomes": str(outcomes),
        "outcomePrices": str(prices).replace("'", '"'),
        "bestBid": bid,
        "bestAsk": ask,
        "liquidityNum": liq,
    }
    if tokens is not None:
        market["clobTokenIds"] = str(tokens).replace("'", '"')
    return market


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
    def fetch():
        return [_pm_market("mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.355", "0.645"], 0.35, 0.36)]

    signal = CrossVenueSignal(fetch_markets=fetch)
    result = signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC"))
    assert result is not None
    assert abs(result.probability_yes - 0.355) < 1e-6

    # Subject = NYM -> the other price.
    result_nym = signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-NYM"))
    assert abs(result_nym.probability_yes - 0.645) < 1e-6


def test_signal_fail_closed_on_no_match():
    def fetch():
        return [_pm_market("mlb-lad-sf-2026-07-08", ["LAD", "SF"], ["0.6", "0.4"])]

    signal = CrossVenueSignal(fetch_markets=fetch)
    assert signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC")) is None


def test_signal_fail_closed_on_wrong_date():
    def fetch():
        return [_pm_market("mlb-kc-nym-2026-07-09", ["KC", "NYM"], ["0.4", "0.6"])]

    signal = CrossVenueSignal(fetch_markets=fetch)
    assert signal.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC")) is None


def test_alias_normalization_matches_wsh_was():
    def fetch():
        return [_pm_market("nba-wsh-bos-2026-07-08", ["WSH", "BOS"], ["0.3", "0.7"])]

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


def test_live_clob_book_replaces_gamma_price_and_adds_depth_provenance():
    def fetch():
        return [_pm_market(
            "mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.20", "0.80"],
            0.19, 0.21, liq=50_000, tokens=["kc-token", "nym-token"],
        )]

    calls = []

    def book(token_id):
        calls.append(token_id)
        return {
            "asset_id": token_id,
            "bids": [{"price": "0.34", "size": "700"}],
            "asks": [{"price": "0.38", "size": "600"}],
        }

    source = CrossVenueSignal(fetch_markets=fetch, fetch_orderbook=book)
    result = source.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC"))
    assert result is not None
    assert result.probability_yes == 0.36
    assert result.features["polymarket_price_source"] == "clob_orderbook_midpoint"
    assert result.features["polymarket_gamma_probability"] == 0.20
    assert result.features["polymarket_best_bid_size"] == 700.0
    # Per-cycle cache avoids hitting the same public book for repeated scans.
    source.generate(_market("KXMLBGAME-26JUL081810KCNYM-KC"))
    assert calls == ["kc-token"]


def test_clob_book_failure_falls_back_to_gamma_without_dropping_signal():
    def fetch():
        return [_pm_market(
            "mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.35", "0.65"],
            0.34, 0.36, tokens=["kc-token", "nym-token"],
        )]

    def unavailable(_token_id):
        raise RuntimeError("public book unavailable")

    result = CrossVenueSignal(fetch, unavailable).generate(_market())
    assert result is not None
    assert result.probability_yes == 0.35
    assert result.features["polymarket_price_source"] == "gamma_outcome_price"


def test_default_shape_can_batch_books_once_per_cycle():
    def fetch():
        return [_pm_market(
            "mlb-kc-nym-2026-07-08", ["KC", "NYM"], ["0.20", "0.80"],
            tokens=["kc-token", "nym-token"],
        )]

    calls = []

    def books(token_ids):
        calls.append(token_ids)
        return {
            "kc-token": {
                "asset_id": "kc-token",
                "bids": [{"price": "0.40", "size": "1000"}],
                "asks": [{"price": "0.42", "size": "1000"}],
            }
        }

    source = CrossVenueSignal(fetch_markets=fetch, fetch_orderbooks=books)
    result = source.generate(_market())
    assert result is not None and abs(result.probability_yes - 0.41) < 1e-9
    assert calls == [["kc-token", "nym-token"]]
