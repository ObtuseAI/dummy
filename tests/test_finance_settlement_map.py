from __future__ import annotations

from v18_test_helpers import assert_domain_settlement_map


def test_finance_settlement_map_requires_official_source_and_release_time() -> None:
    assert_domain_settlement_map("finance")
