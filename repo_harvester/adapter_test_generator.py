from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DUMMY_ARTIFACTS = Path("C:/src/engine/dummy/artifacts/dummy")
TEST_PATH = Path("C:/src/engine/dummy/tests/test_adapter_promotion.py")

_TEST_FILE_HEADER = '''from __future__ import annotations

import ast
import inspect
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from adapters.base import DummyAdapter
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
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import (
    REJECTED_ADAPTERS,
    LiveBrokerFirewall,
    mark_adapter_rejected,
)
from repo_harvester.promotion_engine import build_promotion_records

PROMOTED_RECORDS = build_promotion_records()["adapter_targets"]


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global state and firewall rejection set before every test."""
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
    return LiveOrderRequest(
        proposal_id="p1",
        market_ticker="MARKET",
        contract_ticker="MARKET-YES",
        side="yes",
        price_cents=50,
        size=1,
        strategy_proof_reference="sp1",
        forecast_proof_reference="fp1",
        adapter_name=adapter_name,
    )


def _forbidden_call_hits(source: str) -> list[str]:
    """Static AST check for forbidden live-order function calls or imports."""
    forbidden_calls = {
        "create_order",
        "cancel_order",
        "submit_order",
        "market_order",
        "delete_order",
        "place_order",
    }
    forbidden_modules = {
        "kalshi.client",
        "polymarket",
        "pykalshi",
    }
    hits: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax_error:{exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in forbidden_calls:
                hits.append(name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                if any(forbidden in full.lower() for forbidden in forbidden_modules):
                    hits.append(full)
    return hits
'''

_PARAMETRIZED_TESTS = '''
@pytest.mark.parametrize("record", PROMOTED_RECORDS, ids=lambda r: r["adapter_name"])
def test_import(record):
    module = __import__(f"adapters.promoted.{record['module_name']}", fromlist=[record["class_name"]])
    cls = getattr(module, record["class_name"])
    assert issubclass(cls, DummyAdapter)
    assert cls().name == record["adapter_name"]


@pytest.mark.parametrize("record", PROMOTED_RECORDS, ids=lambda r: r["adapter_name"])
def test_schema_conversion(record):
    module = __import__(f"adapters.promoted.{record['module_name']}", fromlist=[record["class_name"]])
    cls = getattr(module, record["class_name"])
    adapter = cls()
    raw = {
        "market": "MARKET",
        "contract": "MARKET-YES",
        "event": "Test Event",
        "title": "Yes",
        "book": _make_book(),
    }
    forecast = adapter.to_native_forecast(raw)
    assert isinstance(forecast, Forecast)
    assert forecast.market_ticker == "MARKET"
    assert forecast.contract_ticker == "MARKET-YES"


@pytest.mark.parametrize("record", PROMOTED_RECORDS, ids=lambda r: r["adapter_name"])
def test_no_secret_leak(record):
    from live_firewall.firewall import _check_secret_redaction

    module = __import__(f"adapters.promoted.{record['module_name']}", fromlist=[record["class_name"]])
    source = inspect.getsource(module)
    assert _check_secret_redaction(source), f"Secret risk detected in {record['adapter_name']}"


@pytest.mark.parametrize("record", PROMOTED_RECORDS, ids=lambda r: r["adapter_name"])
def test_no_direct_order_path(record):
    module = __import__(f"adapters.promoted.{record['module_name']}", fromlist=[record["class_name"]])
    source = inspect.getsource(module)
    hits = _forbidden_call_hits(source)
    assert not hits, f"Forbidden live-order path in {record['adapter_name']}: {hits}"


@pytest.mark.parametrize("record", PROMOTED_RECORDS, ids=lambda r: r["adapter_name"])
def test_firewall_routing(record):
    module = __import__(f"adapters.promoted.{record['module_name']}", fromlist=[record["class_name"]])
    cls = getattr(module, record["class_name"])
    adapter = cls()
    raw = {
        "market": "MARKET",
        "contract": "MARKET-YES",
        "event": "Test Event",
        "title": "Yes",
        "book": _make_book(),
    }
    forecast = adapter.to_native_forecast(raw)
    assert isinstance(forecast, Forecast)
    # Adapters must not expose broker client methods.
    assert not hasattr(adapter, "create_order")
    assert not hasattr(adapter, "submit_order")


@pytest.mark.parametrize("record", PROMOTED_RECORDS, ids=lambda r: r["adapter_name"])
@pytest.mark.asyncio
async def test_rejected_repo_isolation(record):
    mark_adapter_rejected(record["adapter_name"])
    os.environ["KALSHI_API_KEY_ID"] = "test"
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)

    caps = load_caps()
    caps.allowed_markets = ["MARKET"]
    with patch("live_firewall.firewall.load_caps", return_value=caps):
        fw = LiveBrokerFirewall(None, ExposureTracker())
        verdict = await fw.evaluate(_make_request(record["adapter_name"]), _make_book(), _make_forecast())
        assert not verdict.allow
        assert verdict.rejected_by == "repo_bypass"
'''

def generate_tests(records: list[dict[str, Any]] | None = None) -> str:
    """Return the full pytest source for adapter promotion tests."""
    return _TEST_FILE_HEADER + _PARAMETRIZED_TESTS


def write_tests(path: Path | None = None) -> Path:
    """Write tests/test_adapter_promotion.py and return the path."""
    target = path or TEST_PATH
    target.write_text(generate_tests())
    return target


def write_adapter_test_report(passed: int, failed: int, errors: int, path: Path | None = None) -> Path:
    """Write adapter_test_report_v1.json summarising test results."""
    report_path = path or DUMMY_ARTIFACTS / "adapter_test_report_v1.json"
    DUMMY_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_file": str(TEST_PATH),
        "required_test_types": [
            "import",
            "schema_conversion",
            "no_secret_leak",
            "no_direct_order_path",
            "firewall_routing",
            "rejected_repo_isolation",
        ],
        "result": {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "overall": "PASS" if failed == 0 and errors == 0 else "FAIL",
        },
    }
    report_path.write_text(json.dumps(report, indent=2, default=str))
    return report_path


if __name__ == "__main__":
    print(write_tests())
