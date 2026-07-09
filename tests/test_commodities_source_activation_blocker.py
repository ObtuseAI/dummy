from __future__ import annotations

from v19_test_helpers import assert_domain_blocker_report


def test_commodities_source_activation_blocker_is_proof_backed() -> None:
    assert_domain_blocker_report("commodities")
