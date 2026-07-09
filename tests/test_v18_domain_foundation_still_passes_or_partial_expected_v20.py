from __future__ import annotations


def test_v18_domain_foundation_still_passes_or_partial_expected_v20() -> None:
    from predator_mesh.v20.mission import DummyMissionStateV6

    assert DummyMissionStateV6().to_report()["v18_domain_foundation_status"] in {"PASS", "PARTIAL"}

