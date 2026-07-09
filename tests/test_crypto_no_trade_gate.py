from __future__ import annotations

from v18_test_helpers import assert_domain_no_trade_gate


def test_crypto_no_trade_gate_blocks_stale_or_fragmented_sources() -> None:
    assert_domain_no_trade_gate("crypto")
