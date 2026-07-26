"""Contract tests for the read-only four-axis readiness report."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.run_dummy_elite_validation import evaluate_readiness


NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)


def _write(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stamp(delta: timedelta = timedelta()) -> str:
    return (NOW - delta).isoformat()


def _write_passing_inputs(root: Path) -> None:
    _write(root, "configs/live_submit.json", {"enabled": False})
    _write(
        root,
        "runtime/autonomy/heartbeat.json",
        {
            "alive": True,
            "last_cycle_at": _stamp(timedelta(minutes=3)),
            "last_success_at": _stamp(timedelta(minutes=3)),
            "last_status": "COMPLETED",
        },
    )
    _write(
        root,
        "runtime/autonomy/watchdog_status.json",
        {
            "generated_at": _stamp(timedelta(minutes=2)),
            "healthy": True,
            "stale_tasks": [],
            "uncovered_failing_tasks": [],
            "kill_file_present": False,
            "ledger_over_threshold": False,
            "disk_below_floor": False,
        },
    )
    _write(
        root,
        "runtime/autonomy/autoresearch_status.json",
        {
            "status": "OK",
            "last_success_at": _stamp(timedelta(minutes=10)),
            "highest_supported_level": 0,
            "forward_settlements": 0,
            "orders_placed": False,
            "execution_authority": False,
            "capital_authority": False,
            "automatic_promotion": False,
        },
    )
    _write(
        root,
        "runtime/autonomy/autoresearch/intelligence_lab/observatory_report.json",
        {
            "cycle_observed_at": _stamp(timedelta(hours=1)),
            "highest_supported_level": 0,
            "claims": {
                "recursive_self_improvement_supported": False,
            },
            "orders_placed": False,
            "execution_authority": False,
            "capital_authority": False,
            "automatic_positive_promotion": False,
        },
    )
    _write(
        root,
        "runtime/autonomy/autoresearch/intelligence_lab/research_control_plane_report.json",
        {
            "schema_version": 1,
            "generated_at": _stamp(timedelta(minutes=5)),
            "status": "COMPLETE",
            "queue_id": "queue-1",
            "protocols_seen": 1,
            "runs_created": 1,
            "runs_reused": 0,
            "verdict_counts": {"REJECTED": 1},
            "journal_tip": "abc123",
            "negative_controls_passed": True,
            "execution_authority": False,
            "capital_authority": False,
            "automatic_promotion": False,
            "source_edits_applied": False,
            "orders_placed": False,
        },
    )
    _write(
        root,
        "runtime/autonomy/live_canary_readiness.json",
        {
            "schema_version": 1,
            "generated_at": _stamp(timedelta(hours=1)),
            "status": "PASS",
            "ready": True,
            "execution_authority": False,
            "capital_authority": False,
            "evidence": {
                "independent_realized_post_fee_clusters": 40,
                "grading_coverage": 0.95,
                "post_fee_edge_ci_lower": 0.001,
                "scope_bounded": True,
            },
        },
    )
    _write(
        root,
        "runtime/autonomy/live_scale_readiness.json",
        {
            "schema_version": 1,
            "generated_at": _stamp(timedelta(hours=1)),
            "status": "PASS",
            "ready": True,
            "execution_authority": False,
            "capital_authority": False,
            "evidence": {
                "operational_green_days": 14,
                "restore_drill_verified": True,
                "scheduler_soak_passed": True,
                "maker_taker_policy_decided": True,
                "verified_shadow_fills": True,
                "money_gate_mutation_tests_passed": True,
                "operator_demo_place_cancel_verified": True,
                "kill_reconciliation_verified": True,
            },
        },
    )


def test_missing_inputs_block_each_axis_without_granting_authority(tmp_path: Path) -> None:
    report = evaluate_readiness(tmp_path, now=NOW)

    assert report["status"] == "BLOCKED"
    assert all(axis["status"] == "BLOCKED" for axis in report["axes"].values())
    assert report["execution_authority"] is False
    assert report["capital_authority"] is False
    assert report["orders_placed"] is False
    assert report["broker_contacted"] is False
    assert report["runtime_mutated"] is False


def test_all_axes_can_pass_only_for_separate_operator_review(tmp_path: Path) -> None:
    _write_passing_inputs(tmp_path)

    report = evaluate_readiness(tmp_path, now=NOW)

    assert report["status"] == "READY_FOR_SEPARATE_OPERATOR_AUTHORITY_REVIEW"
    assert report["ready_for_separate_operator_authority_review"] is True
    assert all(axis["ready"] is True for axis in report["axes"].values())
    assert report["authority"]["state"] == "DEFAULT_DISABLED"
    assert report["execution_authority"] is False
    assert report["authority"]["execution_authority"] is False


def test_stale_success_blocks_only_its_dependent_axes(tmp_path: Path) -> None:
    _write_passing_inputs(tmp_path)
    path = tmp_path / "runtime/autonomy/heartbeat.json"
    heartbeat = json.loads(path.read_text(encoding="utf-8"))
    heartbeat["last_cycle_at"] = _stamp(timedelta(hours=2))
    heartbeat["last_success_at"] = _stamp(timedelta(hours=2))
    path.write_text(json.dumps(heartbeat), encoding="utf-8")

    report = evaluate_readiness(tmp_path, now=NOW)

    assert report["axes"]["operations"]["status"] == "BLOCKED"
    assert report["axes"]["research"]["status"] == "PASS"
    assert report["axes"]["canary"]["status"] == "PASS"
    assert report["axes"]["scale"]["status"] == "PASS"
    assert report["status"] == "BLOCKED"


def test_retired_dashboard_canary_cannot_substitute_for_forward_evidence(
    tmp_path: Path,
) -> None:
    _write_passing_inputs(tmp_path)
    (tmp_path / "runtime/autonomy/live_canary_readiness.json").unlink()
    _write(
        tmp_path,
        "runtime/autonomy/latest_dashboard_snapshot.json",
        {
            "generated_at": _stamp(),
            "canary": {
                "status": "RETIRED_NON_AUTHORITATIVE",
                "historical_research_ready": True,
            },
            "paper_evidence_audit": {"canary": {"ready": True}},
        },
    )

    report = evaluate_readiness(tmp_path, now=NOW)

    assert report["axes"]["canary"]["status"] == "BLOCKED"
    assert report["axes"]["canary"]["paper_or_shadow_canary_can_substitute"] is False
    assert report["axes"]["scale"]["status"] == "BLOCKED"


def test_positive_readiness_evidence_never_validates_an_enabled_live_config(
    tmp_path: Path,
) -> None:
    _write_passing_inputs(tmp_path)
    _write(
        tmp_path,
        "configs/live_submit.json",
        {
            "enabled": True,
            "explicit_acknowledgement": "not evaluated by this reader",
        },
    )

    report = evaluate_readiness(tmp_path, now=NOW)

    assert all(axis["ready"] is True for axis in report["axes"].values())
    assert report["status"] == "BLOCKED"
    assert (
        report["authority"]["state"]
        == "SEPARATE_AUTHORITY_EVALUATION_REQUIRED"
    )
    assert report["execution_authority"] is False


def test_future_dated_evidence_fails_closed(tmp_path: Path) -> None:
    _write_passing_inputs(tmp_path)
    path = tmp_path / "runtime/autonomy/live_canary_readiness.json"
    canary = json.loads(path.read_text(encoding="utf-8"))
    canary["generated_at"] = (NOW + timedelta(hours=1)).isoformat()
    path.write_text(json.dumps(canary), encoding="utf-8")

    report = evaluate_readiness(tmp_path, now=NOW)

    assert report["axes"]["canary"]["status"] == "BLOCKED"
    assert any(
        "future_dated" in blocker
        for blocker in report["axes"]["canary"]["blockers"]
    )


def test_malformed_nested_evidence_blocks_instead_of_crashing(tmp_path: Path) -> None:
    _write_passing_inputs(tmp_path)
    control_path = (
        tmp_path
        / "runtime/autonomy/autoresearch/intelligence_lab/research_control_plane_report.json"
    )
    control = json.loads(control_path.read_text(encoding="utf-8"))
    control["verdict_counts"] = ["not", "an", "object"]
    control_path.write_text(json.dumps(control), encoding="utf-8")

    report = evaluate_readiness(tmp_path, now=NOW)

    assert report["axes"]["research"]["status"] == "BLOCKED"
    assert any(
        "verdict_counts_not_an_object" in blocker
        for blocker in report["axes"]["research"]["blockers"]
    )
