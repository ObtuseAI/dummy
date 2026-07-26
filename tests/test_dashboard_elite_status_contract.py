"""Fail-closed contracts for launch-plan System Health and Edge Quality.

Every artifact in this module is synthetic and isolated under ``tmp_path``.
The tests deliberately deny SQLite and the live ``D:\\DummyRuntime`` tree so
the fast dashboard snapshot cannot accidentally turn a status poll into a
ledger query.
"""

from __future__ import annotations

import json
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from autonomy import dashboard
from core import caps_authority


UTC = timezone.utc
KXSOL_SCOPE = "crypto_patience_confirm|sol|15m_direction|15m"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any] | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        row if isinstance(row, str) else json.dumps(row, separators=(",", ":"))
        for row in rows
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cycle_rows() -> tuple[list[dict[str, Any] | str], str, str]:
    """Return 45 valid rows plus three malformed rows in the final-40 scan."""
    base = datetime(2026, 1, 1, tzinfo=UTC)
    deadline_indexes = {0, 1, 5, 15, 25, 35}
    locked_indexes = {10, 20}
    malformed_after = {8, 24, 43}
    rows: list[dict[str, Any] | str] = []
    timestamps: list[str] = []

    for index in range(45):
        at = (base + timedelta(minutes=index)).isoformat()
        timestamps.append(at)
        status = "CYCLE_OK"
        error = None
        if index in deadline_indexes:
            status = "CYCLE_ERROR:CycleDeadline"
            error = "cycle exceeded bounded deadline"
        elif index in locked_indexes:
            status = "CYCLE_ERROR:OperationalError"
            error = "database is locked"
        rows.append({"at": at, "status": status, "error": error})
        if index in malformed_after:
            rows.append("{malformed")

    # The bounded window must ignore indexes 0-4 and retain valid indexes 5-44.
    return rows, timestamps[5], timestamps[44]


def _install_isolated_artifacts(runtime_dir: Path, caps_path: Path) -> None:
    sampled_at = "2026-01-01T01:00:00+00:00"
    _write_json(
        runtime_dir / "heartbeat.json",
        {
            "alive": True,
            "last_cycle_at": sampled_at,
            "last_success_at": sampled_at,
            "last_status": "CYCLE_OK",
            "ledger_health": {
                "exists": True,
                "size_bytes": 4096,
                "size_gib": 4096 / (1024**3),
                "journal_mode": "wal",
                "freelist_count": 0,
                "freelist_bytes": 0,
                "bloat_warn": True,
                "bloat_warn_bytes": 3000,
                "probe_error": None,
            },
        },
    )
    # Metadata may be sampled, but the content of either SQLite file is denied.
    (runtime_dir / "ledger.db").write_bytes(b"d" * 4096)
    (runtime_dir / "ledger.db-wal").write_bytes(b"w" * 128)

    retention_rows: list[dict[str, Any] | str] = [
        {
            "at": "2026-01-01T00:00:00+00:00",
            "status": "APPLIED",
            "lock_retries": 2,
        },
        # An APPLIED label without a timestamp is not last-success evidence.
        {"status": "APPLIED", "lock_retries": 0},
        {
            "at": "2026-01-02T00:00:00+00:00",
            "status": "REFUSED",
            "lock_retries": 4,
            "error": "database is locked",
        },
    ]
    _write_jsonl(runtime_dir / "ledger_retention_stdout.log", retention_rows)

    cycle_rows, _, _ = _cycle_rows()
    _write_jsonl(runtime_dir / "cycles.jsonl", cycle_rows)

    _write_json(
        runtime_dir / "auto_promotion_state.json",
        {
            "report_name": "AUTO_PROMOTION",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "OK",
            "live_trading_authority": "OPERATOR_ONLY_UNAFFECTED",
            # Malicious/legacy authority claims and arbitrary details must not
            # pass through the sanitized summary.
            "execution_authority": True,
            "private_debug_token": "must-not-leak",
            "scopes_evaluated": ["scope-a", "scope-b"],
            "eligible_scopes": ["scope-a"],
            "promoted": [{"scope": "scope-a", "reason": "fixture"}],
            "declined": [{"scope": "scope-b", "reason": "fixture"}],
            "human_review_candidates": [{"scope": "scope-a"}],
        },
    )

    # These two attractive rows are deliberately not bound to a validated
    # board/policy snapshot. They must never manufacture edge or actionability.
    _write_json(
        runtime_dir / "bet_board.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "rows": 2,
            "groups": {
                "sol": {
                    "market": [
                        {
                            "ticker": "KXSOL15M-FIXTURE-A",
                            "tier": "A",
                            "tier_display_bucket": "A",
                            "after_fee_edge": 0.99,
                            "tier_after_fee_edge": 0.99,
                        },
                        {
                            "ticker": "KXSOL15M-FIXTURE-B",
                            "tier": "B",
                            "tier_display_bucket": "B",
                            "after_fee_edge": 0.50,
                            "tier_after_fee_edge": 0.50,
                        },
                    ]
                }
            },
            "top": [],
            "tier_distribution": {
                "counts": {"A": 1, "B": 1, "C": 0, "WATCH": 0},
                "percentages": {"A": 0.5, "B": 0.5, "C": 0.0, "WATCH": 0.0},
            },
        },
    )

    _write_json(
        runtime_dir / "no_edge_map.json",
        {
            "report_name": "NO_EDGE_MAP",
            "generated_at": datetime.now(UTC).isoformat(),
            "min_clusters": 40,
            "counts": {
                "edge": 1,
                "insufficient_evidence": 0,
                "no_demonstrated_edge": 0,
                "significantly_negative": 0,
            },
            "edge": [
                {
                    "scope": KXSOL_SCOPE,
                    "clusters": 99,
                    "edge_mean": 0.040902,
                    "ci_lower": 0.01307,
                    "ci_upper": 0.069225,
                }
            ],
            "insufficient_evidence_scopes": [],
            "no_demonstrated_edge": [],
            "significantly_negative": [],
        },
    )
    _write_json(
        caps_path,
        {
            "allowed_markets": [],
            "allowed_series": ["KXSOL15M"],
            "limit_orders_only": True,
            "allow_market_orders": False,
        },
    )

    _write_json(
        runtime_dir / "execution_tournament.json",
        {
            "report_name": "EXECUTION_POLICY_TOURNAMENT",
            "generated_at": "2000-01-01T00:00:00+00:00",
            "actionable_settled_decisions": 20,
            "actionable_event_clusters": 10,
            "policy_switch_authority": {"auto_switch": False},
            "cohorts": [
                {
                    "policy": {
                        "cohort": "C0",
                        "label": "maker-only control",
                        "mode": "maker",
                    },
                    "fills": 2,
                    "fill_event_clusters": 2,
                    "fill_rate": 0.1,
                    "net_pnl_cents": -5,
                    "mean_pnl_cents": -2.5,
                    "fill_conditioned_brier_edge_vs_market": -0.02,
                    "evidence_class": "observed_incumbent_fill_replay",
                    "output_authority": "control_measurement_only",
                    "witnessed_broker_fill_backing": False,
                    "counts_toward_policy_switch": False,
                    "counts_toward_promotion_readiness": False,
                    "promotion_review_eligible": False,
                },
                {
                    "policy": {
                        "cohort": "C1",
                        "label": "taker-only",
                        "mode": "taker",
                    },
                    "fills": 10,
                    "fill_event_clusters": 8,
                    "fill_rate": 0.5,
                    "net_pnl_cents": 15,
                    "mean_pnl_cents": 1.5,
                    "fill_conditioned_brier_edge_vs_market": 0.01,
                    "evidence_class": "modeled_counterfactual",
                    "output_authority": (
                        "research_only_not_execution_or_promotion_proof"
                    ),
                    "witnessed_broker_fill_backing": False,
                    "counts_toward_policy_switch": False,
                    "counts_toward_promotion_readiness": False,
                    "promotion_review_eligible": False,
                },
            ],
            "headline": {
                "leading_cohort": None,
                "evidence_sufficient_for_promotion_review": False,
                "evidence_sufficient_for_policy_switch": False,
            },
            "ranking": [],
        },
    )


@pytest.fixture
def elite_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    runtime_dir = tmp_path / "runtime" / "autonomy"
    runtime_dir.mkdir(parents=True)
    caps_path = tmp_path / "configs" / "caps.json"
    _install_isolated_artifacts(runtime_dir, caps_path)

    monkeypatch.setattr(
        dashboard,
        "_dashboard_watchdog_status",
        lambda *_args, **_kwargs: {
            "healthy": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "ledger_size_gb": 0.000004096,
            "ledger_size_gib": 4096 / (1024**3),
            "ledger_size_units": "decimal_gb_bytes_over_1e9",
            "ledger_max_gb": 0.000003,
            "ledger_over_threshold": True,
            "tasks": [],
            "stale_tasks": [],
        },
    )
    monkeypatch.setattr(
        dashboard,
        "_live_controls_status",
        lambda: {
            "state": "default_disabled",
            "execution_authority": False,
            "blocker": "DEFAULT_DISABLED",
            "broker_contacted": False,
        },
    )
    monkeypatch.setattr(
        dashboard,
        "session_authorization_state",
        lambda _runtime_dir: {
            "status": "INACTIVE",
            "authorized": False,
            "expired": True,
        },
    )
    monkeypatch.setattr(
        dashboard,
        "_live_account_status",
        lambda _runtime_dir: {
            "status": "UNAVAILABLE",
            "execution_authority": False,
            "broker_contacted_by_dashboard": False,
        },
    )
    monkeypatch.setattr(dashboard, "_switches_summary", lambda: {})
    # The backend contract intentionally exposes this injectable config path.
    monkeypatch.setattr(dashboard, "CAPS_CONFIG_PATH", caps_path)
    monkeypatch.setattr(
        caps_authority,
        "evaluate_caps_authority",
        lambda **_kwargs: caps_authority.CapsAuthorityStatus(
            state=caps_authority.STATE_REVIEW_REQUIRED,
            current_caps_sha256=caps_authority.PROTECTED_CAPS_SHA256,
            protected_caps_sha256=caps_authority.PROTECTED_CAPS_SHA256,
            schema_version=caps_authority.CURRENT_CAPS_SCHEMA_VERSION,
            authority_epoch=caps_authority.CURRENT_CAPS_AUTHORITY_EPOCH,
            config_integrity_valid=True,
            authority_registration_required=True,
            authority_registration_present=False,
            authority_registration_valid=False,
            authority_registration_sha256=None,
            legacy_authority_invalidated=True,
            errors=("CAPS_AUTHORITY_REGISTRATION_MISSING",),
            execution_authority=False,
        ),
    )

    original_path_open = Path.open

    def guarded_path_open(path: Path, *args: Any, **kwargs: Any):
        path_text = str(path).casefold()
        if path.name.casefold() in {"ledger.db", "ledger.db-wal", "ledger.db-shm"}:
            raise AssertionError("dashboard status attempted to open SQLite content")
        if path_text.startswith("d:\\dummyruntime\\"):
            raise AssertionError("test attempted to read the live runtime tree")
        return original_path_open(path, *args, **kwargs)

    def deny_sqlite(*_args: Any, **_kwargs: Any):
        raise AssertionError("dashboard status attempted sqlite3.connect")

    def deny_network(*_args: Any, **_kwargs: Any):
        raise AssertionError("dashboard status attempted a network connection")

    monkeypatch.setattr(Path, "open", guarded_path_open)
    monkeypatch.setattr(sqlite3, "connect", deny_sqlite)
    monkeypatch.setattr(socket, "create_connection", deny_network)

    return dashboard.assemble_status_snapshot(runtime_dir)


def test_system_health_is_bounded_and_accounts_for_malformed_cycles(
    elite_snapshot: dict[str, Any],
) -> None:
    health = elite_snapshot["system_health"]
    cycles = health["cycle_deadlines"]
    _, expected_start, expected_end = _cycle_rows()

    assert health["schema_version"] == 1
    assert health["authority"] == {"execution": False, "promotion": False}
    assert cycles["status"] == "AVAILABLE"
    assert cycles["source"] == "cycles.jsonl"
    assert cycles["window_kind"] == "last_valid_records"
    assert cycles["tail_limit"] == 40
    assert cycles["records_considered"] == 40
    assert cycles["malformed_records"] == 3
    assert cycles["deadline_count"] == 4
    assert cycles["rate"] == pytest.approx(0.1)
    assert cycles["window_start"] == expected_start
    assert cycles["window_end"] == expected_end
    assert elite_snapshot["ledger_touched"] is False


def test_system_health_separates_retention_truth_and_sqlite_terminal_failures(
    elite_snapshot: dict[str, Any],
) -> None:
    health = elite_snapshot["system_health"]
    ledger = health["ledger"]
    retention = health["retention"]
    contention = health["sqlite_contention"]

    assert ledger["source"] == "heartbeat.ledger_health"
    assert ledger["size_bytes"] == 4096
    assert ledger["wal_size_bytes"] == 128
    assert ledger["threshold_bytes"] == 3000
    assert ledger["over_threshold"] is True
    assert ledger["growth"]["status"] == "UNAVAILABLE"
    assert ledger["growth"]["sample_count"] == 1
    assert ledger["growth"]["bytes_per_hour"] is None

    assert retention["last_run_status"] == "REFUSED"
    assert retention["last_run_at"] == "2026-01-02T00:00:00+00:00"
    assert retention["last_success_at"] == "2026-01-01T00:00:00+00:00"
    assert retention["next_due_at"] is None
    assert retention["next_due_status"] == "UNAVAILABLE"
    assert retention["records_considered"] == 3
    assert retention["lock_retries_last_run"] == 4

    assert contention["retry_events"] is None
    assert contention["retry_events_status"] == "UNAVAILABLE"
    assert contention["terminal_failure_count"] == 2
    assert contention["wal_checkpoint_busy"] is None
    assert contention["records_considered"] == 40


def test_promotion_status_is_count_only_and_never_grants_authority(
    elite_snapshot: dict[str, Any],
) -> None:
    promotion = elite_snapshot["system_health"]["promotion_run"]

    assert promotion["run_status"] == "OK"
    assert promotion["scopes_evaluated"] == 2
    assert promotion["eligible_scopes"] == 1
    assert promotion["promoted_count"] == 1
    assert promotion["declined_count"] == 1
    assert promotion["human_review_candidate_count"] == 1
    assert promotion["live_trading_authority"] == "OPERATOR_ONLY_UNAFFECTED"
    assert promotion["execution_authority"] is False
    assert "must-not-leak" not in json.dumps(promotion)
    assert "private_debug_token" not in promotion


def test_invalid_unbound_board_cannot_manufacture_edge_or_actionability(
    elite_snapshot: dict[str, Any],
) -> None:
    edge = elite_snapshot["edge_quality"]
    board = edge["current_board"]

    assert edge["schema_version"] == 1
    assert edge["authority"] == {"execution": False, "promotion": False}
    assert board["total_rows"] >= 0
    assert board["validated_rows"] == 0
    assert board["excluded_rows"] >= 0
    assert board["after_fee_edge"]["status"] == "UNAVAILABLE"
    assert board["after_fee_edge"]["sample_count"] == 0
    assert board["after_fee_edge"]["min"] is None
    assert board["after_fee_edge"]["p50"] is None
    assert board["after_fee_edge"]["p90"] is None
    assert board["after_fee_edge"]["max"] is None
    assert board["after_fee_edge"]["mean"] is None
    assert board["actionable_share"]["status"] == "UNAVAILABLE"
    assert board["actionable_share"]["value"] is None
    assert board["actionable_share"]["execution_authority"] is False
    assert board["gate_reason_counts"] == []


def test_kxsol_scope_caps_and_statistics_are_distinct_non_authority_panes(
    elite_snapshot: dict[str, Any],
) -> None:
    kxsol = elite_snapshot["edge_quality"]["kxsol15m"]
    mapping = kxsol["scope_mapping"]
    statistics = kxsol["statistical_evidence"]
    caps = kxsol["caps_evidence"]
    live = kxsol["live_authority"]

    assert kxsol["series"] == "KXSOL15M"
    assert mapping["status"] == "EXACT_TAXONOMY"
    assert mapping["scope"] == KXSOL_SCOPE
    assert statistics["classification"] == "edge"
    assert statistics["clusters"] == 99
    assert statistics["edge_mean"] == pytest.approx(0.040902)
    assert statistics["ci_lower"] == pytest.approx(0.01307)
    assert statistics["ci_upper"] == pytest.approx(0.069225)
    assert statistics["execution_authority"] is False
    assert caps["exact_series_allowed"] is True
    assert caps["matched_series"] == "KXSOL15M"
    assert caps["execution_authority"] is False
    assert live["state"] == "default_disabled"
    assert live["execution_authority"] is False
    assert live["session_status"] == "INACTIVE"
    assert live["session_expired"] is True
    assert kxsol["execution_authority"] is False


def test_maker_taker_comparison_is_stale_audit_only_evidence(
    elite_snapshot: dict[str, Any],
) -> None:
    comparison = elite_snapshot["edge_quality"]["execution_comparison"]
    maker = comparison["maker"]
    taker = comparison["taker"]

    assert comparison["generated_at"] == "2000-01-01T00:00:00+00:00"
    assert comparison["stale"] is True
    assert comparison["audit_only"] is True
    assert comparison["policy_switch_authority"] is False
    assert maker["cohort"] == "C0"
    assert maker["mode"] == "maker"
    assert maker["fills"] == 2
    assert maker["fill_event_clusters"] == 2
    assert maker["brier_edge_vs_market"] == pytest.approx(-0.02)
    assert taker["cohort"] == "C1"
    assert taker["mode"] == "taker"
    assert taker["fills"] == 10
    assert taker["fill_event_clusters"] == 8
    assert taker["brier_edge_vs_market"] == pytest.approx(0.01)
    assert taker["evidence_class"] == "modeled_counterfactual"
    assert taker["witnessed_broker_fill_backing"] is False
    assert taker["counts_toward_promotion_readiness"] is False
    assert taker["promotion_review_eligible"] is False
