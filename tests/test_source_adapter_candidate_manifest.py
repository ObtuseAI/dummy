from __future__ import annotations

from predator_mesh.v10.source_adapters import SourceAdapterPromotionEngine


def test_source_adapter_candidate_manifest_is_redacted() -> None:
    manifest = SourceAdapterPromotionEngine().candidate_manifest()
    assert manifest["verdict"] == "PASS"
    assert manifest["candidates"]
    text = str(manifest).lower()
    assert "api_key" not in text
    assert "private" not in text
    for candidate in manifest["candidates"]:
        assert candidate["source_name"]
        assert candidate["source_category"]
        assert candidate["mode"]
        assert candidate["proof_reference"]
