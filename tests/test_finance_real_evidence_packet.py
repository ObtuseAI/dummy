from __future__ import annotations

from v19_test_helpers import assert_domain_evidence_packet


def test_finance_real_evidence_packet_tracks_release_context_shape() -> None:
    assert_domain_evidence_packet("finance")
