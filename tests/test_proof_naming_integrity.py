from __future__ import annotations


def test_proof_naming_integrity_detects_v16_labels() -> None:
    from predator_mesh.v16.proof_freshness import ProofNamingIntegrityCheck

    report = ProofNamingIntegrityCheck(["final_report_v16.json", "real_terrain_truth_resolver_report_v1.json"]).to_report()

    assert report["mismatched_version_labels"] == []
    assert report["verdict"] == "PASS"
