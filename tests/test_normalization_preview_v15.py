from __future__ import annotations

from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.normalization_preview import KalshiCredentialNormalizationPreview
from tests.v15_test_helpers import MALFORMED_BACKSLASH_ENV, VALID_ENV, forensics_with_env


def test_preview_never_auto_edits_env() -> None:
    preview = KalshiCredentialNormalizationPreview(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MALFORMED_BACKSLASH_ENV))
    )
    report = preview.to_report()
    assert report["auto_edits_env"] is False
    assert report["writes_env_file"] is False


def test_preview_uses_placeholders_only() -> None:
    preview = KalshiCredentialNormalizationPreview(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MALFORMED_BACKSLASH_ENV))
    )
    report = preview.to_report()
    for example in report["examples"]:
        assert example["placeholder_examples_only"] is True
    template_lines = report["template"]["lines"]
    assert any("<your-key-id-here>" in line for line in template_lines)


def test_preview_never_leaks_real_secrets() -> None:
    preview = KalshiCredentialNormalizationPreview(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV))
    )
    text = str(preview.to_report())
    assert "BEGIN PRIVATE KEY-----\nabc" not in text
    assert "real-looking-key-id-1234" not in text


def test_preview_examples_match_detected_pattern() -> None:
    preview = KalshiCredentialNormalizationPreview(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MALFORMED_BACKSLASH_ENV))
    )
    patterns = [e.pattern for e in preview.examples()]
    assert "LITERAL_BACKSLASH_N_IN_PEM" in patterns
