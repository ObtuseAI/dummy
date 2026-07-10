from __future__ import annotations

import json

from autonomy.paper_dashboard import PAPER_CONTROL_HEADER
from autonomy.sports.dashboard import SPORTS_TASK_NAME, assemble_sports_dashboard


def test_sports_dashboard_assembles_forced_coverage_state(tmp_path):
    (tmp_path / "sports_simulation_latest.json").write_text(json.dumps({
        "cycle_id": "sports-1",
        "completed_at": "2026-07-10T20:00:00+00:00",
        "status": "CYCLE_OK",
        "markets_seen": 12,
        "paper_decision_summary": {
            "decisions": 5,
            "open_decisions": 3,
            "settled_decisions": 2,
            "wins": 1,
            "win_rate": 0.5,
            "net_pnl_cents": 9,
            "lanes": [{
                "lane": "coverage_probe", "sport": "mlb", "market_type": "yrfi",
                "decisions": 2, "settled_decisions": 1, "wins": 1, "pnl_cents": 30,
            }],
        },
        "forced_coverage": {
            "designated_prediction_types": 17,
            "types_observed_this_cycle": 1,
            "types_covered_without_gap": 1,
            "coverage_gap_count": 16,
            "coverage_gaps": ["nfl:winner"],
            "matrix": [{
                "sport": "mlb", "market_type": "yrfi",
                "status": "TRACKING_FORCED_PAPER",
            }],
            "counts_toward_promotion": False,
        },
        "active_paper_trades": [{"ticker": "MLB-1"}],
        "recent_paper_settlements": [{"ticker": "MLB-0"}],
        "authority": {
            "execution_authority": False,
            "capital_authority": False,
            "forced_coverage_counts_toward_promotion": False,
        },
    }), encoding="utf-8")

    state = assemble_sports_dashboard(tmp_path)

    assert state["metrics"]["open_trades"] == 3
    assert state["metrics"]["settled_trades"] == 2
    assert state["metrics"]["net_pnl_cents"] == 9
    assert state["coverage"]["designated_prediction_types"] == 17
    assert state["coverage"]["coverage_gaps"] == ["nfl:winner"]
    assert state["evidence_boundary"]["counts_toward_promotion"] is False
    assert state["authority"]["capital_authority"] is False


def test_sports_scheduler_endpoint_is_fixed_to_sports_task(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    controls: list[tuple[str, str]] = []

    def control(action, task_name="DummyCryptoPaperTwin"):
        controls.append((action, task_name))
        return {
            "ok": True,
            "action": action,
            "capital_authority": False,
            "live_execution_authority": False,
        }

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    monkeypatch.setattr("autonomy.paper_dashboard.control_paper_scheduler", control)
    monkeypatch.setattr(
        "autonomy.paper_dashboard.scheduled_task_status",
        lambda task_name="DummyCryptoPaperTwin": {
            "task_name": task_name,
            "state": "Ready",
            "enabled": True,
            "healthy": True,
        },
    )
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    assert client.post("/api/sports-paper-scheduler/start").status_code == 403
    response = client.post(
        "/api/sports-paper-scheduler/start",
        headers={"X-Dummy-Paper-Control": PAPER_CONTROL_HEADER},
    )

    assert response.status_code == 200
    assert controls == [("start", SPORTS_TASK_NAME)]
    assert response.json()["capital_authority"] is False
