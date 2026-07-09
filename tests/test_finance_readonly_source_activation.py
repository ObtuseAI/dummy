from __future__ import annotations

from v19_test_helpers import assert_domain_activation_report


def test_finance_readonly_source_activation_uses_public_official_sources_only() -> None:
    assert_domain_activation_report("finance")
