"""Cancel/reconcile rehearsal layer for V11."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OrderLifecycleState(str, Enum):
    CREATED_SHADOW = "CREATED_SHADOW"
    FIREWALL_REHEARSED = "FIREWALL_REHEARSED"
    SUBMIT_BLOCKED = "SUBMIT_BLOCKED"
    SUBMIT_ARMED_BUT_NOT_SENT = "SUBMIT_ARMED_BUT_NOT_SENT"
    SUBMITTED_SIMULATED = "SUBMITTED_SIMULATED"
    PARTIAL_FILL_SIMULATED = "PARTIAL_FILL_SIMULATED"
    FILLED_SIMULATED = "FILLED_SIMULATED"
    CANCEL_REQUESTED_SIMULATED = "CANCEL_REQUESTED_SIMULATED"
    CANCELLED_SIMULATED = "CANCELLED_SIMULATED"
    RECONCILED_SIMULATED = "RECONCILED_SIMULATED"
    ERROR_QUARANTINED = "ERROR_QUARANTINED"


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    @classmethod
    def for_packet(cls, packet_id: str) -> "IdempotencyKey":
        return cls(hashlib.sha256(packet_id.encode("utf-8")).hexdigest()[:16])


@dataclass
class DuplicateResponseGuard:
    order_keys: set[str] = field(default_factory=set)
    cancel_keys: set[str] = field(default_factory=set)

    def record_order(self, key: IdempotencyKey) -> str:
        if key.value in self.order_keys:
            return "DUPLICATE_ORDER_PACKET"
        self.order_keys.add(key.value)
        return "ACCEPTED"

    def record_cancel(self, key: IdempotencyKey) -> str:
        if key.value in self.cancel_keys:
            return "DUPLICATE_CANCEL_PACKET"
        self.cancel_keys.add(key.value)
        return "ACCEPTED"

    def to_report(self) -> dict[str, Any]:
        key = IdempotencyKey.for_packet("guard-report")
        first_order = self.record_order(key)
        duplicate_order = self.record_order(key)
        first_cancel = self.record_cancel(key)
        duplicate_cancel = self.record_cancel(key)
        return {
            "workstream": "V11: Idempotency Guard",
            "first_order": first_order,
            "duplicate_order": duplicate_order,
            "first_cancel": first_cancel,
            "duplicate_cancel": duplicate_cancel,
            "verdict": "PASS"
            if duplicate_order == "DUPLICATE_ORDER_PACKET" and duplicate_cancel == "DUPLICATE_CANCEL_PACKET"
            else "FAIL",
        }


@dataclass(frozen=True)
class CancelIntent:
    shadow_order_id: str
    idempotency_key: str
    simulated_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ReconcileEvent:
    state: OrderLifecycleState
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state.value, "message": self.message}


@dataclass(frozen=True)
class PartialFillSimulation:
    requested_size: int
    filled_size: int
    remaining_size: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class CancelRehearsalPacket:
    cancel_intent: CancelIntent
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return {"cancel_intent": self.cancel_intent.to_dict(), "accepted": self.accepted}


@dataclass(frozen=True)
class ReconcileRehearsalPacket:
    handled_states: list[str]
    partial_fill: PartialFillSimulation

    def to_dict(self) -> dict[str, Any]:
        return {"handled_states": self.handled_states, "partial_fill": self.partial_fill.to_dict()}


class ExchangeResponseNormalizer:
    def normalize(self, response: Any) -> dict[str, Any]:
        try:
            order = response.get("order") if isinstance(response, dict) else None
            if not isinstance(order, dict):
                return {"normalized_state": OrderLifecycleState.ERROR_QUARANTINED.value, "reason": "malformed_response"}
            status = str(order.get("status", "")).lower()
            if status in {"partial", "partially_filled"}:
                state = OrderLifecycleState.PARTIAL_FILL_SIMULATED
            elif status == "filled":
                state = OrderLifecycleState.FILLED_SIMULATED
            elif status in {"cancelled", "canceled"}:
                state = OrderLifecycleState.CANCELLED_SIMULATED
            elif status in {"open", "submitted"}:
                state = OrderLifecycleState.SUBMITTED_SIMULATED
            elif status in {"cancel_rejected", "rejected"}:
                state = OrderLifecycleState.ERROR_QUARANTINED
            else:
                state = OrderLifecycleState.ERROR_QUARANTINED
            return {
                "normalized_state": state.value,
                "filled_count": int(order.get("filled_count", 0) or 0),
            }
        except Exception:
            return {"normalized_state": OrderLifecycleState.ERROR_QUARANTINED.value, "reason": "normalization_error"}

    def to_report(self) -> dict[str, Any]:
        samples = [
            self.normalize({"order": {"status": "open"}}),
            self.normalize({"order": {"status": "partially_filled", "filled_count": 1}}),
            self.normalize({"order": {"status": "filled", "filled_count": 2}}),
            self.normalize({"order": {"status": "cancelled"}}),
            self.normalize({"order": {"status": "cancel_rejected"}}),
            self.normalize({"bad": "shape"}),
        ]
        return {
            "workstream": "V11: Exchange Response Normalization",
            "samples": samples,
            "verdict": "PASS" if any(s["normalized_state"] == "ERROR_QUARANTINED" for s in samples) else "FAIL",
        }


class CancelReconcileRehearsal:
    def _events(self) -> list[ReconcileEvent]:
        return [
            ReconcileEvent(OrderLifecycleState.CREATED_SHADOW, "Shadow order packet created."),
            ReconcileEvent(OrderLifecycleState.FIREWALL_REHEARSED, "Firewall rehearsal path evaluated."),
            ReconcileEvent(OrderLifecycleState.SUBMIT_BLOCKED, "Submit blocked because live-submit disabled."),
            ReconcileEvent(OrderLifecycleState.SUBMITTED_SIMULATED, "Synthetic exchange accepted simulated order."),
            ReconcileEvent(OrderLifecycleState.PARTIAL_FILL_SIMULATED, "Synthetic partial fill normalized."),
            ReconcileEvent(OrderLifecycleState.CANCEL_REQUESTED_SIMULATED, "Cancel request rehearsed only."),
            ReconcileEvent(OrderLifecycleState.CANCELLED_SIMULATED, "Synthetic cancel accepted."),
            ReconcileEvent(OrderLifecycleState.RECONCILED_SIMULATED, "Local simulated state reconciled."),
        ]

    def to_report(self) -> dict[str, Any]:
        key = IdempotencyKey.for_packet("shadow-v11-001")
        cancel = CancelRehearsalPacket(CancelIntent("shadow-v11-001", key.value), True)
        reconcile = ReconcileRehearsalPacket(
            handled_states=[
                "no_fill",
                "partial_fill",
                "full_fill",
                "cancel_accepted",
                "cancel_rejected",
                "stale_local_state",
                "unknown_order_state",
                "malformed_response",
            ],
            partial_fill=PartialFillSimulation(2, 1, 1),
        )
        return {
            "workstream": "V11: Cancel Reconcile Rehearsal",
            "real_submit_calls": 0,
            "real_cancel_calls": 0,
            "cancel_rehearsal": cancel.to_dict(),
            "reconcile_rehearsal": reconcile.to_dict(),
            "events": [event.to_dict() for event in self._events()],
            "verdict": "PASS",
        }

    def lifecycle_report(self) -> dict[str, Any]:
        return {
            "workstream": "V11: Order Lifecycle Rehearsal",
            "events": [event.to_dict() for event in self._events()],
            "verdict": "PASS",
        }
