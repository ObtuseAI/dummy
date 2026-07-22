"""Adversarial tests for executable depth, slippage, and quote freshness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from autonomy.executable_liquidity import (
    LIQUIDITY_EVIDENCE_VERSION,
    assess_taker_liquidity,
    evaluate_quote_freshness,
)
from autonomy.fees import kalshi_taker_fee_cents
from autonomy.live_book import BookState


NOW = datetime(2026, 7, 21, 20, 0, tzinfo=timezone.utc)
TICKER = "KXMLBGAME-26JUL21-ABC"


def _quote(
    *,
    bid: int = 48,
    asks: list[list[float]] | None = None,
    received_at: str | None = None,
) -> dict:
    asks = asks if asks is not None else [[50, 10]]
    return {
        "yes_bid": bid,
        "yes_ask": int(asks[0][0]),
        "yes_ask_size": asks[0][1],
        "yes_ask_levels": asks,
        "book_received_at": received_at or NOW.isoformat(),
    }


def _assess(quote: dict, **overrides):
    kwargs = {
        "side": "yes",
        "requested_count": 10,
        "notional_cap_cents": 500,
        "probability_side": 0.80,
        "market_ticker": TICKER,
        "min_ev_cents": 3.0,
        "min_edge_cents": 0.0,
    }
    kwargs.update(overrides)
    return assess_taker_liquidity(quote, **kwargs)


def test_quote_freshness_requires_receipt_witness_and_rejects_stale_or_future():
    missing = evaluate_quote_freshness({"yes_ask": 50}, now_ts=NOW.timestamp())
    assert missing.valid is False
    assert missing.reason == "taker_quote_timestamp_missing"

    stale = evaluate_quote_freshness(
        _quote(received_at=(NOW - timedelta(seconds=6)).isoformat()),
        now_ts=NOW.timestamp(),
    )
    assert stale.valid is False and stale.reason == "taker_quote_stale"
    assert stale.age_seconds == pytest.approx(6.0)

    future = evaluate_quote_freshness(
        _quote(received_at=(NOW + timedelta(seconds=2)).isoformat()),
        now_ts=NOW.timestamp(),
    )
    assert future.valid is False and future.reason == "taker_quote_timestamp_future"

    fresh = evaluate_quote_freshness(_quote(), now_ts=NOW.timestamp())
    assert fresh.valid is True and fresh.reason == "fresh"


def test_taker_plan_uses_depth_haircut_vwap_and_worst_case_limit_notional():
    result = _assess(_quote(asks=[[50, 4], [52, 4], [54, 100]]))
    assert result.allowed is True
    plan = result.plan
    assert plan is not None
    # Only 50% of displayed depth is treated as safely executable. The 54c
    # level is outside the 3c level-slippage cap and is never counted.
    assert plan.level_fills == ((50, 2), (52, 2))
    assert plan.executable_count == 4
    assert plan.visible_depth_contracts == 8
    assert plan.usable_depth_contracts == 4
    assert plan.limit_price_cents == 52
    assert plan.modeled_vwap_cents == pytest.approx(51.0)
    assert plan.visible_cost_cents == 204
    assert plan.worst_case_notional_cents == 208
    expected_fee = (
        kalshi_taker_fee_cents(50, 2, TICKER)
        + kalshi_taker_fee_cents(52, 2, TICKER)
    )
    assert plan.modeled_fee_cents == expected_fee
    assert plan.net_ev_cents_per_contract == pytest.approx(
        80 - (204 + expected_fee) / 4
    )
    evidence = plan.evidence(NOW.isoformat())
    assert evidence["liquidity_evidence_version"] == LIQUIDITY_EVIDENCE_VERSION
    assert evidence["depth_capped"] is True
    assert evidence["fill_status"] == "unfilled_plan_only"


def test_taker_plan_never_exceeds_original_notional_when_ask_moves():
    result = _assess(
        _quote(asks=[[50, 20]]),
        requested_count=3,
        notional_cap_cents=120,
    )
    assert result.allowed is True
    plan = result.plan
    assert plan is not None
    assert plan.executable_count == 2
    assert plan.worst_case_notional_cents == 100 <= 120


def test_taker_plan_blocks_missing_thin_inconsistent_crossed_and_wide_depth():
    missing = _assess({"yes_bid": 48, "yes_ask": 50})
    assert missing.allowed is False and missing.reason == "taker_executable_depth_missing"

    thin = _assess(_quote(asks=[[50, 1]]))
    assert thin.allowed is False and thin.reason == "taker_depth_below_safety_floor"

    inconsistent = _assess({**_quote(), "yes_ask": 49})
    assert inconsistent.allowed is False and inconsistent.reason == "taker_book_inconsistent"

    crossed = _assess(_quote(bid=50))
    assert crossed.allowed is False and crossed.reason == "taker_book_crossed"

    wide = _assess(_quote(bid=20))
    assert wide.allowed is False and wide.reason == "taker_spread_exceeds_cap"


def test_taker_plan_rejects_vwap_slippage_even_when_last_level_is_within_cap():
    result = _assess(
        _quote(asks=[[50, 2], [53, 20]]),
        requested_count=4,
        notional_cap_cents=500,
    )
    assert result.allowed is False
    assert result.reason == "taker_vwap_slippage_exceeds_cap"


def test_book_state_derives_side_specific_ask_ladders_and_sums_duplicates():
    book = BookState("T")
    book.apply_snapshot({
        "yes": [[40, 2], [40, 3], [39, 4]],
        "no": [[50, 1], [55, 2], [55, 4]],
    })
    quote = book.quote()
    assert quote["yes_bid"] == 40 and quote["yes_bid_size"] == 5
    assert quote["yes_ask"] == 45 and quote["yes_ask_size"] == 6
    assert quote["yes_ask_levels"] == [[45, 6.0], [50, 1.0]]
    assert quote["no_ask_levels"] == [[60, 5.0], [61, 4.0]]
    assert quote["book_received_at"] is not None
