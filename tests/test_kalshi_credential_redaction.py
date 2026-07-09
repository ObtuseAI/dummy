from __future__ import annotations

import json

from tests.v13_test_helpers import SECRET_KEY, SECRET_PEM, ready_bridge


def test_kalshi_credential_redaction_report_contains_no_secret_values(tmp_path) -> None:
    report = ready_bridge(tmp_path).redaction_report()
    text = json.dumps(report)

    assert report["verdict"] == "PASS"
    assert report["secret_values_exposed"] is False
    assert SECRET_KEY not in text
    assert SECRET_PEM not in text
