from __future__ import annotations

from predator_mesh.v10.build_factory import BuildEdgeFactory


def test_build_packet_manifest_contains_required_fields() -> None:
    manifest = BuildEdgeFactory().packet_manifest()
    assert manifest["verdict"] == "PASS"
    assert manifest["packets"]
    for packet in manifest["packets"]:
        assert packet["packet_id"]
        assert packet["packet_type"]
        assert packet["priority"]
        assert packet["scope_limits"]["forbidden_paths"]
        assert packet["budget"]["timeout_s"] > 0
        assert packet["proof_gate"]["required_tests"]
        assert packet["rollback_plan"]["notes"]
