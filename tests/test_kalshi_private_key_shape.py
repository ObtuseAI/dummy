from __future__ import annotations

from predator_mesh.v14.credential_forensics import KalshiPrivateKeyFormatCheck


def test_kalshi_private_key_shape_detects_literal_newline_encoding_without_exposing_key() -> None:
    check = KalshiPrivateKeyFormatCheck.from_secret_values(
        {"KALSHI_API_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----"}
    )

    assert check.present is True
    assert check.likely_valid is False
    assert check.failure_reason == "MALFORMED_ENVIRONMENT_VARIABLE"
    assert check.redacted is True
