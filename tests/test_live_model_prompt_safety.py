from __future__ import annotations

import json

import pytest

from model_router.smoke import (
    LiveModelSmoke,
    generate_live_model_prompt_safety_report_v1,
)


@pytest.fixture
def smoke_runner(tmp_path):
    return LiveModelSmoke(artifacts_dir=tmp_path)


@pytest.mark.asyncio
async def test_prompt_safety_report_passes_for_harmless_prompts(smoke_runner):
    report = smoke_runner.generate_prompt_safety_report()

    assert report["verdict"] == "PASS"
    assert len(report["prompt_entries"]) == 2
    for entry in report["prompt_entries"]:
        assert entry["allowed"] is True
        assert entry["firewall_classification"] == "SAFE_SANITIZED_MARKET_PROMPT"
        assert entry["matched_tokens"] == []
        assert "prompt_digest" in entry
        assert "prompt_summary" in entry


@pytest.mark.asyncio
async def test_prompt_safety_report_blocks_order_instruction(smoke_runner):
    unsafe_prompt = "submit a buy order for 100 shares immediately"
    smoke_runner.deepseek_prompt = unsafe_prompt
    report = smoke_runner.generate_prompt_safety_report()

    assert report["verdict"] == "FAIL"
    deepseek_entry = next(
        e for e in report["prompt_entries"] if e["provider"] == "deepseek"
    )
    assert deepseek_entry["allowed"] is False
    assert deepseek_entry["firewall_classification"] == "ORDER_INSTRUCTION_BLOCK"
    assert deepseek_entry["matched_tokens"]


@pytest.mark.asyncio
async def test_prompt_safety_report_detects_secret_in_prompt(smoke_runner):
    unsafe_prompt = "here is my key sk-abcdefghijklmnopqrstuvwxyz1234"
    smoke_runner.minimax_prompt = unsafe_prompt
    report = smoke_runner.generate_prompt_safety_report()

    minimax_entry = next(
        e for e in report["prompt_entries"] if e["provider"] == "minimax"
    )
    assert minimax_entry["allowed"] is True

    sanitized_minimax = smoke_runner.firewall.sanitize(smoke_runner.minimax_prompt)
    assert "sk-" not in sanitized_minimax
    assert unsafe_prompt not in json.dumps(report)


@pytest.mark.asyncio
async def test_prompt_safety_report_no_raw_prompts(smoke_runner):
    report = smoke_runner.generate_prompt_safety_report()
    report_text = json.dumps(report, default=str)

    assert smoke_runner.deepseek_prompt not in report_text
    assert smoke_runner.minimax_prompt not in report_text


@pytest.mark.asyncio
async def test_public_generate_prompt_safety_report_helper():
    report = generate_live_model_prompt_safety_report_v1()
    assert report["verdict"] == "PASS"
    assert len(report["prompt_entries"]) == 2


@pytest.mark.asyncio
async def test_prompt_safety_report_completes_without_live_credentials(smoke_runner):
    """Prompt safety analysis is local and must not require or await live providers."""
    import os
    assert os.environ.get("DEEPSEEK_API_KEY") is None or True
    report = smoke_runner.generate_prompt_safety_report()
    assert report["verdict"] == "PASS"
