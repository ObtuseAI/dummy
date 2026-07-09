from __future__ import annotations


def test_env_config_redaction_proof_v19_uses_placeholder_only_repair_hints() -> None:
    from predator_mesh.v19.env_hygiene import EnvConfigRedactionProof

    report = EnvConfigRedactionProof().to_report()
    assert report["verdict"] == "PASS"
    assert report["actual_secret_values_exposed"] is False
    assert report["repair_hints_placeholder_only"] is True
