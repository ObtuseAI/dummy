from __future__ import annotations

import json

import pytest

from scripts.generate_v8_model_provider_reports import (
    generate_credential_reports,
    generate_model_provider_credential_readiness_report_v1,
    generate_no_model_provider_secret_leak_report_v1,
)


@pytest.fixture
def secret_values():
    return {
        "DEEPSEEK_API_KEY": "sk-deepseek-secret-1234567890abcdef",
        "MINIMAX_API_KEY": "sk-minimax-secret-1234567890abcdef",
    }


class TestNoModelProviderSecretLeak:
    def test_status_object_does_not_contain_api_key(self, monkeypatch, secret_values):
        for key, value in secret_values.items():
            monkeypatch.setenv(key, value)

        from model_router.credential_readiness import CredentialReadiness

        readiness = CredentialReadiness()
        for name, status in readiness.all_statuses().items():
            status_dict = status.as_dict()
            assert "api_key" not in status_dict
            for value in secret_values.values():
                assert value not in str(status_dict)
                assert value not in json.dumps(status_dict)

    def test_credential_readiness_report_does_not_leak_keys(self, monkeypatch, secret_values):
        for key, value in secret_values.items():
            monkeypatch.setenv(key, value)

        report = generate_model_provider_credential_readiness_report_v1()
        report_str = json.dumps(report, default=str)
        for value in secret_values.values():
            assert value not in report_str
        assert report["deepseek"]["redacted"] is True
        assert report["minimax"]["redacted"] is True

    def test_no_secret_leak_report_passes_when_keys_present(self, monkeypatch, secret_values):
        for key, value in secret_values.items():
            monkeypatch.setenv(key, value)

        report = generate_no_model_provider_secret_leak_report_v1()
        assert report["provider_keys_redacted"] is True
        assert report["verdict"] == "PASS"

    def test_generated_report_files_contain_no_secrets(self, monkeypatch, secret_values, tmp_path):
        import scripts.generate_v8_model_provider_reports as reports_module

        for key, value in secret_values.items():
            monkeypatch.setenv(key, value)

        monkeypatch.setattr(reports_module, "ARTIFACTS", tmp_path)
        paths = generate_credential_reports()
        for value in secret_values.values():
            for path in paths.values():
                content = path.read_text()
                assert value not in content

    def test_no_secret_leak_report_passes_when_keys_absent(self, monkeypatch):
        for key in ("DEEPSEEK_API_KEY", "MINIMAX_API_KEY"):
            monkeypatch.delenv(key, raising=False)

        report = generate_no_model_provider_secret_leak_report_v1()
        assert report["provider_keys_redacted"] is True
        assert report["verdict"] == "PASS"
