from __future__ import annotations


def test_source_approval_gate_blocks_unapproved_and_commercial_sources() -> None:
    from predator_mesh.v20.approval_gates import SourceApprovalGateV2
    from predator_mesh.v20.source_universe import SourceUniverse

    report = SourceApprovalGateV2(SourceUniverse()).to_report()

    assert report["verdict"] == "PASS"
    assert report["commercial_sources_activated_without_approval"] == []
    assert report["unapproved_sources_activated"] == []
    assert report["source_api_key_values_exposed"] is False
    assert report["approval_status_counts"]["BLOCKED_LICENSE_REQUIRED"] > 0
