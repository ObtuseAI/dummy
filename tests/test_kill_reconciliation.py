from __future__ import annotations

import json

import pytest

from autonomy.kill_reconciliation import execute_kill_reconciliation


@pytest.mark.asyncio
async def test_kill_cancels_then_rereads_and_reports_residual_positions(tmp_path):
    reads = 0
    canceled: list[str] = []

    async def list_orders():
        nonlocal reads
        reads += 1
        if reads == 1:
            return {"orders": [{"order_id": "o-1", "status": "resting"}]}
        return {"orders": []}

    async def cancel(order_id):
        canceled.append(order_id)
        return {"status": "canceled"}

    async def positions():
        return {
            "positions": [
                {"ticker": "KXTEST", "position": 2},
                {"ticker": "KXFLAT", "position": 0},
            ]
        }

    path = tmp_path / "kill.json"
    receipt = await execute_kill_reconciliation(
        kill_switch_active=True,
        cancel_authorized=True,
        list_open_orders=list_orders,
        cancel_order=cancel,
        list_positions=positions,
        receipt_path=path,
    )
    assert canceled == ["o-1"]
    assert reads == 2
    assert receipt["status"] == "CANCELED_RESIDUAL_POSITIONS"
    assert receipt["flat_book_observed"] is False
    assert receipt["residual_positions"][0]["reconciled_quantity"] == 2
    assert receipt["liquidation_attempted"] is False
    assert json.loads(path.read_text(encoding="utf-8")) == receipt


@pytest.mark.asyncio
async def test_kill_without_separate_cancel_authority_contacts_nothing():
    calls: list[str] = []

    async def no_call(*_args):
        calls.append("called")
        return []

    receipt = await execute_kill_reconciliation(
        kill_switch_active=True,
        cancel_authorized=False,
        list_open_orders=no_call,
        cancel_order=no_call,
        list_positions=no_call,
        receipt_path=None,
    )
    assert receipt["status"] == "CANCEL_AUTHORITY_REQUIRED"
    assert receipt["broker_contacted"] is False
    assert receipt["flat_book_observed"] is False
    assert calls == []


def test_stop_session_queues_reconciliation_without_claiming_flat(tmp_path, monkeypatch):
    import autonomy.session as session

    kill_path = tmp_path / "KILL"
    session_path = tmp_path / "session.json"
    session_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(session, "KILL_PATH", kill_path)
    receipt_path = tmp_path / "reconciliation.json"

    result = session.stop_session(
        session_path,
        kill_reconciliation_path=receipt_path,
    )
    assert result["stopped"] is True
    assert kill_path.exists()
    assert not session_path.exists()
    assert result["kill_reconciliation"]["status"] == (
        "PENDING_CANCEL_AND_RECONCILE"
    )
    assert result["flat_book_observed"] is False
    assert result["liquidation_attempted"] is False
