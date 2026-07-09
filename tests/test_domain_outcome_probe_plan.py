from __future__ import annotations

from v19_test_helpers import DOMAINS


def test_domain_outcome_probe_plan_requires_settlement_maps() -> None:
    from predator_mesh.v19.outcome_observer import OutcomeObserverActivationV2

    report = OutcomeObserverActivationV2().probe_plan_report()
    assert report["verdict"] == "PASS"
    assert set(report["domains"]) == DOMAINS
    assert report["domain_specific_settlement_map_required"] is True
