"""Ensure no live Kalshi order is submitted without explicit operator approval."""

import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from core import state as state_module
from core.config_loader import load_caps
from core.ontology import AccountMode
from execution.hybrid_path import HybridLiveCapRehearsalV2


ROOT = Path("C:/src/engine/dummy")


@pytest.fixture(autouse=True)
def reset_state():
    fresh = state_module.DummyState()
    state_module.STATE = fresh
    import live_firewall.firewall as firewall_module

    firewall_module.STATE = fresh
    firewall_module.REJECTED_ADAPTERS.clear()
    original_key = os.environ.get("KALSHI_API_KEY_ID")
    os.environ["KALSHI_API_KEY_ID"] = "test"
    try:
        yield
    finally:
        firewall_module.REJECTED_ADAPTERS.clear()
        if original_key is None:
            os.environ.pop("KALSHI_API_KEY_ID", None)
        else:
            os.environ["KALSHI_API_KEY_ID"] = original_key


@pytest.mark.asyncio
async def test_v2_rehearsal_does_not_submit_without_operator_approval():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = load_caps()
    caps.allowed_markets = ["SPX-ABOVE-5000"]
    with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
        "execution.hybrid_path.load_caps", return_value=caps
    ):
        rehearsal = HybridLiveCapRehearsalV2()
        result = await rehearsal.rehearse("SPX-ABOVE-5000", "SPX-ABOVE-5000-YES")

    assert result["would_submit"] is False
    assert result["blocked_reason"] == "live_submit_disabled"
    assert result["live_submitted"] is False
    assert result["order_result"] is None


def test_live_submit_config_is_disabled_by_default():
    path = ROOT / "configs" / "live_submit.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    assert config.get("enabled") is not True


def test_valid_operator_one_proof_config_would_enable_firewall():
    """A fully scoped, expiring, one-proof config is recognised as valid.

    This does NOT mutate the repo config and does NOT submit an order.
    """
    from datetime import datetime, timezone, timedelta
    from core.live_submit_state import validate_operator_one_proof_enabled

    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    config = {
        "enabled": True,
        "operator": "chris",
        "reason": "one controlled proof",
        "timestamp": now,
        "expiry": future,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": False,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "explicit_acknowledgement": (
            "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only"
        ),
    }
    result = validate_operator_one_proof_enabled(config)
    assert result.ok is True, result.errors


def test_market_orders_allowed_true_is_rejected_for_one_proof():
    from datetime import datetime, timezone, timedelta
    from core.live_submit_state import validate_operator_one_proof_enabled

    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    config = {
        "enabled": True,
        "operator": "chris",
        "reason": "one controlled proof",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiry": future,
        "proof_scope": "one_controlled_proof",
        "auto_run": False,
        "weaken_gates": False,
        "requires_command_seal": True,
        "requires_livebrokerfirewall": True,
        "requires_limit_order": True,
        "market_orders_allowed": True,
        "order_type_policy": "LIMIT_ONLY",
        "max_order_count": 1,
        "explicit_acknowledgement": (
            "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only"
        ),
    }
    result = validate_operator_one_proof_enabled(config)
    assert result.ok is False
    assert any("market_orders_allowed" in e for e in result.errors)


def test_only_allowed_callers_invoke_create_order():
    excluded = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "tests",
        "artifacts",
    }
    call_re = re.compile(r'(?<![\w"\'])create_order\s*\(')
    offenders = set()
    for py in ROOT.rglob("*.py"):
        if any(part in excluded for part in py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if call_re.search(line) and "def create_order(" not in line:
                offenders.add(py.relative_to(ROOT).as_posix())
                break
    allowed = {"live_firewall/firewall.py", "kalshi/submitter.py"}
    assert offenders <= allowed, offenders
