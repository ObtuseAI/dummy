from __future__ import annotations

from v18_test_helpers import assert_domain_settlement_map


def test_sports_settlement_map_requires_explicit_rule_source() -> None:
    assert_domain_settlement_map("sports")
