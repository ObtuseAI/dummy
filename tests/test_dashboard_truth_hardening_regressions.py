"""Regression coverage for fail-closed dashboard truth contracts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from autonomy import bet_board, dashboard
from core import caps_authority


UTC = timezone.utc
NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numeric_timestamps_are_never_fresh(value: float) -> None:
    assert dashboard._to_epoch(value) is None
    age = dashboard._panel_data_age(
        "heartbeat",
        {"last_cycle_at": value},
        NOW.timestamp(),
    )
    assert age["age_seconds"] is None
    assert age["stale"] is True


@pytest.mark.parametrize(
    ("artifact_status", "stale"),
    [("STALE", True), ("INVALID", True), ("UNREADABLE", True)],
)
def test_non_current_boards_never_publish_gate_reason_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    artifact_status: str,
    stale: bool,
) -> None:
    monkeypatch.setattr(
        bet_board,
        "read_current_board_artifact",
        lambda *_args, **_kwargs: {
            "artifact_status": artifact_status,
            "generated_at": (NOW - timedelta(days=2)).isoformat(),
            "stale": stale,
            "groups": {
                "crypto": {
                    "sol": [
                        {
                            "tier_display_bucket": "WATCH",
                            "tier_display_reason": "must_not_escape_stale_artifact",
                        }
                    ]
                }
            },
        },
    )

    result = dashboard._board_edge_quality(
        tmp_path,
        now_epoch=NOW.timestamp(),
    )

    assert result["status"] in {"STALE", "UNAVAILABLE"}
    assert result["gate_reason_counts"] == []


def test_oversized_board_is_refused_before_parser_invocation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "bet_board.json").write_bytes(b"12345")
    monkeypatch.setattr(dashboard, "STATUS_BOARD_MAX_BYTES", 4)

    def fail_if_called(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("oversized board reached the JSON parser")

    monkeypatch.setattr(bet_board, "read_current_board_artifact", fail_if_called)

    result = dashboard._board_edge_quality(
        tmp_path,
        now_epoch=NOW.timestamp(),
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["artifact_status"] == "INVALID"
    assert result["reason"] == "artifact_size_limit_exceeded:bet_board.json"
    assert result["gate_reason_counts"] == []


@pytest.mark.parametrize(
    ("applied_age", "next_due_offset", "stale_field"),
    [
        (timedelta(minutes=5), timedelta(seconds=-1), "next_due_overdue"),
        (timedelta(days=3), timedelta(hours=1), "last_success_stale"),
    ],
)
def test_retention_degrades_on_overdue_or_stale_success_evidence(
    tmp_path: Path,
    applied_age: timedelta,
    next_due_offset: timedelta,
    stale_field: str,
) -> None:
    applied_at = NOW - applied_age
    (tmp_path / "ledger_retention_stdout.log").write_text(
        json.dumps({"at": applied_at.isoformat(), "status": "APPLIED"}) + "\n",
        encoding="utf-8",
    )
    watchdog = {
        "healthy": True,
        "stale_tasks": [],
        "tasks": [
            {
                "task_name": "DummyLedgerRetention",
                "last_status": "APPLIED",
                "last_status_at": applied_at.isoformat(),
                "last_success_at": applied_at.isoformat(),
                "next_due_at": (NOW + next_due_offset).isoformat(),
                "cadence_seconds": 86_400,
                "threshold_seconds": 172_800,
                "stale": False,
            }
        ],
    }

    result = dashboard._retention_status(
        tmp_path,
        watchdog=watchdog,
        now_epoch=NOW.timestamp(),
    )

    assert result["status"] == "DEGRADED"
    assert result[stale_field] is True
    if stale_field == "next_due_overdue":
        assert result["next_due_status"] == "OVERDUE"


@pytest.mark.parametrize(
    "watchdog",
    [
        {"healthy": False, "stale_tasks": []},
        {"stale_tasks": []},
        {"healthy": True, "stale_tasks": ["DummyLedgerRetention"]},
        {"healthy": True},
    ],
)
def test_system_health_never_ignores_unhealthy_or_incomplete_watchdog(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    watchdog: dict[str, Any],
) -> None:
    monkeypatch.setattr(
        dashboard,
        "_ledger_health_status",
        lambda *_args, **_kwargs: {
            "status": "AVAILABLE",
            "over_threshold": False,
            "growth": {"status": "AVAILABLE"},
        },
    )
    monkeypatch.setattr(
        dashboard,
        "_retention_status",
        lambda *_args, **_kwargs: {
            "status": "AVAILABLE",
            "next_due_status": "AVAILABLE",
        },
    )
    monkeypatch.setattr(
        dashboard,
        "_sqlite_contention_status",
        lambda **_kwargs: {"status": "AVAILABLE"},
    )
    monkeypatch.setattr(
        dashboard,
        "_cycle_deadline_status",
        lambda *_args, **_kwargs: {
            "status": "AVAILABLE",
            "deadline_count": 0,
        },
    )
    monkeypatch.setattr(
        dashboard,
        "_promotion_run_status",
        lambda *_args, **_kwargs: {"status": "AVAILABLE"},
    )

    result = dashboard._system_health_status(
        tmp_path,
        heartbeat={},
        watchdog=watchdog,
        cycles=[],
        malformed_cycles=0,
        promotion={},
        now_epoch=NOW.timestamp(),
    )

    assert result["status"] == "DEGRADED"
    assert result["watchdog"]["status"] == "DEGRADED"


def test_canonical_caps_are_verified_but_never_grant_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dashboard, "CAPS_CONFIG_PATH", caps_authority.CAPS_PATH)

    result = dashboard._caps_evidence_status()

    assert result["status"] == "AVAILABLE"
    assert result["config_integrity_valid"] is True
    assert result["exact_series_allowed"] is True
    assert result["matched_series"] == "KXSOL15M"
    assert result["execution_authority"] is False


def test_tampered_caps_cannot_manufacture_series_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tampered = tmp_path / "caps.json"
    tampered.write_text(
        json.dumps(
            {
                "schema_version": caps_authority.CURRENT_CAPS_SCHEMA_VERSION,
                "authority_epoch": caps_authority.CURRENT_CAPS_AUTHORITY_EPOCH,
                "authority_registration_required": True,
                "allowed_series": ["KXSOL15M"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "CAPS_CONFIG_PATH", tampered)

    result = dashboard._caps_evidence_status()

    assert result["status"] == "INVALID"
    assert result["config_integrity_valid"] is False
    assert result["exact_series_allowed"] is False
    assert result["matched_series"] is None
    assert result["execution_authority"] is False
    assert "CAPS_PROTECTED_HASH_MISMATCH" in result["errors"]


def test_use_sidecar_refuses_unbounded_outcome_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(dashboard, "STATUS_TAIL_MAX_BYTES", 32)
    (tmp_path / "use_predictions.json").write_text("{}", encoding="utf-8")
    (tmp_path / "use_outcomes.jsonl").write_bytes(b"x" * 33)

    unavailable = dashboard._use_sidecar_summary(tmp_path)

    assert unavailable["outcomes_on_tape"] is None
    assert unavailable["outcomes_status"] == "UNAVAILABLE"
    assert unavailable["outcomes_unavailable_reason"] == "size_limit_exceeded"
    assert unavailable["bounded_read_limit_bytes"] == 32

    (tmp_path / "use_outcomes.jsonl").write_text(
        '{"outcome":1}\n{"outcome":2}\n',
        encoding="utf-8",
    )
    available = dashboard._use_sidecar_summary(tmp_path)
    assert available["outcomes_on_tape"] == 2
    assert available["outcomes_status"] == "AVAILABLE"
    assert available["outcomes_unavailable_reason"] is None
