from __future__ import annotations

import json

import pytest

from model_router.smoke import LiveModelSmokeV2


@pytest.fixture
def smoke_v2_runner(tmp_path):
    return LiveModelSmokeV2(artifacts_dir=tmp_path)


@pytest.mark.asyncio
async def test_output_safety_report_passes_for_mock_samples(smoke_v2_runner):
    report = await smoke_v2_runner.generate_output_safety_report()

    assert report["workstream"] == "V8.1: Live Model Output Safety"
    assert report["verdict"] == "PASS"
    assert len(report["samples"]) == 2
    for sample in report["samples"]:
        assert sample["output_firewall_safe"] is True


@pytest.mark.asyncio
async def test_output_safety_report_does_not_echo_secrets(smoke_v2_runner, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")

    report = await smoke_v2_runner.generate_output_safety_report()
    text = json.dumps(report, default=str)
    assert "sk-deepseek-secret-value" not in text
    assert "sk-minimax-secret-value" not in text
