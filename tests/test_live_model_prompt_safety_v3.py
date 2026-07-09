from __future__ import annotations

from model_router.smoke import LiveModelSmokeV3


def test_prompt_safety_v3_all_allowed():
    runner = LiveModelSmokeV3()
    report = runner.generate_prompt_safety_report_v3()
    assert report["verdict"] == "PASS"
    for entry in report["prompt_entries"]:
        assert entry["allowed"] is True
        assert entry["firewall_classification"] == "SAFE_SANITIZED_MARKET_PROMPT"


def test_prompt_safety_v3_contains_no_secrets(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret")
    runner = LiveModelSmokeV3()
    report = runner.generate_prompt_safety_report_v3()
    text = str(report)
    assert "sk-deepseek-secret" not in text
