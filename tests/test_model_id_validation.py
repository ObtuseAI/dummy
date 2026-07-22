from __future__ import annotations

from unittest.mock import patch

import pytest

from archive.report_scripts.generate_v8_2_reports import generate_model_id_validation_report_v1


@pytest.mark.asyncio
async def test_model_id_validation_defaults_to_preflight_without_key(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    report = await generate_model_id_validation_report_v1()
    assert report["verdict"] == "PARTIAL"
    assert report["deepseek_v4_flash"]["status"] == "PREFLIGHT_ONLY"
    assert report["minimax_m3"]["status"] == "PREFLIGHT_ONLY"
    assert report["deepseek_v4_flash"]["network_contacted"] is False
    assert report["minimax_m3"]["network_contacted"] is False


@pytest.mark.asyncio
async def test_model_id_validation_reports_operator_config_on_404(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")

    async def _fake_request(*args, **kwargs):
        from tests.test_model_provider_resolution import _make_response
        return _make_response(404, {})

    with patch("httpx.AsyncClient.get", new=_fake_request):
        with patch("httpx.AsyncClient.post", new=_fake_request):
            report = await generate_model_id_validation_report_v1(allow_live=True)

    assert report["deepseek_v4_flash"]["status"] == "OPERATOR_MODEL_CONFIG_REQUIRED"
    assert report["minimax_m3"]["status"] == "OPERATOR_MODEL_CONFIG_REQUIRED"
