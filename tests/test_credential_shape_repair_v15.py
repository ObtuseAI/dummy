from __future__ import annotations

from predator_mesh.v15.credential_shape_repair import (
    KalshiCredentialShapeRepairEngine,
    KalshiEnvRepairVerdict,
    KalshiMalformedEnvPattern,
)
from tests.v15_test_helpers import (
    MALFORMED_BACKSLASH_ENV,
    MISSING_ENV,
    PLACEHOLDER_KEY_ENV,
    VALID_ENV,
    forensics_with_env,
)


def test_valid_shape_detected_as_shape_valid() -> None:
    engine = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV))
    assert engine.verdict() == KalshiEnvRepairVerdict.SHAPE_VALID
    assert engine.detect_patterns() == [KalshiMalformedEnvPattern.NONE]


def test_malformed_backslash_pem_detected() -> None:
    engine = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MALFORMED_BACKSLASH_ENV))
    patterns = engine.detect_patterns()
    assert KalshiMalformedEnvPattern.LITERAL_BACKSLASH_N_IN_PEM in patterns
    assert engine.verdict() in {KalshiEnvRepairVerdict.SHAPE_REPAIRABLE_LOCALLY, KalshiEnvRepairVerdict.SHAPE_REQUIRES_OPERATOR_ACTION}


def test_missing_credentials_detected_as_shape_absent() -> None:
    engine = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MISSING_ENV))
    assert engine.verdict() == KalshiEnvRepairVerdict.SHAPE_ABSENT
    assert KalshiMalformedEnvPattern.CREDENTIALS_ABSENT in engine.detect_patterns()


def test_placeholder_key_id_detected() -> None:
    engine = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(PLACEHOLDER_KEY_ENV))
    assert KalshiMalformedEnvPattern.PLACEHOLDER_KEY_ID in engine.detect_patterns()


def test_report_never_exposes_secret_values() -> None:
    engine = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV))
    report = engine.to_report()
    text = str(report)
    assert "BEGIN PRIVATE KEY" not in text
    assert "real-looking-key-id-1234" not in text
    assert report["secret_values_exposed"] is False


def test_hints_are_placeholder_only() -> None:
    engine = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MALFORMED_BACKSLASH_ENV))
    for hint in engine.hints():
        assert "<" in hint.placeholder_example or hint.placeholder_example == ""
