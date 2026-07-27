"""Fail-closed KILL cancellation and residual-position reconciliation.

KILL first removes submission authority.  Cancellation is a second, explicit
capability and a broker cancellation response is never treated as a flat
book.  The coordinator re-reads open orders and positions, reports residuals,
and deliberately has no liquidation callback.

No production client is constructed here.  Callers must inject narrowly
scoped list/cancel functions after separately obtaining cancellation
authority; the normal ``stop_session`` path only queues the reconciliation.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

KILL_RECONCILIATION_VERSION = "dummy-kill-reconciliation-v1"
DEFAULT_KILL_RECONCILIATION_PATH = Path(
    "runtime/autonomy/kill_reconciliation.json"
)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    stamped = dict(payload)
    stamped["receipt_sha256"] = hashlib.sha256(
        _canonical_bytes(stamped)
    ).hexdigest()
    return stamped


def _write_atomic(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def queue_kill_reconciliation(
    *,
    kill_asserted_at: str,
    receipt_path: Path | None = DEFAULT_KILL_RECONCILIATION_PATH,
) -> dict[str, Any]:
    """Record that cancel/reconcile remains required; perform no broker I/O."""
    receipt = _stamp(
        {
            "kill_reconciliation_version": KILL_RECONCILIATION_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kill_asserted_at": kill_asserted_at,
            "status": "PENDING_CANCEL_AND_RECONCILE",
            "submission_authority": False,
            "cancel_authority": False,
            "broker_contacted": False,
            "canceled_order_ids": [],
            "open_orders_after": None,
            "residual_positions": None,
            "flat_book_observed": False,
            "liquidation_attempted": False,
            "operator_action": (
                "run the separately authorized central cancellation and "
                "reconciliation procedure"
            ),
        }
    )
    _write_atomic(receipt_path, receipt)
    return receipt


async def _invoke(function: Callable[..., Any], *args: Any) -> Any:
    value = function(*args)
    return await value if inspect.isawaitable(value) else value


def _rows(value: Any, *, key: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} response must be a list")
    return [dict(row) for row in value if isinstance(row, dict)]


def _open_orders(value: Any) -> list[dict[str, Any]]:
    rows = _rows(value, key="orders")
    terminal = {"canceled", "cancelled", "executed", "filled", "expired"}
    return [
        row
        for row in rows
        if str(row.get("status") or "open").strip().lower() not in terminal
    ]


def _positions(value: Any) -> list[dict[str, Any]]:
    rows = _rows(value, key="positions")
    residual: list[dict[str, Any]] = []
    for row in rows:
        raw = (
            row.get("position")
            if row.get("position") is not None
            else row.get("quantity", row.get("count", 0))
        )
        try:
            quantity = int(raw)
        except (TypeError, ValueError):
            # Unparseable position truth is a residual, never silently flat.
            residual.append({**row, "quantity_parse_error": True})
            continue
        if quantity != 0:
            residual.append({**row, "reconciled_quantity": quantity})
    return residual


async def execute_kill_reconciliation(
    *,
    kill_switch_active: bool,
    cancel_authorized: bool,
    list_open_orders: Callable[[], Any],
    cancel_order: Callable[[str], Any],
    list_positions: Callable[[], Any],
    receipt_path: Path | None = DEFAULT_KILL_RECONCILIATION_PATH,
) -> dict[str, Any]:
    """Cancel all observed orders, re-read, and report residual positions.

    This function never liquidates a position and never equates successful
    cancellation with flat exposure.
    """
    generated_at = datetime.now(timezone.utc).isoformat()
    if not kill_switch_active:
        receipt = _stamp(
            {
                "kill_reconciliation_version": KILL_RECONCILIATION_VERSION,
                "generated_at": generated_at,
                "status": "BLOCKED_KILL_SWITCH_NOT_ACTIVE",
                "submission_authority": False,
                "cancel_authority": bool(cancel_authorized),
                "broker_contacted": False,
                "canceled_order_ids": [],
                "open_orders_after": None,
                "residual_positions": None,
                "flat_book_observed": False,
                "liquidation_attempted": False,
            }
        )
        _write_atomic(receipt_path, receipt)
        return receipt
    if not cancel_authorized:
        receipt = _stamp(
            {
                "kill_reconciliation_version": KILL_RECONCILIATION_VERSION,
                "generated_at": generated_at,
                "status": "CANCEL_AUTHORITY_REQUIRED",
                "submission_authority": False,
                "cancel_authority": False,
                "broker_contacted": False,
                "canceled_order_ids": [],
                "open_orders_after": None,
                "residual_positions": None,
                "flat_book_observed": False,
                "liquidation_attempted": False,
            }
        )
        _write_atomic(receipt_path, receipt)
        return receipt

    canceled: list[str] = []
    cancellation_failures: list[dict[str, str]] = []
    broker_contacted = False
    try:
        before = _open_orders(await _invoke(list_open_orders))
        broker_contacted = True
        for order in before:
            order_id = str(order.get("order_id") or order.get("id") or "").strip()
            if not order_id:
                cancellation_failures.append(
                    {"order_id": "", "error": "missing_order_id"}
                )
                continue
            try:
                await _invoke(cancel_order, order_id)
                broker_contacted = True
                canceled.append(order_id)
            except Exception as exc:  # reconciliation must continue after one failure
                cancellation_failures.append(
                    {"order_id": order_id, "error": type(exc).__name__}
                )
        after = _open_orders(await _invoke(list_open_orders))
        residual = _positions(await _invoke(list_positions))
        broker_contacted = True
    except Exception as exc:
        receipt = _stamp(
            {
                "kill_reconciliation_version": KILL_RECONCILIATION_VERSION,
                "generated_at": generated_at,
                "status": "RECONCILIATION_FAILED",
                "error": type(exc).__name__,
                "submission_authority": False,
                "cancel_authority": True,
                "broker_contacted": broker_contacted,
                "canceled_order_ids": sorted(canceled),
                "cancellation_failures": cancellation_failures,
                "open_orders_after": None,
                "residual_positions": None,
                "flat_book_observed": False,
                "liquidation_attempted": False,
            }
        )
        _write_atomic(receipt_path, receipt)
        return receipt

    if after:
        status = "INCOMPLETE_OPEN_ORDERS"
    elif residual:
        status = "CANCELED_RESIDUAL_POSITIONS"
    elif cancellation_failures:
        status = "CANCELLATION_FAILURES_RECONCILED_FLAT"
    else:
        status = "CANCELED_NO_RESIDUAL_POSITIONS"
    receipt = _stamp(
        {
            "kill_reconciliation_version": KILL_RECONCILIATION_VERSION,
            "generated_at": generated_at,
            "status": status,
            "submission_authority": False,
            "cancel_authority": True,
            "broker_contacted": broker_contacted,
            "canceled_order_ids": sorted(canceled),
            "cancellation_failures": cancellation_failures,
            "open_orders_after": after,
            "residual_positions": residual,
            "flat_book_observed": not after and not residual,
            "liquidation_attempted": False,
        }
    )
    _write_atomic(receipt_path, receipt)
    return receipt


__all__ = [
    "DEFAULT_KILL_RECONCILIATION_PATH",
    "KILL_RECONCILIATION_VERSION",
    "execute_kill_reconciliation",
    "queue_kill_reconciliation",
]
