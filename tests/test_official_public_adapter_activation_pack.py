from __future__ import annotations


def test_official_public_adapter_activation_pack_is_readonly_and_fallback_safe() -> None:
    from predator_mesh.v20.official_adapters import OfficialPublicAdapterActivationPack

    report = OfficialPublicAdapterActivationPack().to_report()

    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["read_only_only"] is True
    assert report["write_endpoints_called"] == []
    assert report["bounded_timeouts"] is True
    assert report["fallback_safe"] is True
