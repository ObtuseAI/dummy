from __future__ import annotations

from v19_test_helpers import assert_domain_activation_report


def test_crypto_readonly_source_activation_excludes_perps_and_leverage() -> None:
    assert_domain_activation_report("crypto")
