from __future__ import annotations


def test_improvement_proposal_factory_generates_non_executing_evidence_backed_proposals() -> None:
    from predator_mesh.v17.improvements import ImprovementProposalFactory

    report = ImprovementProposalFactory().to_report()

    assert report["proposal_count"] > 0
    assert report["proposals_execute_automatically"] is False
