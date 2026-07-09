from __future__ import annotations

import json

from scripts.generate_v8_firewall_reports import generate_firewall_reports


def test_no_llm_secret_leak_report_generated(tmp_path, monkeypatch):
    secret = "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    generate_firewall_reports(artifact_dir=str(tmp_path))

    report = json.loads((tmp_path / "no_llm_secret_leak_report_v2.json").read_text())
    assert report["leak_detected"] is False
    text = json.dumps(report)
    assert secret not in text


def test_prompt_firewall_v2_report_generated(tmp_path):
    generate_firewall_reports(artifact_dir=str(tmp_path))
    report = json.loads((tmp_path / "llm_prompt_firewall_v2_report.json").read_text())
    assert report["report"] == "llm_prompt_firewall_v2_report"
    samples = {s["sample"]: s for s in report["samples"]}
    assert samples["safe"]["allowed"] is True
    assert samples["secret"]["allowed"] is False
    assert samples["order"]["allowed"] is False
    assert samples["cap"]["allowed"] is False


def test_model_output_firewall_report_generated(tmp_path):
    generate_firewall_reports(artifact_dir=str(tmp_path))
    report = json.loads((tmp_path / "model_output_firewall_report_v1.json").read_text())
    assert report["report"] == "model_output_firewall_report_v1"
    samples = {s["sample"]: s for s in report["samples"]}
    assert samples["safe"]["safe"] is True
    assert samples["order"]["safe"] is False
    assert samples["order"]["category"] == "ORDER_INSTRUCTION_BLOCK"
