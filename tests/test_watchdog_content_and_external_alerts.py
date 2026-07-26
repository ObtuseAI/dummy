"""Fail-closed coverage for unattended job content and external alerts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import autonomy.alerts as alerts
from autonomy.watchdog import (
    DEFAULT_TASKS,
    RESEARCH_STALL_SECONDS,
    evaluate_watchdog,
    fire_watchdog_alerts,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
NOW_EPOCH = NOW.timestamp()


def _wire_alert_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(alerts, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(alerts, "ALERTS_LOG", tmp_path / "alerts.jsonl")
    monkeypatch.setattr(alerts, "ALERTS_LATEST", tmp_path / "alerts_latest.json")
    monkeypatch.setattr(alerts, "ALERT_STATE", tmp_path / "alert_state.json")


def _retention_spec():
    return next(
        spec for spec in DEFAULT_TASKS
        if spec.name == "DummyLedgerRetention"
    )


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True)
    return runtime


def _write_retention_log(runtime: Path, *records: dict[str, object]) -> None:
    text = "\n".join(json.dumps(record, sort_keys=True) for record in records)
    (runtime / "ledger_retention_stdout.log").write_text(
        text + "\n",
        encoding="utf-8",
    )


def _external_environment(endpoint: str = "https://notify.example.test/hook") -> dict[str, str]:
    return {
        alerts.CRITICAL_ALERTS_ENABLED_ENV: "1",
        alerts.CRITICAL_ALERT_WEBHOOK_URL_ENV: endpoint,
        alerts.CRITICAL_ALERT_ALLOWED_HOSTS_ENV: "notify.example.test",
    }


def test_external_critical_delivery_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _wire_alert_paths(monkeypatch, tmp_path)
    calls: list[object] = []

    record = alerts.emit_alert(
        "SELF_STOP",
        "halted",
        external_transport=lambda *args: calls.append(args) or 204,
        environ={},
    )

    assert calls == []
    assert record["external_delivery"] == {"status": "DISABLED"}
    persisted = json.loads((tmp_path / "alerts_latest.json").read_text("utf-8"))
    assert persisted["external_delivery"] == {"status": "DISABLED"}


def test_external_delivery_ignores_noncritical_alerts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _wire_alert_paths(monkeypatch, tmp_path)
    calls: list[object] = []

    record = alerts.emit_alert(
        "WATCHDOG_CYCLE_ERROR_STREAK",
        "three errors",
        external_transport=lambda *args: calls.append(args) or 204,
        environ=_external_environment(),
    )

    assert calls == []
    assert record["external_delivery"] == {"status": "NOT_CRITICAL"}


@pytest.mark.parametrize(
    ("endpoint", "allowlist", "reason"),
    [
        (
            "http://notify.example.test/hook",
            "notify.example.test",
            "https_required",
        ),
        (
            "https://other.example.test/hook",
            "notify.example.test",
            "host_not_allowlisted",
        ),
        (
            "https://127.0.0.1/hook",
            "127.0.0.1",
            "non_public_endpoint_forbidden",
        ),
        (
            "https://notify.example.test:8443/hook",
            "notify.example.test",
            "nonstandard_port_forbidden",
        ),
    ],
)
def test_external_delivery_refuses_unsafe_endpoints_without_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: str,
    allowlist: str,
    reason: str,
) -> None:
    _wire_alert_paths(monkeypatch, tmp_path)
    calls: list[object] = []
    environment = _external_environment(endpoint)
    environment[alerts.CRITICAL_ALERT_ALLOWED_HOSTS_ENV] = allowlist

    record = alerts.emit_alert(
        "WATCHDOG_TASK_STALE",
        "stale",
        external_transport=lambda *args: calls.append(args) or 204,
        environ=environment,
    )

    assert calls == []
    assert record["external_delivery"] == {
        "status": "REFUSED",
        "reason": reason,
    }


def test_external_critical_delivery_sends_minimal_redacted_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _wire_alert_paths(monkeypatch, tmp_path)
    endpoint = (
        "https://notify.example.test/operator?"
        "token=must-never-enter-local-alert-record"
    )
    captured: dict[str, object] = {}

    def fake_transport(
        target: str,
        payload: dict[str, str],
        timeout_seconds: float,
    ) -> int:
        captured.update({
            "target": target,
            "payload": payload,
            "timeout_seconds": timeout_seconds,
        })
        return 204

    record = alerts.emit_alert(
        "RESEARCH_STALL",
        " cohort alpha \n has stalled ",
        detail={"private_local_context": "not for external delivery"},
        now_iso="2026-07-26T12:00:00+00:00",
        external_transport=fake_transport,
        environ=_external_environment(endpoint),
    )

    assert record["external_delivery"] == {"status": "DELIVERED"}
    assert captured["target"] == endpoint
    assert captured["payload"] == {
        "kind": "RESEARCH_STALL",
        "severity": "critical",
        "message": "cohort alpha has stalled",
        "at": "2026-07-26T12:00:00+00:00",
    }
    serialized = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8")
    assert "must-never-enter-local-alert-record" not in serialized
    assert endpoint not in serialized


def test_external_transport_failure_is_local_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _wire_alert_paths(monkeypatch, tmp_path)
    endpoint = "https://notify.example.test/hook?token=private-value"

    def failing_transport(*_args) -> int:
        raise RuntimeError(endpoint)

    record = alerts.emit_alert(
        "SELF_STOP",
        "halted",
        external_transport=failing_transport,
        environ=_external_environment(endpoint),
    )

    assert record["external_delivery"] == {
        "status": "FAILED",
        "reason": "transport_error:RuntimeError",
    }
    serialized = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8")
    assert endpoint not in serialized
    assert "private-value" not in serialized


def test_local_alert_receipts_redact_known_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _wire_alert_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("DUMMY_ALERT_TEST_TOKEN", "operator-secret-value")

    record = alerts.emit_alert(
        "SELF_STOP",
        "halted with operator-secret-value",
        detail={
            "api_key": "literal-api-key",
            "context": "operator-secret-value",
        },
        environ={},
    )

    serialized = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8")
    assert "operator-secret-value" not in serialized
    assert "literal-api-key" not in serialized
    assert record["message"] == "halted with ***REDACTED***"
    assert record["detail"]["api_key"] == "***REDACTED***"


def test_retention_watchdog_tracks_last_applied_not_log_mtime(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    applied_at = NOW - timedelta(minutes=5)
    _write_retention_log(
        runtime,
        {"status": "APPLIED", "generated_at": applied_at.isoformat()},
    )

    status = evaluate_watchdog(
        runtime,
        now_epoch=NOW_EPOCH,
        tasks=[_retention_spec()],
        inventory=[],
    )
    row = status["tasks"][0]

    assert status["healthy"] is True
    assert row["stale"] is False
    assert row["last_status"] == "APPLIED"
    assert row["last_success_at"] == applied_at.isoformat()
    assert row["last_success_age_seconds"] == 300.0
    assert row["timestamp_source"] == "content:last_success.generated_at"


def test_latest_retention_refusal_degrades_health_and_alerts_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    alert_dir = tmp_path / "alerts"
    _wire_alert_paths(monkeypatch, alert_dir)
    applied_at = NOW - timedelta(hours=2)
    _write_retention_log(
        runtime,
        {"status": "APPLIED", "generated_at": applied_at.isoformat()},
        {
            "status": "REFUSED",
            "generated_at": (NOW - timedelta(minutes=1)).isoformat(),
            "error": "database is locked",
        },
    )

    status = evaluate_watchdog(
        runtime,
        now_epoch=NOW_EPOCH,
        tasks=[_retention_spec()],
        inventory=[],
    )
    row = status["tasks"][0]

    assert status["healthy"] is False
    assert status["stale_tasks"] == ["DummyLedgerRetention"]
    assert row["last_status"] == "REFUSED"
    assert row["content_failure"] is True
    assert row["last_success_at"] == applied_at.isoformat()

    state_path = runtime / "watchdog_state.json"
    first = fire_watchdog_alerts(
        status,
        now_iso=NOW.isoformat(),
        state_path=state_path,
    )
    second = fire_watchdog_alerts(
        status,
        now_iso=(NOW + timedelta(minutes=1)).isoformat(),
        state_path=state_path,
    )
    assert [item["kind"] for item in first] == ["WATCHDOG_JOB_REFUSED"]
    assert first[0]["severity"] == "critical"
    assert second == []


def test_retention_content_contract_never_falls_back_to_fresh_mtime(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    (runtime / "ledger_retention_stdout.log").write_text(
        "Traceback: maintenance crashed\n"
        f"diagnostic only: {json.dumps({'status': 'APPLIED', 'generated_at': NOW.isoformat()})}\n",
        encoding="utf-8",
    )

    status = evaluate_watchdog(
        runtime,
        now_epoch=NOW_EPOCH,
        tasks=[_retention_spec()],
        inventory=[],
    )
    row = status["tasks"][0]

    assert status["healthy"] is False
    assert row["timestamp_source"] == "content:no_structured_status"
    assert row["content_error"] == "no_structured_status"
    assert row["age_seconds"] is None


def test_retention_cli_stamps_refused_terminal_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import run_dummy_ledger_retention

    monkeypatch.delenv("DUMMY_MAINTENANCE_BACKUP_MANIFEST", raising=False)
    exit_code = run_dummy_ledger_retention.main([
        "--db",
        str(tmp_path / "ledger.db"),
        "--apply",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "REFUSED"
    generated_at = datetime.fromisoformat(payload["generated_at"])
    assert generated_at.tzinfo is not None


def _write_research_candidate(
    runtime: Path,
    *,
    cohort: str,
    started_at: datetime,
    issued_at: datetime | None = None,
    observation_registry_id: str = "registry-1",
) -> None:
    cohort_dir = runtime / "autoresearch" / "cohorts" / cohort
    cohort_dir.mkdir(parents=True)
    (cohort_dir / "forward_registry.json").write_text(
        json.dumps({
            "registry_id": "registry-1",
            "status": "ACTIVE_FORWARD_PAPER_OBSERVATION",
            "active_candidate": {
                "epoch_started_at": started_at.isoformat(),
            },
        }),
        encoding="utf-8",
    )
    if issued_at is not None:
        (cohort_dir / "forward_observations.jsonl").write_text(
            json.dumps({
                "sequence": 0,
                "payload": {
                    "registry_id": observation_registry_id,
                    "issued_at": issued_at.isoformat(),
                },
            }) + "\n",
            encoding="utf-8",
        )


def test_active_candidate_without_48h_issuance_fires_research_stall(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    _wire_alert_paths(monkeypatch, tmp_path / "alerts")
    _write_research_candidate(
        runtime,
        cohort="cohort-a",
        started_at=NOW - timedelta(seconds=RESEARCH_STALL_SECONDS + 1),
    )

    status = evaluate_watchdog(
        runtime,
        now_epoch=NOW_EPOCH,
        tasks=[],
        inventory=[],
    )

    assert status["healthy"] is False
    assert status["research_stalls"] == ["cohort-a"]
    candidate = status["research_progress"]["stalled_candidates"][0]
    assert candidate["zero_forward_issuance"] is True
    assert candidate["reason"] == "no_forward_issuance_within_threshold"

    state_path = runtime / "watchdog_state.json"
    first = fire_watchdog_alerts(
        status,
        now_iso=NOW.isoformat(),
        state_path=state_path,
    )
    second = fire_watchdog_alerts(
        status,
        now_iso=NOW.isoformat(),
        state_path=state_path,
    )
    assert [item["kind"] for item in first] == ["RESEARCH_STALL"]
    assert second == []


def test_recent_matching_forward_issuance_keeps_research_healthy(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    _write_research_candidate(
        runtime,
        cohort="cohort-b",
        started_at=NOW - timedelta(days=7),
        issued_at=NOW - timedelta(hours=2),
    )

    status = evaluate_watchdog(
        runtime,
        now_epoch=NOW_EPOCH,
        tasks=[],
        inventory=[],
    )

    assert status["healthy"] is True
    assert status["research_stalls"] == []
    candidate = status["research_progress"]["candidates"][0]
    assert candidate["zero_forward_issuance"] is False
    assert candidate["progress_age_seconds"] == 7200.0


def test_observation_from_old_registry_does_not_clear_research_stall(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    _write_research_candidate(
        runtime,
        cohort="cohort-c",
        started_at=NOW - timedelta(days=3),
        issued_at=NOW - timedelta(minutes=1),
        observation_registry_id="retired-registry",
    )

    status = evaluate_watchdog(
        runtime,
        now_epoch=NOW_EPOCH,
        tasks=[],
        inventory=[],
    )
    candidate = status["research_progress"]["stalled_candidates"][0]

    assert status["healthy"] is False
    assert candidate["matching_observations_in_tail"] == 0
    assert candidate["zero_forward_issuance"] is True
