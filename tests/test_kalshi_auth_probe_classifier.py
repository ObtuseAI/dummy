from __future__ import annotations

from predator_mesh.v14.credential_forensics import KalshiAuthProbeClassifier


def test_kalshi_auth_probe_classifier_maps_pem_error_to_invalid_credentials() -> None:
    report = KalshiAuthProbeClassifier().classify_exception(
        ValueError("Unable to load PEM file. InvalidData(InvalidByte(0, 92))")
    ).to_dict()

    assert report["failure_reason"] == "MALFORMED_ENVIRONMENT_VARIABLE"
    assert report["safe_to_retry_real_readonly"] is False
    assert report["verdict"] == "PARTIAL"
