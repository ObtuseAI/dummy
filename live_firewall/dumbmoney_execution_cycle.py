"""Sealed execution-cycle boundary with no order-submission capability."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from live_firewall.dumbmoney_capital import CapitalEnvelopeAdapter
from live_firewall.dumbmoney_command_feed import CoreCommandFeedConsumer


EXECUTION_CYCLE_SCHEMA = "dummy.dumbmoney-execution-cycle.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BROKER_TRUTH_FIELDS = {
    "schema",
    "venue",
    "account_hash",
    "subaccount_number",
    "observed_at",
    "broker_snapshot_sha256",
    "flat_book_observed",
    "total_exposure_cents",
    "open_order_count",
    "market_exposure_cents",
    "correlated_exposure_cents",
    "unresolved_open_orders",
    "unresolved_positions",
}


class SealedDisabledExecutionCycle:
    """Exercise the execution boundary without owning a broker write sink.

    This object deliberately accepts no broker client, signing key, or callback.
    It proves the production service is wired through the exact execution-cycle
    interface while remaining structurally unable to submit an order.
    """

    submission_capable = False
    deployment_gate = "ATTENDED_LIVE_CANARY_REQUIRED"

    def __call__(
        self,
        *,
        capital_adapter: CapitalEnvelopeAdapter,
        command_feed: CoreCommandFeedConsumer,
        broker_snapshot: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del capital_adapter, command_feed
        if (
            not isinstance(broker_snapshot, Mapping)
            or set(broker_snapshot) != _BROKER_TRUTH_FIELDS
            or broker_snapshot.get("schema")
            != "dummy.kalshi-broker-truth.v1"
        ):
            raise ValueError("broker truth snapshot fields mismatch")
        digest = broker_snapshot.get("broker_snapshot_sha256")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise ValueError("broker truth snapshot digest is invalid")
        return {
            "schema": EXECUTION_CYCLE_SCHEMA,
            "status": "BLOCKED",
            "broker_contacted": False,
            "orders_submitted": 0,
            "broker_snapshot_sha256": digest,
        }


__all__ = [
    "EXECUTION_CYCLE_SCHEMA",
    "SealedDisabledExecutionCycle",
]
