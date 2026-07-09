from __future__ import annotations

from v19_test_helpers import assert_domain_evidence_packet


def test_crypto_real_evidence_packet_has_no_position_management() -> None:
    assert_domain_evidence_packet("crypto")
