from __future__ import annotations


def test_v19_activation_architecture_still_passes_or_partial_expected_v20() -> None:
    from predator_mesh.v20.mission import DummyMissionStateV6

    assert DummyMissionStateV6().to_report()["v19_activation_architecture_status"] in {"PASS", "PARTIAL"}

