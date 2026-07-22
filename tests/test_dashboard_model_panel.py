from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from dashboard.backend import main as backend


PANEL = (
    ("gemini_3_6_flash", "google/gemini-3.6-flash", "forecast_opinion"),
    ("gpt_5_6_luna", "openai/gpt-5.6-luna", "rapid_forecast"),
    ("claude_sonnet_5", "anthropic/claude-sonnet-5", "strategy_critique"),
    ("glm_5_2", "z-ai/glm-5.2", "risk_critique"),
)


def _write_fixture(
    root,
    *,
    configured_gate: bool = True,
    generated_at: datetime | None = None,
    calls: list[dict] | None = None,
) -> tuple:
    config_path = root / "configs" / "model_routing.json"
    smoke_path = root / "artifacts" / "dummy" / "openrouter_four_model_smoke_v1.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({
            "live_model_calls_enabled": configured_gate,
            "hybrid_providers": [alias for alias, _model, _task in PANEL],
            "provider_configs": {
                alias: {
                    "model_name": model,
                    "route_mode": "openrouter",
                    "api_key_env": "OPENROUTER_API_KEY",
                    "reasoning_effort": "high",
                }
                for alias, model, _task in PANEL
            },
        }),
        encoding="utf-8",
    )
    call_rows = calls or [
        {
            "attempts": 1,
            "http_status": 200,
            "latency_ms": 25.0,
            "provider_alias": alias,
            "requested_model": model,
            "response_model": model,
            "response_content_stored": False,
            "model_identity_ok": True,
            "response_schema_ok": True,
            "status": "LIVE_PROVEN",
            "task": task,
        }
        for alias, model, task in PANEL
    ]
    smoke_path.write_text(
        json.dumps({
            "schema_version": 1,
            "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
            "mode": "live",
            "status": "LIVE_PROVEN",
            "all_models_live_proven": True,
            "secret_free": True,
            "response_content_stored": False,
            "calls_attempted": 4,
            "call_cap": 4,
            "expected_panel": [
                {"provider_alias": alias, "model": model}
                for alias, model, _task in PANEL
            ],
            "call_results": call_rows,
        }),
        encoding="utf-8",
    )
    return config_path, smoke_path


def test_model_panel_reports_exact_redacted_four_model_contract(tmp_path, monkeypatch):
    _config_path, smoke_path = _write_fixture(tmp_path)
    secret = "sk-openrouter-must-never-reach-dashboard"
    (tmp_path / ".env").write_text(f"OPENROUTER_API_KEY={secret}\n", encoding="utf-8")
    monkeypatch.setattr(backend, "ROOT", tmp_path)
    monkeypatch.setenv("DUMMY_DEBATE_LIVE", "1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    before = smoke_path.read_bytes()

    response = TestClient(backend.app).get("/api/read-only/model-panel")

    assert response.status_code == 200, response.text
    assert smoke_path.read_bytes() == before
    assert secret not in response.text
    data = response.json()
    assert data["provider_contacted_by_dashboard"] is False
    assert data["network_action_available"] is False
    assert data["openrouter_access"] == {
        "present": True,
        "source": "project_env",
        "redacted": True,
        "required_env_name": "OPENROUTER_API_KEY",
    }
    assert data["panel_configuration"]["exact"] is True
    assert data["panel_configuration"]["configured_gate"] is True
    assert data["panel_configuration"]["runtime_opt_in"] is True
    assert data["panel_configuration"]["two_key_paid_call_gate_open"] is True
    assert data["live_smoke"]["verdict"] == "LIVE_CONNECTIVITY_PROVEN_CURRENT"
    assert data["live_smoke"]["models_proven"] == 4
    assert data["live_smoke"]["response_content_stored"] is False
    assert data["authorities"] == {
        "evidence": False,
        "probability": False,
        "order": False,
    }
    assert [row["model"] for row in data["models"]] == [row[1] for row in PANEL]
    assert all(row["role"] and row["configuration_match"] for row in data["models"])


def test_current_smoke_is_independent_of_persistent_paid_call_gate(tmp_path, monkeypatch):
    _write_fixture(tmp_path, configured_gate=False)
    monkeypatch.setattr(backend, "ROOT", tmp_path)
    monkeypatch.setenv("DUMMY_DEBATE_LIVE", "1")

    data = TestClient(backend.app).get("/api/read-only/model-panel").json()

    assert data["live_smoke"]["all_models_live_proven"] is True
    assert data["panel_configuration"]["configured_gate"] is False
    assert data["panel_configuration"]["runtime_opt_in"] is True
    assert data["panel_configuration"]["two_key_paid_call_gate_open"] is False
    assert data["panel_configuration"]["gate_status"] == "LOCKED"
    assert data["authorities"]["order"] is False


def test_model_panel_fails_closed_for_stale_or_wrong_scope_smoke(tmp_path, monkeypatch):
    _write_fixture(
        tmp_path,
        generated_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    monkeypatch.setattr(backend, "ROOT", tmp_path)

    stale = TestClient(backend.app).get("/api/read-only/model-panel").json()
    assert stale["live_smoke"]["fresh"] is False
    assert stale["live_smoke"]["all_models_live_proven"] is False
    assert stale["live_smoke"]["blockers"]

    wrong_calls = [
        {
            "attempts": 1,
            "http_status": 200,
            "provider_alias": alias,
            "requested_model": model,
            "response_model": model,
            "response_content_stored": False,
            "model_identity_ok": True,
            "response_schema_ok": True,
            "status": "LIVE_PROVEN",
            "task": task,
        }
        for alias, model, task in PANEL
    ]
    wrong_calls[-1]["response_model"] = "z-ai/not-the-configured-model"
    _write_fixture(tmp_path, calls=wrong_calls)
    wrong = TestClient(backend.app).get("/api/read-only/model-panel").json()
    assert wrong["live_smoke"]["exact_panel"] is False
    assert wrong["live_smoke"]["all_models_live_proven"] is False
    assert wrong["authorities"]["evidence"] is False


def test_model_panel_get_has_no_network_or_provider_call_primitive():
    source = inspect.getsource(backend._model_panel_status)
    forbidden = (
        "requests.",
        "httpx.",
        ".complete(",
        "get_value(",
        "urlopen(",
        "subprocess",
    )
    assert not any(token in source for token in forbidden)
