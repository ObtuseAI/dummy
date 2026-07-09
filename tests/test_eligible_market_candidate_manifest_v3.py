from __future__ import annotations

from tests.v16_test_helpers import real_discovery


def test_candidate_manifest_v3_is_sanitized_and_bounded() -> None:
    manifest = real_discovery().candidate_manifest()

    assert manifest["candidate_count"] == 1
    assert manifest["version"] == "v3"
    assert manifest["account_sensitive_fields_excluded"] is True
    assert "balance" not in str(manifest).lower()
