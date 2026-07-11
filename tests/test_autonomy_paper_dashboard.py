from __future__ import annotations

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from autonomy.crypto_paper_twin import PaperTwinLedger
from autonomy.paper_dashboard import (
    PAPER_CONTROL_HEADER,
    assemble_paper_dashboard,
    control_paper_scheduler,
    scheduled_task_status,
)


NOW = datetime(2026, 7, 10, 20, 0, tzinfo=timezone.utc)


def _record_trade(
    ledger: PaperTwinLedger,
    cycle_id: str,
    *,
    suffix: str,
    close_time: datetime,
) -> None:
    observation_id = ledger.record_observation({
        "cycle_id": cycle_id,
        "strategy": "exploratory",
        "vertical": "CRYPTO",
        "timeframe": "1h",
        "bucket_start": NOW.isoformat(),
        "asset": "BTC",
        "event_cluster": f"cluster-{suffix}",
        "ticker": f"BTC-{suffix}",
        "action": "BUY_YES",
        "explanation": f"paper explanation {suffix}",
        "diagnostics": {},
        "created_at": NOW.isoformat(),
    })
    assert ledger.record_trade({
        "trade_id": f"trade-{suffix}",
        "observation_id": observation_id,
        "strategy": "exploratory",
        "vertical": "CRYPTO",
        "timeframe": "1h",
        "asset": "BTC",
        "event_cluster": f"cluster-{suffix}",
        "ticker": f"BTC-{suffix}",
        "side": "yes",
        "created_at": NOW.isoformat(),
        "close_time": close_time.isoformat(),
        "probability_yes": 0.65,
        "market_probability": 0.50,
        "uncertainty": 0.10,
        "edge_cents": 15.0,
        "conservative_ev_cents": 5.0,
        "taker_price_cents": 40,
        "taker_fee_cents": 1,
        "explanation": f"paper explanation {suffix}",
        "features": {"price_target": {"label": "settle at/above 100000"}},
        "market_snapshot": {},
        "policy": {},
        "maker_price_cents": 39,
        "maker_fee_cents": 1,
        "maker_queue_ahead": 2,
        "maker_queue_snapshot": True,
        "maker_status": "FILLED",
        "maker_expires_at": None,
    })


def test_paper_dashboard_reads_open_settled_and_pnl_truth(tmp_path):
    ledger = PaperTwinLedger(tmp_path / "crypto_paper_twin.db")
    cycle_id = ledger.start_cycle(NOW)
    _record_trade(ledger, cycle_id, suffix="settled", close_time=NOW + timedelta(hours=1))
    _record_trade(ledger, cycle_id, suffix="open", close_time=NOW + timedelta(hours=2))
    assert ledger.settle_ticker("BTC-settled", True, NOW + timedelta(hours=1)) == 1
    ledger.close()
    (tmp_path / "crypto_paper_twin_latest.json").write_text(json.dumps({
        "paper_mode": "LIVE_PUBLIC_READ_ONLY_SIMULATION",
        "completed_at": NOW.isoformat(),
        "status": "CYCLE_OK",
        "target_candidate_counts": {
            "forecasts": 25,
            "settled_forecasts": 10,
            "settled_event_clusters": 4,
        },
        "lanes": {"1h": {"exploratory": {"trades": 2, "settled_trades": 1}}},
        "forced_crypto_coverage": {
            "designated_scopes": 12,
            "scopes_observed_this_cycle": 12,
            "coverage_gap_count": 0,
            "summary": {"open_decisions": 12, "settled_decisions": 0},
            "matrix": [{
                "asset": "BTC", "timeframe": "15m",
                "status": "TRACKING_FORCED_PAPER", "is_coverage_gap": False,
            }],
        },
        "authority": {
            "broker_contacted": False,
            "execution_authority": False,
            "capital_authority": False,
        },
    }), encoding="utf-8")

    state = assemble_paper_dashboard(tmp_path)

    assert state["ledger_status"] == "QUERY_ONLY_OK"
    assert state["metrics"]["trades"] == 2
    assert state["metrics"]["open_trades"] == 1
    assert state["metrics"]["settled_trades"] == 1
    assert state["metrics"]["quote_simulated_net_pnl_cents"] == 59
    assert state["metrics"]["maker_witness_net_pnl_cents"] == 60
    assert state["metrics"]["unrealized_pnl_cents"] is None
    assert state["active_trades"][0]["target"]["label"] == "settle at/above 100000"
    assert state["recent_settlements"][0]["taker_pnl_cents"] == 59
    assert state["pnl_curve"][-1]["pnl_cents"] == 59
    assert state["lanes"][0]["vertical"] == "CRYPTO"
    assert state["forced_crypto_coverage"]["summary"]["open_decisions"] == 12
    assert state["forced_crypto_coverage"]["matrix"][0]["timeframe"] == "15m"


def test_scheduled_task_status_normalizes_windows_task():
    payload = {
        "state": "Ready",
        "enabled": True,
        "last_run_time": NOW.isoformat(),
        "last_result": 0,
        "next_run_time": (NOW + timedelta(minutes=5)).isoformat(),
        "execute": "python.exe",
        "arguments": "paper.py --summary",
        "working_directory": "C:\\repo",
        "execution_time_limit": "PT4M",
        "start_when_available": True,
        "multiple_instances": "IgnoreNew",
    }

    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")

    status = scheduled_task_status(runner=runner)

    assert status["enabled"] is True
    assert status["healthy"] is True
    assert status["last_result"] == 0
    assert status["capital_authority"] is False


def test_scheduler_controls_are_fixed_scope_and_fail_closed():
    commands: list[str] = []

    def runner(command, **_kwargs):
        commands.append(command[-1])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    started = control_paper_scheduler("start", runner=runner)
    stopped = control_paper_scheduler("stop", runner=runner)

    assert started["ok"] is True and stopped["ok"] is True
    assert "Enable-ScheduledTask" in commands[0]
    assert "Start-ScheduledTask" in commands[0]
    assert "Disable-ScheduledTask" in commands[1]
    assert all(result["capital_authority"] is False for result in (started, stopped))


def test_dashboard_control_endpoint_requires_header_and_never_grants_authority(
    tmp_path, monkeypatch,
):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(
        "autonomy.paper_dashboard.control_paper_scheduler",
        lambda action: {
            "ok": True,
            "action": action,
            "live_execution_authority": False,
            "capital_authority": False,
        },
    )
    monkeypatch.setattr(
        "autonomy.paper_dashboard.scheduled_task_status",
        lambda: {"state": "Running", "enabled": True, "healthy": True},
    )
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    assert client.post("/api/paper-scheduler/start").status_code == 403
    assert client.post(
        "/api/paper-scheduler/start",
        headers={
            "X-Dummy-Paper-Control": PAPER_CONTROL_HEADER,
            "Origin": "http://localhost.evil.example",
        },
    ).status_code == 403
    response = client.post(
        "/api/paper-scheduler/start",
        headers={"X-Dummy-Paper-Control": PAPER_CONTROL_HEADER},
    )

    assert response.status_code == 200
    assert response.json()["capital_authority"] is False


def test_control_invalidates_an_inflight_stale_dashboard_refresh(monkeypatch):
    from fastapi.testclient import TestClient

    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def assemble():
        nonlocal calls
        calls += 1
        version = calls
        if version == 1:
            entered.set()
            assert release.wait(timeout=5)
        return {"version": version}

    monkeypatch.setattr("autonomy.dashboard.assemble_dashboard_state", assemble)
    monkeypatch.setattr(
        "autonomy.paper_dashboard.control_paper_scheduler",
        lambda action: {"ok": True, "action": action},
    )
    monkeypatch.setattr(
        "autonomy.paper_dashboard.scheduled_task_status",
        lambda: {"state": "Disabled", "enabled": False, "healthy": False},
    )
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    with ThreadPoolExecutor(max_workers=2) as executor:
        old_request = executor.submit(client.get, "/api/autonomy")
        assert entered.wait(timeout=5)
        response = client.post(
            "/api/paper-scheduler/stop",
            headers={"X-Dummy-Paper-Control": PAPER_CONTROL_HEADER},
        )
        assert response.status_code == 200
        release.set()
        assert old_request.result(timeout=5).json()["version"] == 1

    assert client.get("/api/autonomy").json()["version"] == 2
    assert calls == 2
