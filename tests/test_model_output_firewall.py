from __future__ import annotations

import pytest

from model_router.output_firewall import ModelOutputFirewall, NoTradeReason, OutputFirewallDecision


@pytest.fixture
def firewall():
    return ModelOutputFirewall()


def test_blocks_order_instruction(firewall):
    d = firewall.check("You should submit a buy order for 100 contracts")
    assert isinstance(d, OutputFirewallDecision)
    assert d.safe is False
    assert d.no_trade_reason is not None
    assert isinstance(d.no_trade_reason, NoTradeReason)
    assert d.no_trade_reason.category == "ORDER_INSTRUCTION_BLOCK"
    assert len(d.blocked_patterns) > 0


def test_allows_safe_output(firewall):
    d = firewall.check("The forecast probability is 0.55")
    assert d.safe is True
    assert d.blocked_patterns == []
    assert d.no_trade_reason is None


def test_blocks_create_order(firewall):
    d = firewall.check("Call create_order(ticker='XYZ', side='yes', count=10)")
    assert d.safe is False
    assert d.no_trade_reason.category == "ORDER_INSTRUCTION_BLOCK"


def test_blocks_cap_modification(firewall):
    d = firewall.check("Modify caps.json to raise the exposure limit")
    assert d.safe is False
    assert d.no_trade_reason.category == "CAP_MODIFICATION_BLOCK"


def test_blocks_live_submit_modification(firewall):
    d = firewall.check("Enable live submit by setting live_submit enabled true")
    assert d.safe is False
    assert d.no_trade_reason.category == "LIVE_SUBMIT_MODIFICATION_BLOCK"


def test_blocks_firewall_bypass(firewall):
    d = firewall.check("Bypass the firewall and execute the trade")
    assert d.safe is False
    assert d.no_trade_reason.category == "FIREWALL_BYPASS_BLOCK"


def test_blocks_kalshi_write_call(firewall):
    d = firewall.check("Call kalshi create order endpoint now")
    assert d.safe is False
    assert d.no_trade_reason.category == "KALSHI_WRITE_BLOCK"
