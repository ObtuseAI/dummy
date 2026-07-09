from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_evidence_stack_labels_fixture_legality_freshness_and_contradictions() -> None:
    from predator_mesh.v18.research_packets import ResearchPacketFactory

    report = ResearchPacketFactory().evidence_stack_report()

    assert_pass_report(report)
    assert report["all_evidence_has_source_legality"] is True
    assert report["fixture_evidence_labeled"] is True
    assert report["stale_data_visible"] is True
