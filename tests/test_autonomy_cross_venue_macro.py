"""Tests for the Polymarket crypto/econ cross-venue challenger signals (Wave-2 E4).

All fixtures are committed real Gamma-API samples (tests/fixtures/polymarket/*);
no test touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonomy.ontology import MarketView, Vertical
from autonomy.signals.cross_venue_macro import (
    CrossVenueCryptoSignal,
    CrossVenueEconSignal,
    index_polymarket_crypto,
    index_polymarket_econ,
    kalshi_crypto_key,
    kalshi_econ_key,
    parse_cpi_pm_question,
    parse_crypto_pm_question,
    parse_fed_pm_question,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "polymarket"


def _crypto_markets() -> list[dict]:
    return json.loads((_FIXTURES / "crypto_markets.json").read_text())


def _econ_markets() -> list[dict]:
    return json.loads((_FIXTURES / "econ_markets.json").read_text())


def _mv(ticker: str, close: str, vertical: Vertical, *, yes_bid=50, yes_ask=52, **raw) -> MarketView:
    return MarketView(
        ticker=ticker, title="", vertical=vertical, status="open",
        close_time=close, yes_bid=yes_bid, yes_ask=yes_ask, no_bid=48, no_ask=50,
        volume=10, liquidity=100, raw=raw,
        fetched_at="2026-07-16T12:00:00+00:00",
    )


class _FakeLedger:
    def __init__(self):
        self.calls: list[dict] = []

    def record_external_observation(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        return True


# ---------------------------------------------------------------------------
# Question parsing
# ---------------------------------------------------------------------------

def test_parse_crypto_question_variants():
    above = parse_crypto_pm_question("Will the price of Bitcoin be above $62,000 on July 20?")
    assert above == {"asset": "BTC", "comparator": "above", "strike_key": "62000.00", "strike": 62000.0}
    below = parse_crypto_pm_question("Will the price of Ethereum be less than $1,300 on July 17?")
    assert below["comparator"] == "below" and below["strike_key"] == "1300.00"
    between = parse_crypto_pm_question("Will the price of Ethereum be between $1,600 and $1,700 on July 17?")
    assert between["comparator"] == "between" and between["strike_key"] == "1600.00|1700.00"
    assert parse_crypto_pm_question("Bitcoin Up or Down - July 17") is None


def test_parse_fed_and_cpi_questions():
    fed = parse_fed_pm_question("Will the Fed decrease interest rates by 25 bps after the September 2026 meeting?")
    assert fed["outcome"] == "fed:decrease:25"
    fed50 = parse_fed_pm_question("Will the Fed decrease interest rates by 50+ bps after the July 2026 meeting?")
    assert fed50["outcome"] == "fed:decrease:50"
    cpi = parse_cpi_pm_question("Will Core CPI YoY be 2.5% in July?")
    assert cpi["outcome"] == "cpi:exact:2.5"
    cpi_le = parse_cpi_pm_question("Will Core CPI YoY be 2.2% or less in July?")
    assert cpi_le["outcome"] == "cpi:below:2.2"
    assert parse_fed_pm_question("Will Bitcoin reach $140,000?") is None


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def test_index_crypto_keys_by_asset_comparator_strike_date():
    idx = index_polymarket_crypto(_crypto_markets())
    assert ("BTC", "above", "62000.00", "20260720") in idx
    assert ("ETH", "below", "1300.00", "20260717") in idx
    assert ("ETH", "between", "1600.00|1700.00", "20260717") in idx
    # 15m up-down and long-dated "reach" markets are not threshold-matchable.
    assert all("btc-updown" not in v["slug"] for v in idx.values())
    assert all("reach-140000" not in v["slug"] for v in idx.values())


def test_index_econ_keys_by_month_and_outcome():
    idx = index_polymarket_econ(_econ_markets())
    assert ("202609", "fed:decrease:25") in idx
    assert ("202607", "fed:decrease:50") in idx
    assert ("202608", "cpi:exact:2.5") in idx
    assert ("202608", "cpi:below:2.2") in idx


# ---------------------------------------------------------------------------
# Crypto signal
# ---------------------------------------------------------------------------

def _crypto_signal(ledger=None) -> CrossVenueCryptoSignal:
    sig = CrossVenueCryptoSignal(
        fetch_markets=_crypto_markets, fetch_orderbooks=lambda _tokens: {}, ledger=ledger)
    sig.on_cycle_start()
    return sig


def test_crypto_greater_market_matches_and_extracts_yes_probability():
    sig = _crypto_signal()
    km = _mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
             strike_type="greater", floor_strike=62000.0)
    assert sig.applicable(km)
    r = sig.generate(km)
    assert r is not None
    assert r.source == "cross_venue_polymarket_crypto"
    assert abs(r.probability_yes - 0.85) < 1e-6
    assert r.features["market_type"] == "crypto_above"
    assert r.features["polymarket_price_source"] == "gamma_outcome_price"


def test_crypto_less_and_between_markets_match():
    sig = _crypto_signal()
    less = sig.generate(_mv("KXETH-26JUL1712-T1300.00", "2026-07-17T16:00:00Z", Vertical.CRYPTO,
                            strike_type="less", cap_strike=1300.0))
    assert less is not None and less.features["market_type"] == "crypto_below"
    between = sig.generate(_mv("KXETH-26JUL1712-B1600.00", "2026-07-17T16:00:00Z", Vertical.CRYPTO,
                               strike_type="between", floor_strike=1600.0, cap_strike=1700.0))
    assert between is not None and between.features["market_type"] == "crypto_between"


def test_crypto_fail_closed_on_strike_date_and_asset_mismatch():
    sig = _crypto_signal()
    # Strike not listed on Polymarket.
    assert sig.generate(_mv("KXBTCD-26JUL2012-T61000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                            strike_type="greater", floor_strike=61000.0)) is None
    # Right strike, wrong date.
    assert sig.generate(_mv("KXBTCD-26JUL2112-T62000.00", "2026-07-21T16:00:00Z", Vertical.CRYPTO,
                            strike_type="greater", floor_strike=62000.0)) is None
    # comparator mismatch (Polymarket lists 'above 62000', not 'below').
    assert sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                            strike_type="less", cap_strike=62000.0)) is None


def test_crypto_15m_and_nonthreshold_tickers_abstain():
    sig = _crypto_signal()
    # 15m direction contract parses but carries no threshold -> no PM match.
    km = _mv("KXBTC15M-26JUL160000-15", "2026-07-16T00:15:00Z", Vertical.CRYPTO)
    assert sig.generate(km) is None
    # Non-crypto vertical is never applicable.
    assert not sig.applicable(_mv("KXNBAGAME-26JUL08-X", "2026-07-08T00:00:00Z", Vertical.SPORTS))


def test_crypto_clob_midpoint_replaces_gamma_and_adds_depth():
    yes_token = "83365750894356506589098992210320440187766786626745198620141393740916642725488"

    def books(token_ids):
        assert yes_token in token_ids
        return {yes_token: {"asset_id": yes_token,
                            "bids": [{"price": "0.80", "size": "400"}],
                            "asks": [{"price": "0.82", "size": "500"}]}}

    sig = CrossVenueCryptoSignal(fetch_markets=_crypto_markets, fetch_orderbooks=books)
    sig.on_cycle_start()
    r = sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                         strike_type="greater", floor_strike=62000.0))
    assert r is not None
    assert abs(r.probability_yes - 0.81) < 1e-9
    assert r.features["polymarket_price_source"] == "clob_orderbook_midpoint"
    assert r.features["polymarket_gamma_probability"] == 0.85
    assert r.features["polymarket_best_bid_size"] == 400.0


def test_crypto_book_failure_falls_back_to_gamma():
    def books(_token_ids):
        raise RuntimeError("clob down")

    sig = CrossVenueCryptoSignal(fetch_markets=_crypto_markets, fetch_orderbooks=books)
    sig.on_cycle_start()
    r = sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                         strike_type="greater", floor_strike=62000.0))
    assert r is not None and r.features["polymarket_price_source"] == "gamma_outcome_price"


def test_crypto_thin_liquidity_widens_uncertainty():
    markets = _crypto_markets()
    thick = index_polymarket_crypto(markets)  # BTC 62k has liq ~17k
    assert thick  # sanity
    thin_markets = [dict(m, liquidityNum=150.0) for m in markets]
    thin = CrossVenueCryptoSignal(fetch_markets=lambda: thin_markets, fetch_orderbooks=lambda _t: {})
    thick_sig = CrossVenueCryptoSignal(fetch_markets=lambda: markets, fetch_orderbooks=lambda _t: {})
    thin.on_cycle_start()
    thick_sig.on_cycle_start()
    km = _mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
             strike_type="greater", floor_strike=62000.0)
    assert thin.generate(km).uncertainty > thick_sig.generate(km).uncertainty


def test_crypto_stamps_challenger_only_and_not_promotion_eligible():
    sig = _crypto_signal()
    r = sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                         strike_type="greater", floor_strike=62000.0))
    assert r.features["challenger_only"] is True
    assert "promotion_eligible" not in r.features


def test_crypto_records_divergence_observation():
    ledger = _FakeLedger()
    sig = _crypto_signal(ledger=ledger)
    sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                     yes_bid=50, yes_ask=52, strike_type="greater", floor_strike=62000.0))
    assert len(ledger.calls) == 1
    call = ledger.calls[0]
    assert call["source"] == "polymarket_crypto"
    assert call["series_id"] == "KXBTCD-26JUL2012-T62000.00"
    assert call["unit"] == "probability"
    # Kalshi implied = (50+52)/200 = 0.51; PM yes = 0.85; divergence ~ +0.34.
    assert abs(call["features"]["divergence"] - 0.34) < 1e-6
    # De-duplicated within a cycle.
    sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                     strike_type="greater", floor_strike=62000.0))
    assert len(ledger.calls) == 1


def test_crypto_diagnostics_report_match_rate():
    sig = _crypto_signal()
    sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                     strike_type="greater", floor_strike=62000.0))
    sig.generate(_mv("KXBTCD-26JUL2012-T61000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                     strike_type="greater", floor_strike=61000.0))  # no match
    diag = sig.diagnostics()
    assert diag["kalshi_attempted"] == 2 and diag["kalshi_matched"] == 1
    assert abs(diag["match_rate"] - 0.5) < 1e-9


def test_index_failure_is_swallowed():
    def boom():
        raise RuntimeError("gamma down")

    sig = CrossVenueCryptoSignal(fetch_markets=boom, fetch_orderbooks=lambda _t: {})
    sig.on_cycle_start()
    assert sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                            strike_type="greater", floor_strike=62000.0)) is None


# ---------------------------------------------------------------------------
# Econ signal
# ---------------------------------------------------------------------------

def _econ_signal(ledger=None) -> CrossVenueEconSignal:
    sig = CrossVenueEconSignal(
        fetch_markets=_econ_markets, fetch_orderbooks=lambda _tokens: {}, ledger=ledger)
    sig.on_cycle_start()
    return sig


def test_econ_fed_decision_matches():
    sig = _econ_signal()
    fm = _mv("KXFEDDECISION-26SEP-D25", "2026-09-16T00:00:00Z", Vertical.ECON,
             yes_sub_title="25 bps decrease")
    assert sig.applicable(fm)
    r = sig.generate(fm)
    assert r is not None
    assert r.source == "cross_venue_polymarket_econ"
    assert r.features["cross_venue_outcome"] == "fed:decrease:25"
    assert abs(r.probability_yes - 0.0395) < 1e-6
    assert r.features["challenger_only"] is True
    assert "promotion_eligible" not in r.features


def test_econ_cpi_between_ladder_maps_to_exact_bucket():
    sig = _econ_signal()
    cm = _mv("KXCPI-26AUG-B25", "2026-08-12T03:59:00Z", Vertical.ECON,
             strike_type="between", floor_strike=2.45, cap_strike=2.55)
    r = sig.generate(cm)
    assert r is not None and r.features["cross_venue_outcome"] == "cpi:exact:2.5"
    # 'or less' bucket maps to a Kalshi 'less' ladder.
    cm_le = _mv("KXCPI-26AUG-L22", "2026-08-12T03:59:00Z", Vertical.ECON,
                strike_type="less", cap_strike=2.2)
    r_le = sig.generate(cm_le)
    assert r_le is not None and r_le.features["cross_venue_outcome"] == "cpi:below:2.2"


def test_econ_fail_closed_on_wrong_month_or_outcome():
    sig = _econ_signal()
    # Right outcome, wrong meeting month.
    assert sig.generate(_mv("KXFEDDECISION-26OCT-D25", "2026-10-28T00:00:00Z", Vertical.ECON,
                            yes_sub_title="25 bps decrease")) is None
    # Right month, outcome not listed (75 bps).
    assert sig.generate(_mv("KXFEDDECISION-26SEP-D75", "2026-09-16T00:00:00Z", Vertical.ECON,
                            yes_sub_title="75 bps decrease")) is None


def test_econ_records_observation_with_econ_source():
    ledger = _FakeLedger()
    sig = _econ_signal(ledger=ledger)
    sig.generate(_mv("KXFEDDECISION-26SEP-D25", "2026-09-16T00:00:00Z", Vertical.ECON,
                     yes_sub_title="25 bps decrease"))
    assert ledger.calls and ledger.calls[0]["source"] == "polymarket_econ"


def test_econ_fed_no_change_round_trips():
    market = {
        "slug": "will-the-fed-not-change-interest-rates-after-july-2026",
        "question": "Will the Fed not change interest rates after the July 2026 meeting?",
        "outcomes": '["Yes", "No"]', "outcomePrices": '["0.60", "0.40"]',
        "clobTokenIds": '["yes-tok", "no-tok"]', "liquidityNum": 5000.0,
        "endDate": "2026-07-29T00:00:00Z",
    }
    assert parse_fed_pm_question(market["question"])["outcome"] == "fed:no_change:0"
    sig = CrossVenueEconSignal(fetch_markets=lambda: [market], fetch_orderbooks=lambda _t: {})
    sig.on_cycle_start()
    r = sig.generate(_mv("KXFEDDECISION-26JUL-NC", "2026-07-29T00:00:00Z", Vertical.ECON,
                         yes_sub_title="No change"))
    assert r is not None and abs(r.probability_yes - 0.60) < 1e-6


def test_crypto_abstains_on_degenerate_zero_one_price():
    market = {
        "slug": "bad", "question": "Will the price of Bitcoin be above $62,000 on July 20?",
        "outcomes": '["Yes", "No"]', "outcomePrices": '["0.0", "1.0"]',
        "clobTokenIds": '["y", "n"]', "liquidityNum": 5000.0,
        "endDate": "2026-07-20T16:00:00Z",
    }
    sig = CrossVenueCryptoSignal(fetch_markets=lambda: [market], fetch_orderbooks=lambda _t: {})
    sig.on_cycle_start()
    assert sig.generate(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO,
                            strike_type="greater", floor_strike=62000.0)) is None


def test_kalshi_implied_uses_ask_only_when_bid_absent():
    sig = _crypto_signal()
    km = MarketView(
        ticker="KXBTCD-26JUL2012-T62000.00", title="", vertical=Vertical.CRYPTO,
        status="open", close_time="2026-07-20T16:00:00Z", yes_bid=None, yes_ask=90,
        no_bid=None, no_ask=None, volume=10, liquidity=100,
        raw={"strike_type": "greater", "floor_strike": 62000.0},
        fetched_at="2026-07-16T12:00:00+00:00",
    )
    r = sig.generate(km)
    assert r is not None and abs(r.features["kalshi_implied_yes"] - 0.90) < 1e-9


def test_kalshi_key_helpers_reject_unrelated_tickers():
    assert kalshi_crypto_key(_mv("KXNBAGAME-26JUL08-X", "2026-07-08T00:00:00Z", Vertical.SPORTS)) is None
    assert kalshi_econ_key(_mv("KXBTCD-26JUL2012-T62000.00", "2026-07-20T16:00:00Z", Vertical.CRYPTO)) is None
