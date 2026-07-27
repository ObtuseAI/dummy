"""Wire-schema tests for Kalshi create-order payload construction."""

from __future__ import annotations

from predator_mesh.brokers.kalshi_types import kalshi_create_order_payload
from predator_mesh.brokers.livebrokerfirewall_adapter import LimitOrderRequest


def _req(**overrides):
    defaults = dict(
        venue="KALSHI",
        order_type="LIMIT",
        market_orders_allowed=False,
        side="yes",
        action="buy",
        price=7,
        quantity=1,
        idempotency_key="idem-123",
        market_ticker="KXTEST-PAYLOAD",
    )
    defaults.update(overrides)
    return LimitOrderRequest(**defaults)


def test_yes_side_uses_yes_price():
    payload = kalshi_create_order_payload(_req(side="yes", price=7))
    assert payload["yes_price"] == 7
    assert "no_price" not in payload
    assert "price" not in payload


def test_no_side_uses_no_price():
    payload = kalshi_create_order_payload(_req(side="no", price=93))
    assert payload["no_price"] == 93
    assert "yes_price" not in payload
    assert "price" not in payload


def test_client_order_id_from_idempotency_key():
    payload = kalshi_create_order_payload(_req(idempotency_key="idem-xyz"))
    assert payload["client_order_id"] == "idem-xyz"


def test_required_fields_present():
    payload = kalshi_create_order_payload(_req())
    for key in ("ticker", "side", "action", "type", "count", "client_order_id"):
        assert key in payload, key
    assert payload["type"] == "limit"
    assert payload["ticker"] == "KXTEST-PAYLOAD"
    assert payload["count"] == 1


def test_firewall_build_order_uses_event_order_v2_fixed_point_wire():
    from core.ontology import LiveOrderRequest
    from live_firewall.firewall import LiveBrokerFirewall
    from live_firewall.exposure_tracker import ExposureTracker

    firewall = LiveBrokerFirewall(kalshi_client=None, exposure_tracker=ExposureTracker())
    req = LiveOrderRequest(
        proposal_id="prop-1",
        market_ticker="KXTEST",
        contract_ticker="KXTEST",
        side="yes",
        price_cents=12,
        size=1,
        strategy_proof_reference="s",
        forecast_proof_reference="f",
        adapter_name="a",
        expiration_ts=1_900_000_000,
    )
    order = firewall._build_order(req)
    assert order["side"] == "bid"
    assert order["price"] == "0.1200"
    assert order["count"] == "1.00"
    assert order["client_order_id"] == "prop-1"
    assert order["time_in_force"] == "good_till_canceled"
    assert order["post_only"] is True
    assert order["expiration_time"] == 1_900_000_000
    assert order["subaccount"] == 0
