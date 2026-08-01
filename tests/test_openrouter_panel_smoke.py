from __future__ import annotations

import json

import httpx
import pytest

from model_router.openrouter_panel_smoke import (
    EXACT_PANEL,
    run_openrouter_panel_smoke,
    write_redacted_smoke_report,
)


@pytest.fixture
def exact_config(tmp_path):
    config = {
        "default_provider": {},
        "hybrid_providers": [alias for alias, _ in EXACT_PANEL],
        "provider_configs": {
            alias: {
                "api_base": "https://openrouter.ai/api",
                "api_key_env": "OPENROUTER_API_KEY",
                "model_name": model,
                "route_mode": "openrouter",
            }
            for alias, model in EXACT_PANEL
        },
        "live_model_calls_enabled": False,
    }
    path = tmp_path / "model_routing.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_preflight_never_creates_network_calls(monkeypatch, tmp_path, exact_config):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-never-log")
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    report = await run_openrouter_panel_smoke(
        config_path=exact_config,
        project_root=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert report["status"] == "PREFLIGHT_READY"
    assert report["calls_attempted"] == 0
    assert report["call_results"] == []
    assert requests == 0
    assert "test-secret-never-log" not in json.dumps(report)


@pytest.mark.asyncio
async def test_live_smoke_calls_each_exact_model_once_and_records_identity(
    monkeypatch, tmp_path, exact_config
):
    secret = "test-secret-never-persist"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    requested_models: list[str] = []

    response_content = {
        "openai/gpt-5.6-terra": {
            "dummy_probability": 0.5,
            "confidence_score": 0.1,
            "reasoning": "smoke",
        },
        "openai/gpt-5.6-luna": {
            "dummy_probability": 0.5,
            "confidence_score": 0.1,
            "reasoning": "smoke",
            "action": "hold",
            "entry_condition": "smoke test only",
        },
        "anthropic/claude-sonnet-5": {
            "verdict": "warn",
            "reasoning": "smoke",
        },
        "z-ai/glm-5.2": {"risk_level": "low", "reasoning": "smoke"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(
            "https://openrouter.ai/api/v1/chat/completions"
        )
        assert request.headers["Authorization"] == f"Bearer {secret}"
        body = json.loads(request.content)
        requested_models.append(body["model"])
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(response_content[body["model"]])
                        }
                    }
                ],
                "usage": {"total_tokens": 17, "cost": 0.00001},
            },
        )

    report = await run_openrouter_panel_smoke(
        live=True,
        config_path=exact_config,
        project_root=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert report["status"] == "LIVE_PROVEN"
    assert report["calls_attempted"] == 4
    assert requested_models == [model for _, model in EXACT_PANEL]
    assert [row["response_model"] for row in report["call_results"]] == requested_models
    assert all(row["attempts"] == 1 for row in report["call_results"])
    assert all(row["response_content_stored"] is False for row in report["call_results"])
    encoded = json.dumps(report)
    assert secret not in encoded
    assert "smoke test only" not in encoded


@pytest.mark.asyncio
async def test_live_smoke_fails_closed_on_response_model_mismatch(
    monkeypatch, tmp_path, exact_config
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # Mismatch the FIRST panel entry explicitly. This used to key off
        # "not openai/", which worked only because the first seat happened
        # to be a non-OpenAI model; once that seat became an OpenAI one the
        # trigger silently stopped firing and the test passed for the wrong
        # reason. Tie it to the panel, not to a vendor prefix.
        first_panel_model = EXACT_PANEL[0][1]
        response_model = (
            "unexpected/model" if body["model"] == first_panel_model else body["model"]
        )
        return httpx.Response(
            200,
            json={
                "model": response_model,
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "dummy_probability": 0.5,
                                    "confidence_score": 0.1,
                                    "reasoning": "smoke",
                                }
                            )
                        }
                    }
                ],
            },
        )

    report = await run_openrouter_panel_smoke(
        live=True,
        config_path=exact_config,
        project_root=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert report["status"] == "LIVE_SMOKE_FAILED"
    assert report["all_models_live_proven"] is False
    assert report["call_results"][0]["status"] == "MODEL_IDENTITY_MISMATCH"


@pytest.mark.asyncio
async def test_shared_auth_failure_stops_further_requests(
    monkeypatch, tmp_path, exact_config
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "rejected-secret")
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    report = await run_openrouter_panel_smoke(
        live=True,
        config_path=exact_config,
        project_root=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert requests == 1
    assert report["calls_attempted"] == 1
    assert report["call_results"][0]["status"] == "PROVIDER_AUTH_FAILED"
    assert all(
        row["status"] == "SKIPPED_SHARED_AUTH_FAILURE"
        for row in report["call_results"][1:]
    )


def test_redacted_writer_rejects_unmarked_report_and_writes_atomically(tmp_path):
    with pytest.raises(ValueError):
        write_redacted_smoke_report({"secret_free": False}, tmp_path / "bad.json")

    path = tmp_path / "smoke.json"
    report = {"status": "LIVE_PROVEN", "secret_free": True, "response_content_stored": False}
    assert write_redacted_smoke_report(report, path) == path
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert list(tmp_path.glob("*.tmp")) == []
