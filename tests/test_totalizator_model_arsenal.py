from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from autonomy.dashboard import build_app
from dashboard import model_arsenal_status as arsenal


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _write_exact_fixture(root, *, generated_at: datetime = NOW) -> None:
    config = root / "configs" / "model_routing.json"
    smoke = root / "artifacts" / "dummy" / "openrouter_four_model_smoke_v1.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    smoke.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps({
            "live_model_calls_enabled": False,
            "hybrid_providers": [row["provider_alias"] for row in arsenal.MODEL_ARSENAL_SPECS],
            "provider_configs": {
                row["provider_alias"]: {
                    "model_name": row["model"],
                    "route_mode": "openrouter",
                    "api_key_env": "OPENROUTER_API_KEY",
                    "reasoning_effort": "high",
                }
                for row in arsenal.MODEL_ARSENAL_SPECS
            },
        }),
        encoding="utf-8",
    )
    calls = [
        {
            "attempts": 1,
            "http_status": 200,
            "latency_ms": 125.0,
            "provider_alias": row["provider_alias"],
            "requested_model": row["model"],
            "response_model": row["model"],
            "response_content_stored": False,
            "model_identity_ok": True,
            "response_schema_ok": True,
            "reported_cost_usd": 0.0001,
            "status": "LIVE_PROVEN",
            "task": row["task"],
        }
        for row in arsenal.MODEL_ARSENAL_SPECS
    ]
    smoke.write_text(
        json.dumps({
            "schema_version": 1,
            "generated_at": generated_at.isoformat(),
            "mode": "live",
            "status": "LIVE_PROVEN",
            "all_models_live_proven": True,
            "secret_free": True,
            "response_content_stored": False,
            "calls_attempted": 4,
            "call_cap": 4,
            "expected_panel": [
                {"provider_alias": row["provider_alias"], "model": row["model"]}
                for row in arsenal.MODEL_ARSENAL_SPECS
            ],
            "call_results": calls,
        }),
        encoding="utf-8",
    )


def test_model_arsenal_builder_is_exact_redacted_and_fail_closed(tmp_path, monkeypatch):
    _write_exact_fixture(tmp_path)
    secret = "sk-totalizator-secret-must-not-render"
    (tmp_path / ".env").write_text(f"OPENROUTER_API_KEY={secret}\n", encoding="utf-8")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DUMMY_DEBATE_LIVE", "1")

    data = arsenal.build_model_arsenal_status(tmp_path, now=NOW)

    assert secret not in json.dumps(data)
    assert data["provider_contacted_by_dashboard"] is False
    assert data["mutation_authority"] is False
    assert data["network_action_available"] is False
    assert data["openrouter_access"] == {
        "present": True,
        "source": "project_env",
        "redacted": True,
        "required_env_name": "OPENROUTER_API_KEY",
    }
    assert data["panel_configuration"]["exact"] is True
    assert data["panel_configuration"]["configured_gate"] is False
    assert data["panel_configuration"]["runtime_opt_in"] is True
    assert data["panel_configuration"]["two_key_paid_call_gate_open"] is False
    assert data["panel_configuration"]["background_panel_ready"] is False
    assert data["live_smoke"]["verdict"] == "LIVE_CONNECTIVITY_PROVEN_CURRENT"
    assert data["live_smoke"]["models_proven"] == 4
    assert data["live_smoke"]["response_content_stored"] is False
    assert data["authorities"] == {
        "evidence": False,
        "probability": False,
        "order": False,
    }
    assert [row["model"] for row in data["models"]] == [
        "google/gemini-3.6-flash",
        "openai/gpt-5.6-luna",
        "anthropic/claude-sonnet-5",
        "z-ai/glm-5.2",
    ]


def test_model_arsenal_rejects_stale_or_identity_mismatched_smoke(tmp_path):
    _write_exact_fixture(tmp_path, generated_at=NOW - timedelta(hours=25))
    stale = arsenal.build_model_arsenal_status(tmp_path, now=NOW)
    assert stale["live_smoke"]["fresh"] is False
    assert stale["live_smoke"]["all_models_live_proven"] is False

    _write_exact_fixture(tmp_path)
    smoke_path = tmp_path / arsenal.MODEL_SMOKE_RELATIVE_PATH
    payload = json.loads(smoke_path.read_text(encoding="utf-8"))
    payload["call_results"][-1]["response_model"] = "z-ai/wrong-model"
    smoke_path.write_text(json.dumps(payload), encoding="utf-8")
    wrong = arsenal.build_model_arsenal_status(tmp_path, now=NOW)
    assert wrong["live_smoke"]["exact_panel"] is False
    assert wrong["live_smoke"]["all_models_live_proven"] is False
    assert wrong["authorities"]["order"] is False


def test_totalizator_model_arsenal_endpoint_is_read_only(monkeypatch):
    payload = {
        "provider_contacted_by_dashboard": False,
        "mutation_authority": False,
        "authorities": {"evidence": False, "probability": False, "order": False},
    }
    monkeypatch.setattr(arsenal, "build_model_arsenal_status", lambda: payload)

    response = TestClient(build_app()).get("/api/model-arsenal")

    assert response.status_code == 200
    assert response.json() == payload


def test_model_arsenal_status_module_has_no_network_or_mutation_primitive():
    source = inspect.getsource(arsenal)
    forbidden = (
        "requests.",
        "httpx.",
        ".complete(",
        "get_value(",
        "urlopen(",
        "subprocess",
        "create_order",
        "cancel_order",
        "write_text(",
        "write_bytes(",
    )
    assert not any(token in source for token in forbidden)
