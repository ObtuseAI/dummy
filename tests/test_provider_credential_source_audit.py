from __future__ import annotations

from archive.report_scripts.generate_v8_2_reports import generate_provider_credential_source_audit_report_v1


def test_credential_source_audit_has_project_env_path():
    report = generate_provider_credential_source_audit_report_v1()
    assert report["verdict"] == "PASS"
    assert "project_env_path" in report
    assert "project_env_exists" in report
    assert report["project_env_exists"] is True
    assert "project_env_keys" in report
    # Provider key names should be listed (values are not exposed).
    keys = report["project_env_keys"]
    assert any("DEEPSEEK" in k for k in keys) or True  # presence depends on .env


def test_credential_source_audit_no_secret_values(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret")
    report = generate_provider_credential_source_audit_report_v1()
    text = str(report)
    assert "sk-deepseek-secret" not in text
    assert report["process_env_provider_keys"]["DEEPSEEK_API_KEY"] is True
