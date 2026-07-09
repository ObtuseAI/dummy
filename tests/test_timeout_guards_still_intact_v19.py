from __future__ import annotations


def test_timeout_guards_still_intact_v19() -> None:
    from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController
    from predator_mesh.v19.runtime import V19RuntimeBudget

    assert RealReadOnlySourceActivationController.max_request_timeout_s <= 10
    assert V19RuntimeBudget().pytest_timeout_seconds == 60
