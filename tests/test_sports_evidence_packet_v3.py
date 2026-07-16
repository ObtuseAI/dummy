from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_sports_evidence_packet_v3_labels_licensed_lineup_blocker() -> None:
    report = assert_v20_report("sports_evidence_packet_v3_report.json", "source_blockers")
    assert "injury/lineup licensed gate" in report["source_blockers"]
