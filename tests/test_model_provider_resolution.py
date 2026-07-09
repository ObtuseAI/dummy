from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from model_router.resolver import ModelProviderResolver
from model_router.smoke import _DEEPSEEK_SMOKE_PROMPT


def _make_response(status_code: int, json_data: dict):
    """Return a sync-shaped httpx Response mock.

    httpx.Response.json() and raise_for_status() are synchronous, so we use
    MagicMock rather than AsyncMock to avoid returning unawaited coroutines.
    """
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
async def test_resolver_returns_mock_only_without_key(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    resolver = ModelProviderResolver()
    result = await resolver.resolve(
        "deepseek_v4_flash",
        default_base="https://api.deepseek.com",
        default_aliases=["deepseek-chat"],
        smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
    )

    assert result.status == "MOCK_ONLY"
    assert result.redacted_metadata["api_key_present"] is False
    assert result.error_category is None


@pytest.mark.asyncio
async def test_resolver_proves_live_via_model_list(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    resolver = ModelProviderResolver()

    async def _fake_model_list(*args, **kwargs):
        return _make_response(200, {"data": [{"id": "deepseek-chat"}]})

    with patch("httpx.AsyncClient.get", new=_fake_model_list):
        result = await resolver.resolve(
            "deepseek_v4_flash",
            default_base="https://api.deepseek.com",
            default_aliases=["deepseek-chat"],
            smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
        )

    assert result.status == "LIVE_PROVEN"
    assert result.resolved_model == "deepseek-chat"
    assert result.resolved_by == "model_list"


@pytest.mark.asyncio
async def test_resolver_proves_live_via_alias_smoke(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    resolver = ModelProviderResolver()

    async def _fake_model_list(*args, **kwargs):
        return _make_response(404, {})

    call_count = 0

    async def _fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_response(
            200,
            {"choices": [{"message": {"content": '{"thesis":"ok","confidence":"0.5"}'}}]},
        )

    with patch("httpx.AsyncClient.get", new=_fake_model_list):
        with patch("httpx.AsyncClient.post", new=_fake_post):
            result = await resolver.resolve(
                "deepseek_v4_flash",
                default_base="https://api.deepseek.com",
                default_aliases=["deepseek-chat"],
                smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
            )

    assert result.status == "LIVE_PROVEN"
    assert result.resolved_by == "alias_smoke"
    assert call_count >= 1


@pytest.mark.asyncio
async def test_resolver_reports_operator_config_when_all_aliases_404(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    resolver = ModelProviderResolver()

    async def _fake_request(*args, **kwargs):
        return _make_response(404, {})

    with patch("httpx.AsyncClient.get", new=_fake_request):
        with patch("httpx.AsyncClient.post", new=_fake_request):
            result = await resolver.resolve(
                "deepseek_v4_flash",
                default_base="https://api.deepseek.com",
                default_aliases=["unknown-model"],
                smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
            )

    assert result.status == "OPERATOR_MODEL_CONFIG_REQUIRED"
    assert result.error_category in ("ENDPOINT_NOT_FOUND", "MODEL_NOT_FOUND", "PROVIDER_ROUTE_NOT_FOUND")
