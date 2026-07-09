from __future__ import annotations

from v18_test_helpers import assert_domain_research_foundation


def test_crypto_research_foundation_has_readiness_without_perp_execution() -> None:
    assert_domain_research_foundation("crypto")
