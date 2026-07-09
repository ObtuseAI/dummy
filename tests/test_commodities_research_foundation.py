from __future__ import annotations

from v18_test_helpers import assert_domain_research_foundation


def test_commodities_research_foundation_covers_energy_metals_agriculture() -> None:
    assert_domain_research_foundation("commodities")
