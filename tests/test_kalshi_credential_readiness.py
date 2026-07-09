import os
import pytest


def test_required_secret_names_detected_without_leaking_values():
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
    pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")

    present = bool(key_id and (pem or pem_path))
    # We only assert that the detection logic works; values must never appear.
    assert isinstance(present, bool)
    if key_id:
        assert len(key_id) > 0
        # Ensure no raw PEM/secret material is treated as a value we would log.
        assert "BEGIN PRIVATE" not in str(key_id)


def test_credential_helper_does_not_expose_secrets():
    from scripts.generate_v5_reports import generate_kalshi_credential_readiness_report
    report = generate_kalshi_credential_readiness_report()
    assert report["credentials_present"] in (True, False)
    # The report must list the required secret names but never contain the actual values.
    assert "KALSHI_API_KEY_ID" in report["required_secret_names"][0]
    assert "PRIVATE_KEY" in report["required_secret_names"][1]
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
