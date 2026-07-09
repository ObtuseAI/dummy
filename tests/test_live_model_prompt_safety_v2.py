from __future__ import annotations

import json

import pytest

from model_router.smoke import LiveModelSmokeV2


@pytest.fixture
def smoke_v2_runner(tmp_path):
    return LiveModelSmokeV2(artifacts_dir=tmp_path)


def test_prompt_safety_report_v2_all_allowed(smoke_v2_runner):
    report = smoke_v2_runner.generate_prompt_safety_report_v2()

    assert report["workstream"] == "V8.1: Live Model Prompt Safety"
    assert report["verdict"] == "PASS"
    assert len(report["prompt_entries"]) == 2
    for entry in report["prompt_entries"]:
        assert entry["allowed"] is True
        assert entry["firewall_classification"] == "SAFE_SANITIZED_MARKET_PROMPT"
        assert "prompt_digest" in entry
        assert "prompt_summary" in entry


def test_prompt_safety_report_v2_no_raw_prompts(smoke_v2_runner):
    report = smoke_v2_runner.generate_prompt_safety_report_v2()
    text = json.dumps(report, default=str)
    assert smoke_v2_runner.deepseek_prompt not in text
    assert smoke_v2_runner.minimax_prompt not in text


def test_prompt_safety_report_v2_does_not_contain_secret_values(smoke_v2_runner, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")

    report = smoke_v2_runner.generate_prompt_safety_report_v2()
    text = json.dumps(report, default=str)
    assert "sk-deepseek-secret-value" not in text
    assert "sk-minimax-secret-value" not in text
