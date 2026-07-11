from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from model_router.config import ProviderConfig
from model_router.providers import BaseModelProvider
from model_router.smoke import LiveModelSmoke
from model_router.tasks import ModelTask
from archive.report_scripts.generate_v8_reports import main as orchestrator_main, ORCHESTRATOR_TIMEOUT_SECONDS


class _SlowProvider(BaseModelProvider):
    name = "slow_provider"

    @property
    def available(self) -> bool:
        return True

    async def _call_api(self, prompt, task, max_tokens, temperature):
        await asyncio.sleep(120)
        return "{}"


@pytest.mark.asyncio
async def test_orchestrator_wraps_generators_in_wait_for(tmp_path, monkeypatch):
    """The V8 orchestrator must apply a hard timeout to every report generator."""
    import archive.report_scripts.generate_v8_reports as orchestrator
    import archive.report_scripts.generate_v8_model_provider_reports as model_reports

    artifacts = tmp_path / "dummy"
    artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(orchestrator, "ARTIFACTS", artifacts)
    # Use a short timeout so the test proves the path without waiting 90s.
    monkeypatch.setattr(orchestrator, "ORCHESTRATOR_TIMEOUT_SECONDS", 2)

    async def _stall(*args, **kwargs):
        await asyncio.sleep(120)
        return {}

    start = asyncio.get_event_loop().time()
    with patch.object(model_reports, "main", new=_stall):
        result = await orchestrator_main(run_tests=False)
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 20, f"Orchestrator blocked for {elapsed:.1f}s"
    assert result["verdict"] in ("PASS", "PARTIAL", "FAIL")
    assert (artifacts / "tests_summary.json").exists()
    assert (artifacts / "final_report.json").exists()


def test_orchestrator_timeout_constant_is_finite():
    """The orchestrator-level timeout must be a finite, reasonable bound."""
    assert ORCHESTRATOR_TIMEOUT_SECONDS <= 120


@pytest.mark.asyncio
async def test_run_pytest_summary_uses_subprocess_timeout(monkeypatch):
    """``run_pytest_summary`` must pass a finite timeout to subprocess.run."""
    import subprocess
    import archive.report_scripts.generate_v8_reports as orchestrator

    calls = []

    def _fake_run(*args, **kwargs):
        calls.append(kwargs)
        class _Proc:
            returncode = 0
            stdout = "1 passed"
            stderr = ""
        return _Proc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    summary = orchestrator.run_pytest_summary()

    assert len(calls) == 1
    assert calls[0].get("timeout") is not None
    assert calls[0]["timeout"] > 0
    assert summary["pytest_returncode"] == 0


@pytest.mark.asyncio
async def test_smoke_runner_has_total_timeout(tmp_path, monkeypatch):
    """LiveModelSmoke.run() must have a hard total timeout and fall back."""
    import model_router.smoke as smoke_module

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-test")
    monkeypatch.setattr(smoke_module, "SMOKE_TOTAL_TIMEOUT", 1)
    monkeypatch.setattr(smoke_module, "SMOKE_CALL_TIMEOUT", 60)

    runner = LiveModelSmoke(artifacts_dir=tmp_path)
    slow = _SlowProvider(ProviderConfig(api_base="", api_key_env="", model_name="slow"))
    monkeypatch.setattr(runner, "_build_provider", lambda name: slow)

    start = asyncio.get_event_loop().time()
    report = await runner.run()
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 10, f"Smoke run blocked for {elapsed:.1f}s"
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"
