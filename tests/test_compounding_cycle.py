from __future__ import annotations


def test_compounding_cycle_has_guardrails_and_proof_refs() -> None:
    from predator_mesh.v19.compounding import AutonomousCompoundingEngine

    report = AutonomousCompoundingEngine().cycle_report()
    assert report["verdict"] == "PASS"
    assert report["guardrails"]
    assert report["proof_refs"]
