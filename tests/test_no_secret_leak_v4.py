import pytest
from core.secret_guard import redact


def test_secret_guard_redacts_keys_and_values():
    payload = {
        "api_key_id": "AKIA123",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
        "safe": "visible",
    }
    out = redact(payload)
    assert out["api_key_id"] == "***REDACTED***"
    assert out["private_key"] == "***REDACTED***"
    assert out["safe"] == "visible"


def test_no_secret_leak_report_passes():
    from archive.report_scripts.generate_v5_reports import generate_no_secret_leak_report_v4
    report = generate_no_secret_leak_report_v4()
    assert report["verdict"] == "PASS"
