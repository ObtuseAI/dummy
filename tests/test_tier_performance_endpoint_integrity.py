from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autonomy import dashboard
from autonomy.tier_policy import (
    TIER_POLICY_SHA256,
    TIER_POLICY_SPEC,
    TIER_POLICY_VERSION,
)


def _lane(*, realized: bool = False) -> dict[str, object]:
    empty_metric = {
        "n": 0,
        "evidence_status": "COLLECTING_FORWARD_EVIDENCE",
    }
    lane: dict[str, object] = {
        "population": "persisted forward-only evidence",
        "overall": copy.deepcopy(empty_metric),
        "by_tier": {
            tier: copy.deepcopy(empty_metric) for tier in ("A", "B", "C", "WATCH")
        },
        "by_tier_scope": {},
        "by_scope_horizon": {},
        "by_tier_scope_horizon": {},
        "by_tier_scope_market_horizon": {},
    }
    if realized:
        lane["by_book"] = {
            book: {
                "overall": copy.deepcopy(empty_metric),
                "by_tier": {
                    tier: copy.deepcopy(empty_metric)
                    for tier in ("A", "B", "C", "WATCH")
                },
            }
            for book in ("shadow", "live")
        }
    return lane


def _valid_empty_report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "policy_version": TIER_POLICY_VERSION,
        "policy_sha256": TIER_POLICY_SHA256,
        "policy_spec": copy.deepcopy(TIER_POLICY_SPEC),
        "legacy_backfill": False,
        "status": "COLLECTING_FORWARD_EVIDENCE",
        "forecast": _lane(),
        "realized": _lane(realized=True),
        "caveat": "Forward-only tier evidence.",
    }


def _valid_forward_report() -> dict[str, object]:
    report = _valid_empty_report()
    report["status"] = "FORWARD_SAMPLE_AVAILABLE"
    forward_metric = {
        "n": 30,
        "event_clusters": 10,
        "value_side_n": 30,
        "value_side_wins": 18,
        "value_side_hit_rate": 0.6,
        "value_side_hit_rate_descriptive_wilson_ci95": {
            "low": 0.42,
            "high": 0.75,
        },
        "value_side_hit_rate_cluster_ci95": {
            "low": 0.4,
            "high": 0.8,
            "event_clusters": 10,
        },
        "mean_brier": 0.24,
        "mean_log_loss": 0.68,
        "expected_calibration_error": 0.0,
        "maximum_calibration_error": 0.0,
        "calibration_bins": [{
            "range": "0.6-0.7",
            "n": 30,
            "predicted_mean": 0.6,
            "observed_rate": 0.6,
        }],
        "mean_assigned_after_fee_edge": 0.05,
        "evidence_status": "FORWARD_SAMPLE_AVAILABLE",
    }
    forecast = report["forecast"]
    forecast["overall"] = copy.deepcopy(forward_metric)  # type: ignore[index]
    forecast["by_tier"]["A"] = copy.deepcopy(forward_metric)  # type: ignore[index]
    forecast["by_tier_scope"] = {  # type: ignore[index]
        "A|MLB": copy.deepcopy(forward_metric),
    }
    forecast["by_scope_horizon"] = {  # type: ignore[index]
        "MLB|pregame": copy.deepcopy(forward_metric),
    }
    forecast["by_tier_scope_horizon"] = {  # type: ignore[index]
        "A|MLB|pregame": copy.deepcopy(forward_metric),
    }
    forecast["by_tier_scope_market_horizon"] = {  # type: ignore[index]
        "A|MLB|winner|pregame": copy.deepcopy(forward_metric),
    }
    return report


def _write_artifacts(
    runtime_dir: Path,
    *,
    report: object,
    evidence_at: datetime,
) -> None:
    now = datetime.now(timezone.utc)
    snapshot = {
        "generated_at": now.isoformat(),
        "backtest_generated_at": evidence_at.isoformat(),
        "backtest": {} if report is None else {"tier_performance": report},
    }
    (runtime_dir / "latest_dashboard_snapshot.json").write_text(
        json.dumps(snapshot), encoding="utf-8",
    )
    (runtime_dir / "bet_board.json").write_text(
        json.dumps({
            "generated_at": now.isoformat(),
            "rows": 0,
            "groups": {},
            "top": [],
        }),
        encoding="utf-8",
    )


def _client(runtime_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(dashboard, "RUNTIME_DIR", runtime_dir)
    return TestClient(dashboard.build_app())


def test_valid_generated_empty_report_is_collecting_not_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    _write_artifacts(tmp_path, report=_valid_empty_report(), evidence_at=now)

    response = _client(tmp_path, monkeypatch).get("/api/tier-performance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert payload["performance_artifact_status"] == "VALID"
    assert payload["policy_version"] == TIER_POLICY_VERSION
    assert payload["policy_sha256"] == TIER_POLICY_SHA256
    assert payload["policy_spec"] == TIER_POLICY_SPEC
    assert payload["evidence_time_status"] == "FRESH"
    assert payload["evidence_stale"] is False


def test_exact_structured_forward_sample_remains_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _valid_forward_report()
    _write_artifacts(
        tmp_path,
        report=report,
        evidence_at=datetime.now(timezone.utc),
    )

    response = _client(tmp_path, monkeypatch).get("/api/tier-performance")

    assert response.status_code == 200
    assert response.json()["status"] == "FORWARD_SAMPLE_AVAILABLE"
    assert response.json()["performance_artifact_status"] == "VALID"


@pytest.mark.parametrize(
    "case",
    (
        "missing",
        "wrong_policy",
        "wrong_hash",
        "wrong_spec",
        "bad_structure",
        "inflated_forward_status",
        "inflated_forward_lane",
        "inflated_group_lane",
        "schema_bool",
        "policy_numeric_type",
        "empty_metric_payload",
        "cross_tab_key_mismatch",
        "bad_metric_range",
        "object_status",
    ),
)
def test_missing_or_untrusted_performance_evidence_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    report: dict[str, object] | None = _valid_empty_report()
    if case == "missing":
        report = None
    elif case == "wrong_policy":
        report["policy_version"] = "legacy_probability_v1"
    elif case == "wrong_hash":
        report["policy_sha256"] = "0" * 64
    elif case == "wrong_spec":
        report["policy_spec"] = {**TIER_POLICY_SPEC, "a_max_per_scope": 999}
    elif case == "bad_structure":
        report["forecast"].pop("by_tier")  # type: ignore[union-attr]
    elif case == "inflated_forward_status":
        report["status"] = "FORWARD_SAMPLE_AVAILABLE"
    elif case == "inflated_forward_lane":
        report["status"] = "FORWARD_SAMPLE_AVAILABLE"
        report["forecast"]["overall"] = {  # type: ignore[index]
            "n": 0,
            "evidence_status": "FORWARD_SAMPLE_AVAILABLE",
        }
    elif case == "inflated_group_lane":
        report["forecast"]["by_tier"]["A"] = {  # type: ignore[index]
            "n": 30,
            "event_clusters": 10,
            "evidence_status": "FORWARD_SAMPLE_AVAILABLE",
        }
    elif case == "schema_bool":
        report["schema_version"] = True
    elif case == "policy_numeric_type":
        report["policy_spec"]["a_max_per_scope"] = 5.0  # type: ignore[index]
    elif case == "empty_metric_payload":
        report["forecast"]["by_tier"]["A"]["mean_brier"] = -100  # type: ignore[index]
    elif case == "cross_tab_key_mismatch":
        report = _valid_forward_report()
        metric = report["forecast"]["by_tier_scope"].pop("A|MLB")  # type: ignore[index]
        report["forecast"]["by_tier_scope"]["B|MLB"] = metric  # type: ignore[index]
    elif case == "bad_metric_range":
        report = _valid_forward_report()
        report["forecast"]["overall"]["mean_brier"] = -1  # type: ignore[index]
    elif case == "object_status":
        report["status"] = {"forecast": {"A": {"n": 999_999}}}
    _write_artifacts(
        tmp_path,
        report=report,
        evidence_at=datetime.now(timezone.utc),
    )

    response = _client(tmp_path, monkeypatch).get("/api/tier-performance")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "UNAVAILABLE"
    assert payload["performance_artifact_status"] == (
        "MISSING" if case == "missing" else "INVALID"
    )
    assert payload["status"] != "FORWARD_SAMPLE_AVAILABLE"
    assert payload["error"]
    assert "forecast" not in payload
    assert "realized" not in payload
    if case == "object_status":
        assert payload["performance_status"] is None
    if case == "missing":
        assert payload["evidence_generated_at"] is None
        assert payload["evidence_time_status"] == "TIME_UNKNOWN"


def test_evidence_clock_labels_staleness_and_rejects_future_skew(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _valid_empty_report()
    _write_artifacts(
        tmp_path,
        report=report,
        evidence_at=datetime.now(timezone.utc) - timedelta(hours=49),
    )
    client = _client(tmp_path, monkeypatch)

    stale = client.get("/api/tier-performance")

    assert stale.status_code == 200
    assert stale.json()["status"] == "STALE_EVIDENCE"
    assert stale.json()["performance_status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert stale.json()["evidence_time_status"] == "STALE"
    assert stale.json()["evidence_stale"] is True

    _write_artifacts(
        tmp_path,
        report=report,
        evidence_at=datetime.now(timezone.utc) + timedelta(minutes=6),
    )

    future = client.get("/api/tier-performance")

    assert future.status_code == 503
    assert future.json()["status"] == "UNAVAILABLE"
    assert future.json()["performance_status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert future.json()["performance_artifact_status"] == "INVALID"
    assert future.json()["evidence_time_status"] == "FUTURE_SKEW"
    assert future.json()["evidence_future_skew_seconds"] > 300
    assert "forecast" not in future.json()


def test_stale_forward_sample_cannot_keep_forward_ready_top_level_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_artifacts(
        tmp_path,
        report=_valid_forward_report(),
        evidence_at=datetime.now(timezone.utc) - timedelta(hours=49),
    )

    response = _client(tmp_path, monkeypatch).get("/api/tier-performance")

    assert response.status_code == 200
    assert response.json()["status"] == "STALE_EVIDENCE"
    assert response.json()["performance_status"] == "FORWARD_SAMPLE_AVAILABLE"
    assert response.json()["evidence_stale"] is True


def test_tier_evidence_clock_requires_timezone_and_bounds_future_skew() -> None:
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    now_epoch = now.timestamp()

    assert dashboard._tier_evidence_freshness(
        "2026-07-22T12:00:00", now_epoch=now_epoch,
    )["evidence_time_status"] == "TIME_UNKNOWN"
    assert dashboard._tier_evidence_freshness(
        "not-a-time", now_epoch=now_epoch,
    )["evidence_time_status"] == "TIME_UNKNOWN"
    assert dashboard._tier_evidence_freshness(
        (now + timedelta(minutes=5)).isoformat(), now_epoch=now_epoch,
    )["evidence_time_status"] == "FRESH"
    assert dashboard._tier_evidence_freshness(
        (now + timedelta(minutes=5, milliseconds=1)).isoformat(),
        now_epoch=now_epoch,
    )["evidence_time_status"] == "FUTURE_SKEW"


def test_route_never_calls_legacy_board_or_ledger_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autonomy import bet_board

    _write_artifacts(
        tmp_path,
        report=_valid_empty_report(),
        evidence_at=datetime.now(timezone.utc),
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("request route attempted a non-artifact fallback")

    monkeypatch.setattr(bet_board, "assemble_bet_board", forbidden)

    response = _client(tmp_path, monkeypatch).get("/api/tier-performance")

    assert response.status_code == 200
    assert response.json()["performance_artifact_status"] == "VALID"


def test_valid_performance_with_missing_board_is_explicitly_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_artifacts(
        tmp_path,
        report=_valid_empty_report(),
        evidence_at=datetime.now(timezone.utc),
    )
    (tmp_path / "bet_board.json").unlink()

    response = _client(tmp_path, monkeypatch).get("/api/tier-performance")

    assert response.status_code == 503
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["performance_artifact_status"] == "VALID"
    assert response.json()["performance_status"] == "COLLECTING_FORWARD_EVIDENCE"
    assert response.json()["board_artifact_status"] == "MISSING"
