"""Tests for the read-only pre-submit validator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


from kalshi.presubmit import (
    presubmit_validate,
    validate_order_body_schema,
    write_presubmit_report,
)

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def _market(**overrides):
    market = {
        "ticker": "KXTEST-PRESUBMIT",
        "status": "active",
        "close_time": (NOW + timedelta(days=2)).isoformat(),
        "tick_size": 1,
    }
    market.update(overrides)
    return market


def _fetch_market_factory(market):
    def fetch(ticker):
        return market
    return fetch


def _fetch_orderbook_factory(orderbook):
    def fetch(ticker):
        return orderbook
    return fetch


def test_passes_on_active_market_valid_price():
    report = presubmit_validate(
        ticker="KXTEST-PRESUBMIT",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market()),
        fetch_orderbook=_fetch_orderbook_factory({"yes": [[41, 100]], "no": [[58, 50]]}),
        now=NOW,
    )
    assert report.passed is True
    assert report.blockers == []


def test_blocks_closed_market():
    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market(status="closed")),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert report.passed is False
    assert any("market_status_not_tradable" in b for b in report.blockers)


def test_blocks_imminent_close():
    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market(close_time=(NOW + timedelta(minutes=10)).isoformat())),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert any("closes_within" in b for b in report.blockers)


def test_blocks_already_closed_time():
    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market(close_time=(NOW - timedelta(hours=1)).isoformat())),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert "market_already_closed" in report.blockers


def test_blocks_price_out_of_range():
    report = presubmit_validate(
        ticker="T",
        price_cents=0,
        count=1,
        fetch_market=_fetch_market_factory(_market()),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert "price_out_of_1_99_cents" in report.blockers


def test_blocks_off_tick_price():
    report = presubmit_validate(
        ticker="T",
        price_cents=43,
        count=1,
        fetch_market=_fetch_market_factory(_market(tick_size=5)),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert any(b.startswith("price_off_tick") for b in report.blockers)


def test_blocks_missing_market():
    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory({}),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert "market_not_found" in report.blockers


def test_fetch_failure_is_a_blocker_not_an_exception():
    def boom(ticker):
        raise RuntimeError("network down")

    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=boom,
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert report.passed is False
    assert any(b.startswith("market_fetch_failed") for b in report.blockers)


def test_empty_orderbook_blocks_presubmit():
    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market()),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    assert report.passed is False
    assert "orderbook_empty" in report.blockers


def test_orderbook_fetch_failure_blocks_presubmit():
    def fail(_ticker):
        raise RuntimeError("network down")

    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market()),
        fetch_orderbook=fail,
        now=NOW,
    )
    assert report.passed is False
    assert "orderbook_fetch_failed:RuntimeError" in report.blockers


def test_order_body_schema_valid_v2_body():
    body = {
        "ticker": "T",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "client_order_id": "abc",
        "yes_price": 42,
    }
    assert validate_order_body_schema(body) == []


def test_order_body_schema_rejects_flat_price():
    body = {
        "ticker": "T",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "client_order_id": "abc",
        "price": 42,
    }
    errors = validate_order_body_schema(body)
    assert "flat_price_field_not_in_v2_schema" in errors
    assert "exactly_one_of_yes_price_or_no_price_required" in errors


def test_order_body_schema_rejects_both_prices():
    body = {
        "ticker": "T",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "client_order_id": "abc",
        "yes_price": 42,
        "no_price": 58,
    }
    assert "exactly_one_of_yes_price_or_no_price_required" in validate_order_body_schema(body)


def test_order_body_schema_requires_client_order_id():
    body = {
        "ticker": "T",
        "side": "yes",
        "action": "buy",
        "type": "limit",
        "count": 1,
        "yes_price": 42,
    }
    assert "missing_field:client_order_id" in validate_order_body_schema(body)


def test_write_report_creates_timestamped_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_EVIDENCE_ROOT", str(tmp_path))
    report = presubmit_validate(
        ticker="T",
        price_cents=42,
        count=1,
        fetch_market=_fetch_market_factory(_market()),
        fetch_orderbook=_fetch_orderbook_factory({}),
        now=NOW,
    )
    path = write_presubmit_report(report)
    assert path.exists()
    assert "presubmit_checks" in str(path)
