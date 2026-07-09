from __future__ import annotations

import json

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics


def test_kalshi_credential_forensics_classifies_invalid_local_key_without_secrets() -> None:
    report = KalshiCredentialForensics().to_report()
    text = json.dumps(report)

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["failure_reason"] in {
        "NONE",
        "CREDENTIALS_MISSING",
        "MALFORMED_ENVIRONMENT_VARIABLE",
        "UNSUPPORTED_PRIVATE_KEY_ENCODING",
        "AUTH_SIGNATURE_FAILURE_LIKELY",
        "KEY_ID_PRIVATE_KEY_MISMATCH_LIKELY",
        "BASE_URL_MISMATCH_LIKELY",
        "PERMISSION_OR_ACCOUNT_ISSUE_LIKELY",
        "CLOCK_DRIFT_LIKELY",
        "ENDPOINT_BASE_URL_MISMATCH_LIKELY",
    }
    assert report["secret_values_exposed"] is False
    assert "BEGIN PRIVATE KEY" not in text
