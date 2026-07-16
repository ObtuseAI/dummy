from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_nasdaq_evidence_packet_labels_static_context_and_blockers() -> None:
    report = assert_v20_report("nasdaq_evidence_packet_report_v1.json", "source_blockers")
    assert report["fixture_evidence_claimed_real"] is False
    assert report["source_blockers"]
