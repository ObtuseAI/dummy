import os
import pytest


def test_kalshi_credential_readiness_v2():
    from archive.report_scripts.generate_v6_reports import generate_kalshi_credential_readiness_report_v2
    report = generate_kalshi_credential_readiness_report_v2()
    assert report["credentials_present"] in (True, False)
    assert report["verdict"] in ("PASS", "PARTIAL", "SKIP")
    assert "KALSHI_API_KEY_ID" in report["required_secret_names"][0]
    assert "PRIVATE_KEY" in report["required_secret_names"][1]


def test_credential_helper_v2_does_not_expose_secrets():
    from archive.report_scripts.generate_v6_reports import generate_kalshi_credential_readiness_report_v2
    report = generate_kalshi_credential_readiness_report_v2()
    report_str = str(report)
    key_id = os.environ.get("KALSHI_API_KEY_ID", "")
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM", "")
    pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH", "")
    if key_id:
        assert key_id not in report_str
    if pem:
        assert pem not in report_str
    if pem_path:
        assert pem_path not in report_str
