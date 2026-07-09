from __future__ import annotations

from v19_test_helpers import assert_domain_evidence_packet


def test_sports_real_evidence_packet_keeps_fixture_fallback_labeled() -> None:
    assert_domain_evidence_packet("sports")
