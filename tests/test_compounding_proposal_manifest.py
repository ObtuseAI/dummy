from __future__ import annotations


def test_compounding_proposal_manifest_contains_expected_benefit_and_tests() -> None:
    from predator_mesh.v19.compounding import AutonomousCompoundingEngine

    report = AutonomousCompoundingEngine().proposal_manifest()
    assert report["verdict"] == "PASS"
    assert report["proposal_count"] > 0
    assert all(item["expected_benefit"] and item["tests_required"] for item in report["proposals"])
