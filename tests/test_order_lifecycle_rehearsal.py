from __future__ import annotations

from predator_mesh.v11.reconcile import OrderLifecycleState, CancelReconcileRehearsal


def test_order_lifecycle_rehearsal_contains_expected_states() -> None:
    report = CancelReconcileRehearsal().lifecycle_report()
    states = {entry["state"] for entry in report["events"]}

    assert report["verdict"] == "PASS"
    assert OrderLifecycleState.CREATED_SHADOW.value in states
    assert OrderLifecycleState.SUBMIT_BLOCKED.value in states
    assert OrderLifecycleState.CANCELLED_SIMULATED.value in states
    assert OrderLifecycleState.RECONCILED_SIMULATED.value in states
