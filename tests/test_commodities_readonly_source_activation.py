from __future__ import annotations

from v19_test_helpers import assert_domain_activation_report


def test_commodities_readonly_source_activation_blocks_unapproved_paid_data() -> None:
    assert_domain_activation_report("commodities")
