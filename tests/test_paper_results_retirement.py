"""Authority and UI contract for retired paper/shadow results."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import (
    LiveBrokerFirewall,
    live_execution_authority_status,
)


def test_default_disabled_live_controls_remain_fail_closed(monkeypatch):
    import live_firewall.firewall as firewall_module

    monkeypatch.setattr(
        firewall_module,
        "_load_live_submit_config",
        lambda: {"enabled": False},
    )
    monkeypatch.setattr(firewall_module, "_command_seal_ready", lambda: True)
    monkeypatch.setattr(firewall_module, "_caps_strict", lambda: True)
    monkeypatch.setattr(firewall_module, "_descriptor_staged", lambda: True)
    monkeypatch.setattr(firewall_module, "_credential_resolver_ready", lambda: True)
    monkeypatch.setattr(firewall_module, "_proof_lock_clear", lambda: True)

    status = live_execution_authority_status()

    assert status["state"] == "default_disabled"
    assert status["execution_authority"] is False
    assert status["blocker"] == "DEFAULT_DISABLED"
    assert status["central_firewall_required"] is True
    assert status["limit_orders_only"] is True
    assert status["market_orders_allowed"] is False
    assert status["paper_results_authority"] == "RETIRED_NON_AUTHORITATIVE"
    assert status["paper_results_can_enable_live"] is False
    assert status["paper_results_can_block_live"] is False
    assert status["broker_contacted"] is False


def test_retired_canary_compatibility_flag_cannot_change_firewall(monkeypatch):
    import autonomy.canary as canary

    monkeypatch.setattr(
        canary,
        "evaluate_canary_readiness",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("paper evidence was read")
        ),
    )
    firewall = LiveBrokerFirewall(
        None,
        ExposureTracker(),
        require_canary_readiness=True,
    )

    verdict = firewall._canary_readiness_verdict(required=True)

    assert verdict.allow is True
    assert "retired" in verdict.reason.lower()


def test_legacy_overview_fields_are_stripped_at_artifact_boundary():
    from autonomy.dashboard_snapshot import sanitize_primary_overview

    result = sanitize_primary_overview({
        "paper": True,
        "bankroll_cents": 1,
        "realized_pnl_cents": 9_999,
        "realized_trade_statistics": {"roi_on_entry_cost": 100.0},
        "promoted": [{"name": "paper-winner", "execution_authority": True}],
        "close_to_promotion": [{"name": "paper-loser"}],
        "active_sources": [{"source": "forecast", "weight": 1.0}],
    })

    assert result["active_sources"] == [{"source": "forecast", "weight": 1.0}]
    assert result["paper_results_status"] == "RETIRED_NON_AUTHORITATIVE"
    assert result["paper_results_can_enable_live"] is False
    assert result["paper_results_can_block_live"] is False
    for retired in (
        "paper",
        "bankroll_cents",
        "realized_pnl_cents",
        "realized_trade_statistics",
        "promoted",
        "close_to_promotion",
    ):
        assert retired not in result


def test_live_brain_does_not_install_paper_performance_quarantine():
    source = Path("autonomy/session.py").read_text(encoding="utf-8")

    assert "performance_guard=(None if live else PerformanceGuard())" in source


def test_temporary_session_start_never_clears_production_kill(
    tmp_path,
    monkeypatch,
):
    import autonomy.session as session
    from autonomy.ontology import SessionMode

    global_kill = tmp_path / "production" / "KILL"
    global_kill.parent.mkdir(parents=True)
    global_kill.write_text("maintenance", encoding="utf-8")
    monkeypatch.setattr(session, "KILL_PATH", global_kill)

    result = session.start_session(
        SessionMode.SHADOW,
        session_path=tmp_path / "hermetic" / "session.json",
    )

    assert result["started"] is True
    assert global_kill.read_text(encoding="utf-8") == "maintenance"


def test_redirected_default_session_alias_never_clears_production_kill(
    tmp_path,
    monkeypatch,
):
    """Omitting session_path is not production authority by itself."""
    import autonomy.session as session
    from autonomy.ontology import SessionMode

    redirected_session = tmp_path / "alternate-runtime" / "session.json"
    global_kill = tmp_path / "production-runtime" / "KILL"
    global_kill.parent.mkdir(parents=True)
    global_kill.write_text("operator stop", encoding="utf-8")
    monkeypatch.setattr(session, "SESSION_PATH", redirected_session)
    monkeypatch.setattr(session, "KILL_PATH", global_kill)

    result = session.start_session(SessionMode.SHADOW)

    assert result["started"] is True
    assert redirected_session.exists()
    assert global_kill.read_text(encoding="utf-8") == "operator stop"


def test_session_target_identity_uses_resolved_path():
    import autonomy.session as session

    repository_root = Path(session.__file__).resolve().parents[1]
    equivalent = (
        repository_root
        / "runtime"
        / "alternate"
        / ".."
        / "autonomy"
        / "session.json"
    )

    assert session._is_real_production_session_target(equivalent) is True
    assert session._is_real_production_session_target(
        repository_root / "runtime" / "autonomy" / "session-test.json"
    ) is False


def test_legacy_autonomy_paper_fields_are_namespaced_without_mutating_source():
    from autonomy.dashboard import sanitize_autonomy_response

    legacy = {
        "heartbeat": {"alive": True},
        "realized_shadow_pnl_cents": -4_200,
        "auto_promotion": {"promoted": ["paper-winner"]},
        "paper_operation": {"paper_bankroll_cents": 9_000},
        "bankroll_curve": [{"bankroll": 9_000}],
        "canary": {"ready": True},
        "ledger": {"realized_pnl_cents": -4_200},
        "crypto_paper_twin": {"paper_mode": "SIMULATION"},
        "sports_operation": {"paper_mode": "SIMULATION"},
        "scheduler_fleet": [
            {"role": "crypto paper twin", "healthy": True},
            {"role": "dashboard", "healthy": True},
        ],
        "data_ages": {
            "heartbeat": {"stale": False},
            "crypto_paper_twin": {"stale": False},
        },
    }
    sanitized = sanitize_autonomy_response(legacy)

    for field in (
        "realized_shadow_pnl_cents",
        "auto_promotion",
        "paper_operation",
        "bankroll_curve",
        "canary",
        "ledger",
        "crypto_paper_twin",
        "sports_operation",
    ):
        assert field not in sanitized
        assert sanitized["retired_audit_history"][field] == legacy[field]
        assert field in legacy  # source/raw audit input was not rewritten
    audit = sanitized["retired_audit_history"]
    assert audit["status"] == "RETIRED_NON_AUTHORITATIVE"
    assert audit["execution_authority"] is False
    assert audit["can_enable_live"] is False
    assert audit["can_block_live"] is False
    assert audit["raw_history_preserved"] is True
    assert sanitized["scheduler_fleet"] == [
        {"role": "dashboard", "healthy": True},
    ]
    assert audit["scheduler_fleet"] == [
        {"role": "crypto paper twin", "healthy": True},
    ]
    assert "crypto_paper_twin" not in sanitized["data_ages"]
    assert "crypto_paper_twin" in audit["data_ages"]


def test_api_autonomy_sanitizes_fresh_legacy_assembly(monkeypatch):
    from starlette.testclient import TestClient

    import autonomy.dashboard as dashboard

    monkeypatch.setattr(
        dashboard,
        "assemble_dashboard_state",
        lambda: {
            "heartbeat": {"alive": True},
            "realized_shadow_pnl_cents": 123,
            "auto_promotion": {"execution_authority": True},
            "paper_operation": {"paper_bankroll_cents": 123},
            "bankroll_curve": [{"bankroll": 123}],
        },
    )

    with TestClient(dashboard.build_app()) as client:
        body = client.get("/api/autonomy").json()

    for field in (
        "realized_shadow_pnl_cents",
        "auto_promotion",
        "paper_operation",
        "bankroll_curve",
    ):
        assert field not in body
        assert field in body["retired_audit_history"]
    assert body["retired_audit_history"]["status"] == "RETIRED_NON_AUTHORITATIVE"
    assert body["retired_audit_history"]["execution_authority"] is False


def test_overview_reads_cached_live_account_without_broker_contact(
    tmp_path,
    monkeypatch,
):
    import json

    from starlette.testclient import TestClient

    import autonomy.dashboard as dashboard
    from autonomy.live_account_snapshot import write_live_account_snapshot

    now = datetime.now(timezone.utc)
    (tmp_path / "latest_dashboard_snapshot.json").write_text(
        json.dumps({
            "generated_at": now.isoformat(),
            "overview_generated_at": now.isoformat(),
            "block_status": {"overview": "REFRESHED"},
            "overview": {"bankroll_cents": 999_999, "paper": True},
        }),
        encoding="utf-8",
    )
    write_live_account_snapshot({
        "schema": "dummy.live_account_snapshot",
        "version": 1,
        "generated_at": now.isoformat(),
        "status": "FRESH",
        "stale": False,
        "reason": None,
        "execution_authority": False,
        "balance_cents": 10_381,
        "open_positions_count": 0,
        "open_orders_count": 0,
        "historical_orders_count": 84,
        "historical_fills_count": 78,
        "order_status_counts": {"canceled": 10, "executed": 74},
        "source": {"provider": "kalshi", "authenticated": True},
        "http_proof": {"get_only": True},
        "errors": [],
    }, tmp_path / "live_account_snapshot.json")
    monkeypatch.setattr(dashboard, "RUNTIME_DIR", tmp_path)

    overview = TestClient(dashboard.build_app()).get("/api/overview").json()

    assert overview["live_account"]["balance_cents"] == 10_381
    assert overview["live_account"]["open_positions_count"] == 0
    assert overview["live_account"]["open_orders_count"] == 0
    assert overview["live_account"]["broker_contacted_by_dashboard"] is False
    assert overview["live_account"]["execution_authority"] is False
    assert "bankroll_cents" not in overview
    assert "paper" not in overview


def test_production_mispricing_runner_does_not_append_retired_paper_entries():
    runner = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_dummy_mispricing_monitor.py"
    ).read_text(encoding="utf-8")

    assert "persist_paper_entries" not in runner
    assert "PAPER_ENTRIES_PATH" not in runner
    assert "paper_entries.jsonl``" in runner
    assert "history is deliberately never appended here" in runner


def test_scheduled_shadow_daemon_runs_cycles_without_authority(monkeypatch, capsys):
    """Production must continue; authority must not.

    The retirement is an *authority* contract: shadow evidence keeps accruing
    (the forward proof plan depends on it) while every emitted record
    discloses that it can never enable or block live trading.
    """
    from scripts import run_dummy_shadow_daemon as runner

    monkeypatch.setattr(runner.sys, "argv", ["run_dummy_shadow_daemon.py"])
    seen: dict[str, object] = {}

    def fake_cycle(at, mode):
        seen["mode"] = mode
        return {"at": at, "status": "CYCLE_OK", "orders_placed": 0}

    monkeypatch.setattr(runner, "run_one_cycle", fake_cycle)

    assert runner.main() == 0
    output = capsys.readouterr().out
    assert seen["mode"] is runner.SessionMode.SHADOW
    assert '"status": "CYCLE_OK"' in output
    assert '"paper_results_authority": "RETIRED_NON_AUTHORITATIVE"' in output
    assert '"execution_authority": false' in output


def test_crypto_paper_twin_runner_runs_cycles_without_authority(
    monkeypatch, capsys, tmp_path
):
    from scripts import run_dummy_crypto_paper_twin as runner

    monkeypatch.setattr(runner.sys, "argv", [
        "run_dummy_crypto_paper_twin.py",
        "--db", str(tmp_path / "twin.db"),
        "--out-dir", str(tmp_path / "out"),
        "--lock", str(tmp_path / "twin.lock"),
    ])

    class FakeLedger:
        def __init__(self, *_args, **_kwargs):
            pass

    class FakeTwin:
        def __init__(self, *_args, **_kwargs):
            pass

        def run_cycle(self):
            return {"status": "CYCLE_OK", "trades_opened": 1}

        def close(self):
            pass

    monkeypatch.setattr(runner, "PaperTwinLedger", FakeLedger)
    monkeypatch.setattr(runner, "CryptoPaperTwin", FakeTwin)
    monkeypatch.setattr(
        runner, "write_paper_twin_report",
        lambda report, out_dir: tmp_path / "out" / "report.json",
    )
    monkeypatch.setattr(runner, "_summary", lambda report, path: dict(report))
    monkeypatch.setattr(runner, "_atomic_json", lambda path, row: None)
    monkeypatch.setattr(runner, "_console_summary", lambda summary: dict(summary))

    assert runner.main() == 0
    output = capsys.readouterr().out
    assert '"status": "CYCLE_OK"' in output
    assert '"paper_results_authority": "RETIRED_NON_AUTHORITATIVE"' in output
    assert '"execution_authority": false' in output
    assert '"capital_authority": false' in output


def test_vnext_shadow_runner_runs_passes_without_authority(monkeypatch, capsys):
    import autonomy.vnext_runtime as vnext_runtime
    from scripts import run_dummy_vnext_shadow as runner

    monkeypatch.setattr(
        vnext_runtime,
        "run_shadow_pass",
        lambda: {"status": "SHADOW_PASS_OK", "episodes_issued": 2},
    )

    assert runner.main() == 0
    output = capsys.readouterr().out
    assert '"status": "SHADOW_PASS_OK"' in output
    assert '"episodes_issued": 2' in output
    assert '"paper_results_authority": "RETIRED_NON_AUTHORITATIVE"' in output
    assert '"execution_authority": false' in output
