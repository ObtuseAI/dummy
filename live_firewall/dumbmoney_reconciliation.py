"""Restart-safe read-only reconciliation orchestration for DumbMoney Dummy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from live_firewall.dumbmoney_capital import CapitalEnvelopeAdapter
from live_firewall.exposure_tracker import ExposureTracker


class SignedReconciliationReader(Protocol):
    def terminal_reconciliation_witness(
        self,
        reservation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None: ...

    def settlement_reconciliation_witness(
        self,
        position_exposure: Mapping[str, Any],
    ) -> Mapping[str, Any] | None: ...


class DumbMoneyKalshiReconciliationSweeper:
    """Resolve prior dispatches before allowing another execution cycle."""

    def __init__(
        self,
        *,
        capital_adapter: CapitalEnvelopeAdapter,
        broker_reader: SignedReconciliationReader,
        exposure_tracker: ExposureTracker,
    ) -> None:
        self._capital_adapter = capital_adapter
        self._broker_reader = broker_reader
        self._exposure_tracker = exposure_tracker

    def run_once(self) -> dict[str, Any]:
        broker_contacted = False
        terminal_witnesses = 0
        settlement_witnesses = 0
        unresolved_reservations = 0
        unresolved_positions = 0

        reservations = (
            self._capital_adapter.pending_reconciliation_reservations()
        )
        for reservation in reservations:
            if reservation.get("dispatch_claimed") is not True:
                unresolved_reservations += 1
                continue
            broker_contacted = True
            wrapper = self._broker_reader.terminal_reconciliation_witness(
                reservation
            )
            if wrapper is None:
                unresolved_reservations += 1
                continue
            witness = (
                self._capital_adapter
                .verify_terminal_reconciliation_witness(wrapper)
            )
            terminal_state = (
                "filled"
                if witness["terminal_status"] == "executed"
                else "canceled"
            )
            if not self._exposure_tracker.record_cumulative_fill(
                str(witness["proposal_id"]),
                int(witness["fill_count"]),
                witness["average_fill_price_cents"],
                terminal_state=terminal_state,
                reconciliation_id=str(witness["witness_id"]),
            ):
                raise RuntimeError(
                    "local terminal exposure projection failed closed"
                )
            self._capital_adapter.record_signed_terminal_reconciliation(
                wrapper
            )
            terminal_witnesses += 1

        positions = self._capital_adapter.active_position_exposures()
        for position in positions:
            broker_contacted = True
            wrapper = self._broker_reader.settlement_reconciliation_witness(
                position
            )
            if wrapper is None:
                unresolved_positions += 1
                continue
            witness = (
                self._capital_adapter
                .verify_settlement_reconciliation_witness(wrapper)
            )
            if not self._exposure_tracker.record_position_close(
                str(witness["contract_ticker"]),
                str(witness["side"]),
                reconciliation_id=str(witness["witness_id"]),
            ):
                raise RuntimeError(
                    "local settlement projection failed closed"
                )
            self._capital_adapter.record_signed_settlement_reconciliation(
                wrapper
            )
            settlement_witnesses += 1

        blocked = bool(
            unresolved_reservations or unresolved_positions
        )
        return {
            "schema": "dummy.kalshi-reconciliation-sweep.v1",
            "status": "BLOCKED" if blocked else "COMPLETE",
            "broker_contacted": broker_contacted,
            "reservations_scanned": len(reservations),
            "terminal_witnesses_recorded": terminal_witnesses,
            "positions_scanned": len(positions),
            "settlement_witnesses_recorded": settlement_witnesses,
            "unresolved_reservations": unresolved_reservations,
            "unresolved_positions": unresolved_positions,
        }


__all__ = [
    "DumbMoneyKalshiReconciliationSweeper",
    "SignedReconciliationReader",
]
