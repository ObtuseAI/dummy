from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_oil_evidence_packet_labels_context_and_blockers() -> None:
    report = assert_v20_report("oil_evidence_packet_report_v1.json", "source_blockers")
    assert "CL futures orderbook/trades" in report["source_blockers"]
    assert report["fixture_evidence_claimed_real"] is False
