"""Fail-closed handoff tests for retired operator-proof report workflows."""

from __future__ import annotations

import json

from predator_mesh import operator_proof_workflows as workflows


def _write_report(path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _fixture_only_pass() -> dict[str, object]:
    return {
        "verdict": "PASS",
        "execute_once_final_proof_runner_v7_controller_status": (
            "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
        ),
        "proof_is_real": False,
        "fixture_only": True,
        "uses_non_broker_double": True,
        "non_broker_double_used": True,
        "submitted_autolocked": True,
        "real_broker_contacted": False,
        "real_live_orders_submitted_count": 0,
        "market_order_submitted": False,
        "max_attempts": 1,
    }


def _real_submit_receipt() -> dict[str, object]:
    return {
        "verdict": "PASS",
        "execute_once_final_proof_runner_v7_controller_status": (
            "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
        ),
        "proof_is_real": True,
        "fixture_only": False,
        "uses_non_broker_double": False,
        "non_broker_double_used": False,
        "submitted_autolocked": True,
        "real_broker_contacted": True,
        "real_live_orders_submitted_count": 1,
        "market_order_submitted": False,
        "max_attempts": 1,
        "broker_order_id": "broker-order-1",
        "proof_id": "proof-1",
        "idempotency_key": "a" * 32,
    }


def test_fixture_only_v298_pass_cannot_unlock_downstream_operator_state(
    monkeypatch,
    tmp_path,
) -> None:
    report_path = tmp_path / "final_report_v298.json"
    _write_report(report_path, _fixture_only_pass())
    monkeypatch.setattr(workflows, "V298_FINAL", report_path)

    assert workflows._successful_v298() is False
    assert workflows._staged_proof_kwargs() == {}
    assert workflows._staged_route_kwargs() == {}
    assert workflows._staged_real_proof_kwargs() == {}


def test_real_submit_handoff_requires_every_bound_receipt_field(
    monkeypatch,
    tmp_path,
) -> None:
    report_path = tmp_path / "final_report_v298.json"
    monkeypatch.setattr(workflows, "V298_FINAL", report_path)
    receipt = _real_submit_receipt()

    _write_report(report_path, receipt)
    assert workflows._successful_v298() is True
    # A submission is not a fill, reconciliation, or forensic receipt.
    assert workflows._staged_proof_kwargs() == {}
    assert workflows._staged_route_kwargs() == {}
    assert workflows._staged_real_proof_kwargs() == {
        "real_proof_override": True
    }

    for field in (
        "broker_order_id",
        "proof_id",
        "idempotency_key",
        "real_broker_contacted",
        "proof_is_real",
    ):
        broken = dict(receipt)
        broken[field] = False if field.endswith(("contacted", "real")) else ""
        _write_report(report_path, broken)
        assert workflows._successful_v298() is False, field


def test_boolean_order_count_is_not_accepted_as_one(
    monkeypatch,
    tmp_path,
) -> None:
    report_path = tmp_path / "final_report_v298.json"
    receipt = _real_submit_receipt()
    receipt["real_live_orders_submitted_count"] = True
    _write_report(report_path, receipt)
    monkeypatch.setattr(workflows, "V298_FINAL", report_path)

    assert workflows._successful_v298() is False
