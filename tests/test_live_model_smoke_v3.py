from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from model_router.smoke import LiveModelSmokeV3


@pytest.fixture
def smoke_v3_runner(tmp_path):
    return LiveModelSmokeV3(artifacts_dir=tmp_path)


@pytest.mark.asyncio
async def test_smoke_v3_mock_only_without_credentials(clean_env, no_project_env, smoke_v3_runner):
    report = await smoke_v3_runner.run()
    assert report["live_model_status"] == "MOCK_ONLY"
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"
    for r in report["call_results"]:
        assert r["status"] == "MOCK_ONLY"
        assert r["prompt_firewall_ok"] is True
        assert r["output_firewall_ok"] is True
        assert r["secret_free"] is True
        assert "route_mode" in r


@pytest.mark.asyncio
async def test_smoke_v3_operator_config_required_on_404(monkeypatch, smoke_v3_runner):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")

    async def _fake_resolve(self, *args, **kwargs):
        from model_router.resolver import ProviderResolutionResult

        return ProviderResolutionResult(
            provider_name=args[0],
            status="OPERATOR_MODEL_CONFIG_REQUIRED",
            api_base="https://api.example.com",
            api_key_env="TEST_API_KEY",
            configured_model="unknown-model",
            error_category="MODEL_NOT_FOUND",
            error_detail="all aliases unresolved",
        )

    with patch("model_router.smoke.ModelProviderResolver.resolve", new=_fake_resolve):
        report = await smoke_v3_runner.run()

    assert report["live_model_status"] == "OPERATOR_MODEL_CONFIG_REQUIRED"
    assert report["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_smoke_v3_no_raw_prompts_or_keys(clean_env, smoke_v3_runner, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")

    report = await smoke_v3_runner.run()
    text = json.dumps(report, default=str)
    assert smoke_v3_runner.deepseek_prompt not in text
    assert smoke_v3_runner.minimax_prompt not in text
    assert "sk-deepseek-secret-value" not in text
    assert "sk-minimax-secret-value" not in text


@pytest.mark.asyncio
async def test_smoke_v3_writes_v3_reports(clean_env, no_project_env, tmp_path):
    runner = LiveModelSmokeV3(artifacts_dir=tmp_path)
    report = await runner.run()
    paths = await runner.write_reports_v3(report)

    assert "live_model_smoke_report_v3.json" in paths
    assert "live_model_prompt_safety_report_v3.json" in paths
    assert "live_model_output_safety_report_v2.json" in paths
    for path in paths.values():
        assert path.exists()
