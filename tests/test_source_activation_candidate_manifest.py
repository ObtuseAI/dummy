from __future__ import annotations

from v19_test_helpers import DOMAINS


def test_source_activation_candidate_manifest_requires_legality_and_timeouts() -> None:
    from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController

    report = RealReadOnlySourceActivationController().candidate_manifest()
    assert report["verdict"] == "PASS"
    assert set(report["candidate_domains"]) == DOMAINS
    assert all(item["legality_class"] for item in report["candidates"])
    assert all(item["timeout_seconds"] <= 10 for item in report["candidates"])
