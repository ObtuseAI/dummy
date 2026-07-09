from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_source_contradiction_profile_represents_disagreements_without_hiding_them() -> None:
    from predator_mesh.v18.source_truth import SourceTruthRegistryV2

    report = SourceTruthRegistryV2().contradiction_report()

    assert_pass_report(report)
    assert report["contradictions_represented"] is True
    assert report["contradictions"]
