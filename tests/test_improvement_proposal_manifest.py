from __future__ import annotations


def test_improvement_proposal_manifest_includes_tests_and_risk_notes() -> None:
    from predator_mesh.v17.improvements import ImprovementProposalFactory

    manifest = ImprovementProposalFactory().manifest()

    assert manifest["proposals"][0]["tests_required"]
    assert manifest["proposals"][0]["risk_intelligence_notes"]
