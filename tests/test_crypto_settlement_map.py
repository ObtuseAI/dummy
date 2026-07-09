from __future__ import annotations

from v18_test_helpers import assert_domain_settlement_map


def test_crypto_settlement_map_requires_reference_price_source() -> None:
    assert_domain_settlement_map("crypto")
