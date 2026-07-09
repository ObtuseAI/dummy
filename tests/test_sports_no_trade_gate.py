from __future__ import annotations

from v18_test_helpers import assert_domain_no_trade_gate


def test_sports_no_trade_gate_blocks_stale_or_ambiguous_inputs() -> None:
    assert_domain_no_trade_gate("sports")
