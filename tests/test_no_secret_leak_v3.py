"""Scan logs and artifacts for leaked Kalshi secrets."""

import os
from pathlib import Path

import pytest

import core.secret_guard as secret_guard

SECRET_KEYS = [
    "KALSHI_API_KEY_ID",
    "KALSHI_API_PRIVATE_KEY_PEM",
    "KALSHI_API_PRIVATE_KEY_PEM_PATH",
]


def _real_secret_values():
    """Return configured secrets that look like real credentials."""
    values = []
    for key in SECRET_KEYS:
        value = os.environ.get(key)
        if value and len(value) >= 8:
            values.append((key, value))
    return values


def test_no_real_secret_values_in_logs_and_artifacts():
    """Any real configured secret value must not appear in logs or artifacts."""
    secrets = _real_secret_values()
    if not secrets:
        pytest.skip("No real secret values configured in environment")

    paths = []
    for root in ["logs", "artifacts"]:
        p = Path(root)
        if p.exists():
            paths.extend(p.rglob("*"))

    offenders = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for key, value in secrets:
            if value in text:
                offenders.append((key, str(path)))

    assert not offenders, f"Secrets found in: {offenders}"


def test_redact_text_masks_registered_secret():
    """redact_text masks a secret value once it is registered."""
    original = list(secret_guard._SECRET_VALUES)
    try:
        secret_guard._SECRET_VALUES.append("kalshi-test-key-id-12345")
        text = secret_guard.redact_text("Authorization: kalshi-test-key-id-12345")
        assert "kalshi-test-key-id-12345" not in text
        assert "***REDACTED***" in text
    finally:
        secret_guard._SECRET_VALUES[:] = original


def test_redact_masks_secret_keys():
    payload = {"api_key_id": "secret123", "private_key": "pem456", "safe": "visible"}
    redacted = secret_guard.redact(payload)
    assert redacted["api_key_id"] == "***REDACTED***"
    assert redacted["private_key"] == "***REDACTED***"
    assert redacted["safe"] == "visible"
