"""Dashboard contracts for the authoritative sports seed health lane."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from autonomy.dashboard import (
    MISPRICING_MONITOR_AUTHORITY,
    SPORTS_BOARD_REFRESH_TASK_NAME,
    SPORTS_MODEL_SEED_STATUS_FILE,
    SPORTS_MODEL_SEED_TASK_NAME,
    assemble_dashboard_state,
    assemble_status_snapshot,
)


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _iso_age(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def test_full_dashboard_names_authoritative_sports_tasks_and_legacy_monitor(
    tmp_path,
):
    seed_status = {
        "status": "REFRESH_OK",
        "last_success_at": _iso_age(60),
        "last_success_run_id": "seed-run-1",
        "execution_authority": False,
    }
    _write_json(tmp_path / SPORTS_MODEL_SEED_STATUS_FILE, seed_status)

    state = assemble_dashboard_state(runtime_dir=tmp_path)
    fleet = {row["task_name"]: row for row in state["scheduler_fleet"]}

    assert fleet[SPORTS_MODEL_SEED_TASK_NAME]["role"] == (
        "authoritative sports model seed"
    )
    assert fleet[SPORTS_BOARD_REFRESH_TASK_NAME]["role"] == (
        "authoritative sports quote board"
    )
    assert fleet["DummyMispricingMonitor"]["role"] == (
        "legacy mispricing research (non-authoritative)"
    )
    assert fleet["DummyShadowPredator"]["role"] == (
        "retired shadow research (non-authoritative)"
    )
    assert fleet["DummyShadowPredator"]["can_gate_live"] is False
    assert fleet["DummyCryptoPaperTwin"]["role"] == (
        "retired crypto paper research (non-authoritative)"
    )
    assert fleet["DummyCryptoPaperTwin"]["can_gate_live"] is False
    assert fleet["DummySportsSimulation"]["role"] == (
        "sports research simulation (non-authoritative)"
    )
    assert fleet["DummySportsSimulation"]["can_gate_sports_grades"] is False
    assert state["mispricing_monitor_authority"] == MISPRICING_MONITOR_AUTHORITY
    assert state["sports_model_seed"] == seed_status
    assert state["data_ages"]["sports_model_seed"]["at"] == (
        seed_status["last_success_at"]
    )
    assert state["data_ages"]["sports_model_seed"]["threshold_seconds"] == 600
    assert state["data_ages"]["sports_model_seed"]["stale"] is False


def test_fast_snapshot_uses_last_success_not_latest_attempt_for_seed_freshness(
    tmp_path,
):
    seed_status = {
        "status": "REFRESH_FAILED",
        "updated_at": _iso_age(1),
        "last_success_at": _iso_age(601),
        "last_success_run_id": "old-success",
        "execution_authority": False,
    }
    _write_json(tmp_path / SPORTS_MODEL_SEED_STATUS_FILE, seed_status)

    snapshot = assemble_status_snapshot(runtime_dir=tmp_path)

    assert snapshot["sports_model_seed"] == seed_status
    assert snapshot["data_ages"]["sports_model_seed"]["stale"] is True
    assert snapshot["data_ages"]["sports_model_seed"]["age_seconds"] >= 600
    assert snapshot["mispricing_monitor_authority"]["can_gate_sports_grades"] is False
    assert snapshot["mispricing_monitor_authority"]["can_gate_live"] is False


def test_fresh_persisted_watchdog_is_used_without_recompute(tmp_path, monkeypatch):
    _write_json(
        tmp_path / "watchdog_status.json",
        {
            "generated_at": _iso_age(60),
            "healthy": True,
            "tasks": [
                {"task_name": SPORTS_MODEL_SEED_TASK_NAME},
                {"task_name": SPORTS_BOARD_REFRESH_TASK_NAME},
            ],
            "stale_tasks": [],
        },
    )

    def unexpected_recompute(**_kwargs):
        raise AssertionError("fresh watchdog status must not be recomputed")

    monkeypatch.setattr(
        "autonomy.watchdog.evaluate_watchdog", unexpected_recompute
    )
    snapshot = assemble_status_snapshot(runtime_dir=tmp_path)

    assert snapshot["watchdog"]["source"] == "persisted_watchdog_status"
    assert snapshot["watchdog"]["persisted_status_stale"] is False
    assert snapshot["watchdog"]["healthy"] is True


def test_fresh_old_schema_watchdog_without_authoritative_lanes_is_recomputed(
    tmp_path, monkeypatch
):
    _write_json(
        tmp_path / "watchdog_status.json",
        {
            "generated_at": _iso_age(10),
            "healthy": True,
            "tasks": [{"task_name": "DummyMispricingMonitor"}],
            "stale_tasks": [],
        },
    )
    calls = []

    def evaluate(**kwargs):
        calls.append(kwargs)
        return {
            "generated_at": datetime.fromtimestamp(
                kwargs["now_epoch"], tz=timezone.utc
            ).isoformat(),
            "healthy": False,
            "tasks": [
                {"task_name": SPORTS_MODEL_SEED_TASK_NAME, "stale": True},
                {"task_name": SPORTS_BOARD_REFRESH_TASK_NAME, "stale": True},
            ],
            "stale_tasks": [
                SPORTS_MODEL_SEED_TASK_NAME,
                SPORTS_BOARD_REFRESH_TASK_NAME,
            ],
        }

    monkeypatch.setattr("autonomy.watchdog.evaluate_watchdog", evaluate)
    snapshot = assemble_status_snapshot(runtime_dir=tmp_path)

    assert len(calls) == 1
    assert snapshot["watchdog"]["source"] == "live_read_only_recompute"
    assert snapshot["watchdog"]["healthy"] is False
    assert snapshot["watchdog"]["persisted_status_stale"] is True


def test_stale_watchdog_is_recomputed_read_only(tmp_path, monkeypatch):
    _write_json(
        tmp_path / "watchdog_status.json",
        {
            "generated_at": _iso_age(601),
            "healthy": True,
            "tasks": [],
            "stale_tasks": [],
        },
    )
    calls = []

    def evaluate(**kwargs):
        calls.append(kwargs)
        return {
            "generated_at": datetime.fromtimestamp(
                kwargs["now_epoch"], tz=timezone.utc
            ).isoformat(),
            "healthy": False,
            "tasks": [{"task_name": SPORTS_MODEL_SEED_TASK_NAME, "stale": True}],
            "stale_tasks": [SPORTS_MODEL_SEED_TASK_NAME],
        }

    monkeypatch.setattr("autonomy.watchdog.evaluate_watchdog", evaluate)
    before = (tmp_path / "watchdog_status.json").read_bytes()
    snapshot = assemble_status_snapshot(runtime_dir=tmp_path)

    assert len(calls) == 1
    assert calls[0]["runtime_dir"] == tmp_path
    assert snapshot["watchdog"]["source"] == "live_read_only_recompute"
    assert snapshot["watchdog"]["read_only_recompute"] is True
    assert snapshot["watchdog"]["persisted_status_stale"] is True
    assert snapshot["watchdog"]["healthy"] is False
    assert snapshot["watchdog"]["stale_tasks"] == [SPORTS_MODEL_SEED_TASK_NAME]
    assert (tmp_path / "watchdog_status.json").read_bytes() == before


def test_failed_watchdog_recompute_reports_unhealthy_fail_closed(
    tmp_path, monkeypatch
):
    def fail(**_kwargs):
        raise RuntimeError("diagnostic failure")

    monkeypatch.setattr("autonomy.watchdog.evaluate_watchdog", fail)
    snapshot = assemble_status_snapshot(runtime_dir=tmp_path)
    watchdog = snapshot["watchdog"]

    assert watchdog["source"] == "live_read_only_recompute"
    assert watchdog["status"] == "RECOMPUTE_FAILED_CLOSED"
    assert watchdog["healthy"] is False
    assert watchdog["stale_tasks"] == ["WATCHDOG_HEALTH_UNAVAILABLE"]
    assert watchdog["error_type"] == "RuntimeError"
