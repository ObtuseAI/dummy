from __future__ import annotations


def test_evidence_mode_selector_never_mixes_real_and_fixture_without_labels() -> None:
    from predator_mesh.v19.research_ops import EvidenceModeSelector

    report = EvidenceModeSelector().to_report()
    assert report["verdict"] == "PASS"
    assert report["mixed_without_labels"] is False
