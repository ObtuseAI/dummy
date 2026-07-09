from __future__ import annotations

from v19_test_helpers import assert_domain_evidence_packet


def test_commodities_real_evidence_packet_keeps_category_context() -> None:
    assert_domain_evidence_packet("commodities")
