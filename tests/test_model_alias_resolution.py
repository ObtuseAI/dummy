from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from model_router.resolver import ModelProviderResolver


def _make_response(status_code: int, json_data: dict):
    """Return a sync-shaped httpx Response mock."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        request = httpx.Request("GET", "https://api.example.com/v1/models")
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=request, response=httpx.Response(status_code, request=request)
        )
    else:
        response.raise_for_status.return_value = None
    return response


@pytest.mark.asyncio
async def test_alias_resolution_report_lists_configured_aliases_and_resolution(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")

    async def _fake_model_list(*args, **kwargs):
        return _make_response(200, {"data": [{"id": "deepseek-chat"}, {"id": "minimax-01"}]})

    with patch("httpx.AsyncClient.get", new=_fake_model_list):
        from archive.report_scripts.generate_v8_1_reports import generate_model_alias_resolution_report_v1

        report = await generate_model_alias_resolution_report_v1()

    assert report["verdict"] == "PASS"
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        entry = report[provider]
        assert entry["configured_model"]
        assert isinstance(entry["aliases_attempted"], list)
        assert len(entry["aliases_attempted"]) >= 1
        assert entry["resolved_model"]
        assert entry["resolved_by"] == "model_list"


@pytest.mark.asyncio
async def test_alias_resolution_prefers_configured_model(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "custom-model")
    resolver = ModelProviderResolver()
    aliases = resolver._aliases("deepseek_v4_flash", ["deepseek-chat"])
    assert aliases[0].model_name == "custom-model"
    assert aliases[0].source == "config"


@pytest.mark.asyncio
async def test_alias_resolution_includes_env_aliases(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL_ALIASES", "env-alias-1,env-alias-2")
    resolver = ModelProviderResolver()
    aliases = resolver._aliases("deepseek_v4_flash", ["deepseek-chat"])
    sources = {a.source for a in aliases}
    assert "env" in sources
    model_names = [a.model_name for a in aliases]
    assert "env-alias-1" in model_names
    assert "env-alias-2" in model_names


@pytest.mark.asyncio
async def test_alias_resolution_no_duplicates(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_MODEL_ALIASES", "deepseek-chat")
    resolver = ModelProviderResolver()
    aliases = resolver._aliases("deepseek_v4_flash", ["deepseek-chat"])
    model_names = [a.model_name for a in aliases]
    assert model_names.count("deepseek-chat") == 1


@pytest.mark.asyncio
async def test_alias_resolution_respects_provider_specific_defaults():
    resolver = ModelProviderResolver()
    ds = [a.model_name for a in resolver._aliases("deepseek_v4_flash", ["deepseek-chat"])]
    mm = [a.model_name for a in resolver._aliases("minimax_m3", ["minimax-01"])]
    assert "deepseek-chat" in ds
    assert "minimax-01" in mm
    assert "deepseek-chat" not in mm
