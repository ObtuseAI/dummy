from __future__ import annotations

import json

from predator_mesh.v14.credential_forensics import KalshiCredentialRepairHint


def test_kalshi_credential_repair_hints_are_placeholder_only() -> None:
    report = KalshiCredentialRepairHint.for_reason("MALFORMED_ENVIRONMENT_VARIABLE").to_report()
    text = json.dumps(report)

    assert report["verdict"] == "PASS"
    assert report["placeholder_examples_only"] is True
    assert "KALSHI_API_PRIVATE_KEY_PEM_PATH=<path-to-private-key-pem>" in text
    assert "BEGIN PRIVATE KEY" not in text
