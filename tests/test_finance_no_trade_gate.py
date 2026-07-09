from __future__ import annotations

from v18_test_helpers import assert_domain_no_trade_gate


def test_finance_no_trade_gate_blocks_ambiguous_or_stale_macro_events() -> None:
    assert_domain_no_trade_gate("finance")
