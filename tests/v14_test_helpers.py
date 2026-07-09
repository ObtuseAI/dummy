from __future__ import annotations

from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient, real_snapshot_result


def fake_invalid_forensics_report() -> dict:
    return {
        "verdict": "PARTIAL",
        "failure_reason": "MALFORMED_ENVIRONMENT_VARIABLE",
        "credentials_valid_for_retry": False,
        "secret_values_exposed": False,
    }


def fake_valid_forensics_report() -> dict:
    return {
        "verdict": "PASS",
        "failure_reason": "NONE",
        "credentials_valid_for_retry": True,
        "secret_values_exposed": False,
    }
