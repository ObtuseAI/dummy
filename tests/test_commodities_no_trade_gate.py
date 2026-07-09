from __future__ import annotations

from v18_test_helpers import assert_domain_no_trade_gate


def test_commodities_no_trade_gate_blocks_unclear_reference_prices() -> None:
    assert_domain_no_trade_gate("commodities")
