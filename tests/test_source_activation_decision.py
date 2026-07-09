from __future__ import annotations

from v19_test_helpers import ALLOWED_MODES


def test_source_activation_decision_requires_blocker_or_real_proof() -> None:
    from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController

    report = RealReadOnlySourceActivationController().decision_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert all(item["mode"] in ALLOWED_MODES for item in report["decisions"])
    assert all(item["proof"] or item["blockers"] for item in report["decisions"])
