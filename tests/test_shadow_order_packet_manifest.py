from __future__ import annotations

from predator_mesh.v11.shadow_orders import ShadowOrderPacket


def test_shadow_order_packet_manifest_redacts_sensitive_payload() -> None:
    manifest = ShadowOrderPacket.manifest()
    text = str(manifest).lower()

    assert manifest["verdict"] == "PASS"
    assert manifest["packets"]
    assert "private" not in text
    assert "raw_prompt" not in text
    assert manifest["packets"][0]["digest"]["payload_stored"] == "digest_only"
