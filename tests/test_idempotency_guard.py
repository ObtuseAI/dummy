from __future__ import annotations

from predator_mesh.v11.reconcile import DuplicateResponseGuard, IdempotencyKey


def test_idempotency_guard_detects_duplicate_order_and_cancel_packets() -> None:
    guard = DuplicateResponseGuard()
    key = IdempotencyKey.for_packet("shadow-order-1")

    assert guard.record_order(key) == "ACCEPTED"
    assert guard.record_order(key) == "DUPLICATE_ORDER_PACKET"
    assert guard.record_cancel(key) == "ACCEPTED"
    assert guard.record_cancel(key) == "DUPLICATE_CANCEL_PACKET"
    assert guard.to_report()["verdict"] == "PASS"
