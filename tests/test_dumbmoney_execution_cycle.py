from __future__ import annotations

import hashlib

import pytest

from live_firewall.dumbmoney_execution_cycle import (
    SealedDisabledExecutionCycle,
)


def _snapshot() -> dict:
    return {
        "schema": "dummy.kalshi-broker-truth.v1",
        "venue": "dummy_kalshi",
        "account_hash": hashlib.sha256(b"account").hexdigest(),
        "subaccount_number": 0,
        "observed_at": "2026-07-26T22:00:00Z",
        "broker_snapshot_sha256": hashlib.sha256(b"snapshot").hexdigest(),
        "flat_book_observed": True,
        "total_exposure_cents": 0,
        "open_order_count": 0,
        "market_exposure_cents": {},
        "correlated_exposure_cents": {},
        "unresolved_open_orders": 0,
        "unresolved_positions": 0,
    }


def test_sealed_cycle_is_snapshot_bound_and_has_no_submission_surface() -> None:
    cycle = SealedDisabledExecutionCycle()
    snapshot = _snapshot()

    result = cycle(
        capital_adapter=object(),  # type: ignore[arg-type]
        command_feed=object(),  # type: ignore[arg-type]
        broker_snapshot=snapshot,
    )

    assert result == {
        "schema": "dummy.dumbmoney-execution-cycle.v1",
        "status": "BLOCKED",
        "broker_contacted": False,
        "orders_submitted": 0,
        "broker_snapshot_sha256": snapshot["broker_snapshot_sha256"],
    }
    assert cycle.submission_capable is False
    assert not hasattr(cycle, "broker")
    assert not hasattr(cycle, "submit")


def test_sealed_cycle_rejects_non_exact_or_unbound_snapshot() -> None:
    cycle = SealedDisabledExecutionCycle()
    extra = {**_snapshot(), "unexpected": True}
    with pytest.raises(ValueError, match="fields mismatch"):
        cycle(
            capital_adapter=object(),  # type: ignore[arg-type]
            command_feed=object(),  # type: ignore[arg-type]
            broker_snapshot=extra,
        )

    malformed = {**_snapshot(), "broker_snapshot_sha256": "not-a-digest"}
    with pytest.raises(ValueError, match="digest is invalid"):
        cycle(
            capital_adapter=object(),  # type: ignore[arg-type]
            command_feed=object(),  # type: ignore[arg-type]
            broker_snapshot=malformed,
        )
