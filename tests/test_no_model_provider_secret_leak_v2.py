from __future__ import annotations

import json

import pytest

from archive.report_scripts.generate_v8_1_reports import generate_no_model_provider_secret_leak_report_v2


@pytest.fixture
def secret_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret-value")


def test_no_secret_leak_report_passes_when_reports_are_clean(secret_env, tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts" / "dummy"
    artifacts.mkdir(parents=True)
    # Create clean report files.
    for name in [
        "model_provider_config_audit_report_v1.json",
        "model_provider_resolution_report_v1.json",
        "model_alias_resolution_report_v1.json",
        "model_provider_error_resolution_report_v1.json",
        "live_model_smoke_report_v2.json",
        "live_model_prompt_safety_report_v2.json",
        "live_model_output_safety_report_v1.json",
        "model_provider_operator_repair_recommendations_v1.json",
        "dashboard_v8_1_report_v1.json",
    ]:
        (artifacts / name).write_text(json.dumps({"safe": True, "note": "no secrets here"}))

    monkeypatch.setattr(
        "archive.report_scripts.generate_v8_1_reports.ARTIFACTS", artifacts
    )
    report = generate_no_model_provider_secret_leak_report_v2()
    assert report["verdict"] == "PASS"
    assert not report["leaked_files"]


def test_no_secret_leak_report_fails_when_secret_present(secret_env, tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts" / "dummy"
    artifacts.mkdir(parents=True)
    leaked = artifacts / "model_provider_resolution_report_v1.json"
    leaked.write_text(json.dumps({"note": "sk-deepseek-secret-value"}))

    monkeypatch.setattr(
        "archive.report_scripts.generate_v8_1_reports.ARTIFACTS", artifacts
    )
    report = generate_no_model_provider_secret_leak_report_v2()
    assert report["verdict"] == "FAIL"
    assert "model_provider_resolution_report_v1.json" in report["leaked_files"]
