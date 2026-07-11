from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from model_router.error_classifier import classify_provider_error
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider, MockProvider, ProviderError
from model_router.config import ProviderConfig
from model_router.tasks import ModelTask
from archive.report_scripts.generate_v8_model_provider_reports import (
    generate_live_model_provider_adapter_report_v1,
    generate_model_provider_error_handling_report_v1,
    generate_provider_reports,
)


def _http_status_error(status_code: int) -> Exception:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("provider error", request=request, response=response)


class TestClassifyProviderError:
    def test_timeout(self):
        request = httpx.Request("GET", "https://example.com")
        assert classify_provider_error(httpx.TimeoutException("timeout", request=request)) == "TIMEOUT"

    def test_connect_error(self):
        request = httpx.Request("GET", "https://example.com")
        assert classify_provider_error(httpx.ConnectError("refused", request=request)) == "CONNECT_ERROR"

    def test_http_429(self):
        assert classify_provider_error(_http_status_error(429)) == "HTTP_429"

    def test_http_500(self):
        assert classify_provider_error(_http_status_error(500)) == "HTTP_500"

    def test_provider_error_fallback(self):
        assert classify_provider_error(RuntimeError("Unexpected provider response")) == "PROVIDER_ERROR"


class TestProviderErrorHandling:
    @pytest.mark.asyncio
    async def test_deepseek_raises_provider_error_without_key(self, monkeypatch, no_project_env):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        cfg = ProviderConfig(
            api_base="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            model_name="deepseekv4flash",
        )
        provider = DeepSeekV4FlashProvider(cfg)
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete("test", ModelTask.FORECAST_OPINION)
        assert exc_info.value.metadata["error_class"] == "PROVIDER_ERROR"

    @pytest.mark.asyncio
    async def test_minimax_raises_provider_error_without_key(self, monkeypatch, no_project_env):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        cfg = ProviderConfig(
            api_base="https://api.minimax.chat",
            api_key_env="MINIMAX_API_KEY",
            model_name="minimaxm3",
        )
        provider = MinimaxM3Provider(cfg)
        with pytest.raises(ProviderError) as exc_info:
            await provider.complete("test", ModelTask.STRATEGY_CRITIQUE)
        assert exc_info.value.metadata["error_class"] == "PROVIDER_ERROR"

    @pytest.mark.asyncio
    async def test_mock_provider_returns_tuple_with_metadata(self):
        provider = MockProvider()
        text, metadata = await provider.complete("test", ModelTask.FORECAST_OPINION)
        assert isinstance(text, str)
        assert metadata["provider"] == "mock"
        assert metadata["model"] == "mock"
        assert "latency_ms" in metadata
        assert "prompt_digest" in metadata
        assert metadata["error_class"] is None

    @pytest.mark.asyncio
    async def test_deepseek_retries_on_500_then_succeeds(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        cfg = ProviderConfig(
            api_base="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            model_name="deepseekv4flash",
            timeout_seconds=1.0,
        )
        provider = DeepSeekV4FlashProvider(cfg)

        request = httpx.Request("POST", cfg.api_base)
        error_response = httpx.Response(500, request=request)
        error_exc = httpx.HTTPStatusError("server error", request=request, response=error_response)

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = {
            "choices": [{"message": {"content": '{"dummy_probability":"0.55","confidence_score":"0.72","reasoning":"ok"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        ok_response.raise_for_status = MagicMock()

        call_count = 0
        async def post_mock(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise error_exc
            return ok_response

        client_instance = MagicMock()
        client_instance.post = AsyncMock(side_effect=post_mock)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("model_router.providers.httpx.AsyncClient", return_value=client_instance):
            with patch("model_router.providers.asyncio.sleep", new_callable=AsyncMock):
                content, metadata = await provider.complete("prompt", ModelTask.FORECAST_OPINION)

        assert call_count == 2
        assert metadata["attempts"] == 2
        assert metadata["error_class"] is None


class TestErrorHandlingReport:
    @pytest.mark.asyncio
    async def test_error_handling_report_passes(self):
        report = await generate_model_provider_error_handling_report_v1()
        assert report["verdict"] == "PASS"
        classifications = report["sample_classifications"]
        assert len(classifications) >= 5
        assert all(c["error_type"] != "unknown" for c in classifications)
        assert report["provider_error_sample"]["tag"] == "PROVIDER_ERROR"

    @pytest.mark.asyncio
    async def test_live_adapter_report_passes_without_credentials(self, monkeypatch, no_project_env):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        report = await generate_live_model_provider_adapter_report_v1()
        assert report["verdict"] == "PASS"
        by_name = {r["provider"]: r for r in report["provider_results"]}
        assert by_name["mock"]["status"] == "ok"
        assert by_name["deepseek_v4_flash"]["status"] == "skipped"
        assert by_name["minimax_m3"]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_provider_reports_writes_files(self, monkeypatch, tmp_path):
        import archive.report_scripts.generate_v8_model_provider_reports as reports_module

        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.setattr(reports_module, "ARTIFACTS", tmp_path)
        paths = await generate_provider_reports()
        assert "live_model_provider_adapter_report_v1.json" in paths
        assert "model_provider_error_handling_report_v1.json" in paths
        for path in paths.values():
            assert path.exists()
            assert "sk-" not in path.read_text()
