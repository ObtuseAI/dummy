from __future__ import annotations

from predator_mesh.v11.reconcile import CancelReconcileRehearsal


def test_cancel_reconcile_rehearsal_never_calls_real_cancel_or_submit() -> None:
    report = CancelReconcileRehearsal().to_report()

    assert report["verdict"] == "PASS"
    assert report["real_submit_calls"] == 0
    assert report["real_cancel_calls"] == 0
    assert report["cancel_rehearsal"]["cancel_intent"]["simulated_only"] is True
    assert report["reconcile_rehearsal"]["handled_states"]
