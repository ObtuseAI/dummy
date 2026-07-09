from __future__ import annotations


def test_domain_settlement_truth_schema_is_explicit_and_proof_backed() -> None:
    from predator_mesh.v17.outcomes import DomainOutcomeOntology

    report = DomainOutcomeOntology().settlement_truth_schema_report()

    assert "RESOLVED_TRUE" in report["settlement_truth_values"]
    assert "AMBIGUOUS" in report["settlement_truth_values"]
    assert report["proof_refs_supported"] is True
