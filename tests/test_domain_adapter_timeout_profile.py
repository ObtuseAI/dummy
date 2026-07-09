from __future__ import annotations


def test_domain_adapter_timeout_profile_bounds_every_adapter() -> None:
    from predator_mesh.v19.runtime import DomainAdapterTimeoutProfile

    report = DomainAdapterTimeoutProfile().to_report()
    assert report["verdict"] == "PASS"
    assert all(item["timeout_seconds"] <= 10 for item in report["adapter_timeouts"])
