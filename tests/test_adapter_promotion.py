from __future__ import annotations

import ast
import inspect
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from adapters.promoted import PendingAdapter
from core import state as state_module
from core.config_loader import load_caps
from core.ontology import (
    AccountMode,
    Forecast,
    LiveOrderRequest,
    OrderBook,
    OrderBookLevel,
)
from core.state import DummyState
from forecasting.model_influence_attestation import build_model_influence_attestation
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import (
    REJECTED_ADAPTERS,
    LiveBrokerFirewall,
    mark_adapter_rejected,
)
from repo_harvester.promotion_engine import (
    build_promotion_records,
    generate_promoted_adapter_modules,
)

PENDING_RECORDS = build_promotion_records()["adapter_targets"]


@pytest.fixture(autouse=True)
def reset_state():
    fresh = DummyState()
    state_module.STATE = fresh
    import live_firewall.firewall as firewall_module

    firewall_module.STATE = fresh
    REJECTED_ADAPTERS.clear()
    yield


def _make_book() -> OrderBook:
    return OrderBook(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        bids=[OrderBookLevel(price=48, size=10)],
        asks=[OrderBookLevel(price=52, size=10)],
        timestamp=datetime.now(timezone.utc),
    )


def _make_forecast() -> Forecast:
    return Forecast(
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        event_title="Test Event",
        contract_title="Yes",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        probability_delta=Decimal("0.05"),
        confidence_score=Decimal("0.7"),
        uncertainty_band=(Decimal("0.5"), Decimal("0.6")),
        expected_edge=Decimal("0.015"),
        edge_after_fees=Decimal("0.010"),
        freshness_score=Decimal("1.0"),
        liquidity_score=Decimal("0.8"),
        spread_score=Decimal("0.8"),
        orderbook_depth_score=Decimal("0.8"),
        settlement_risk_score=Decimal("0.1"),
        source_summary="test",
        model_summary="test",
        calibration_notes="test",
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        strategy_references=[],
        proof_reference="fp1",
    )


def _make_request(adapter_name: str) -> LiveOrderRequest:
    forecast = _make_forecast()
    request_fields = {
        "proposal_id": "p1",
        "market_ticker": "MARKET",
        "contract_ticker": "MARKET-YES",
        "side": "yes",
        "price_cents": 50,
        "size": 1,
        "strategy_proof_reference": "sp1",
        "forecast_proof_reference": forecast.proof_reference,
        "adapter_name": adapter_name,
    }
    return LiveOrderRequest(
        **request_fields,
        model_influence_attestation=build_model_influence_attestation(
            forecast, request_fields
        ),
    )


def test_pending_candidates_are_metadata_not_generated_modules():
    package_dir = Path(inspect.getfile(PendingAdapter)).parent

    assert PENDING_RECORDS
    assert generate_promoted_adapter_modules(
        {"adapter_targets": PENDING_RECORDS}
    ) == []
    assert all(record["production_capability"] is False for record in PENDING_RECORDS)
    assert all(record["prediction_authority"] is False for record in PENDING_RECORDS)
    assert all(record["execution_authority"] is False for record in PENDING_RECORDS)
    assert all(
        not (package_dir / f"{record['module_name']}.py").exists()
        for record in PENDING_RECORDS
    )


@pytest.mark.parametrize(
    "record", PENDING_RECORDS, ids=lambda record: record["adapter_name"]
)
def test_one_inert_adapter_represents_all_pending_candidates(record):
    adapter = PendingAdapter.from_record(record)

    assert adapter.name == record["adapter_name"]
    assert adapter.to_native_forecast({"book": _make_book()}) is None
    assert adapter.LIFECYCLE_STATUS == "DORMANT"
    assert adapter.INTEGRATION_STATUS == "DORMANT"
    assert adapter.TEST_STATUS == "DORMANT_UNVERIFIED"
    assert adapter.UPSTREAM_INTEGRATION_VERIFIED is False
    assert adapter.PRODUCTION_CAPABILITY is False
    assert adapter.PREDICTION_AUTHORITY is False
    assert adapter.EXECUTION_AUTHORITY is False
    assert not hasattr(adapter, "create_order")
    assert not hasattr(adapter, "submit_order")


def test_pending_adapter_source_has_no_secret_or_order_path():
    from live_firewall.firewall import _check_secret_redaction

    source = inspect.getsource(PendingAdapter)
    assert _check_secret_redaction(source)

    forbidden_calls = {
        "create_order",
        "cancel_order",
        "submit_order",
        "market_order",
        "delete_order",
        "place_order",
    }
    tree = ast.parse(source)
    calls = {
        node.func.id
        if isinstance(node.func, ast.Name)
        else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not calls.intersection(forbidden_calls)


@pytest.mark.asyncio
async def test_pending_adapter_identity_remains_firewall_rejected():
    record = PENDING_RECORDS[0]
    adapter = PendingAdapter.from_record(record)
    assert adapter.to_native_forecast({"book": _make_book()}) is None

    mark_adapter_rejected(adapter.name)
    os.environ["KALSHI_API_KEY_ID"] = "test"
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["MARKET"]

    with patch("live_firewall.firewall.load_caps", return_value=caps):
        verdict = await LiveBrokerFirewall(
            None, ExposureTracker()
        ).evaluate(_make_request(adapter.name), _make_book(), _make_forecast())

    assert verdict.allow is False
    assert verdict.rejected_by == "repo_bypass"
