from __future__ import annotations

from predator_mesh.v13.endpoint_audit import KalshiReadOnlyEndpointAuditV2


def test_kalshi_readonly_endpoint_audit_v2_allows_only_bounded_gets() -> None:
    report = KalshiReadOnlyEndpointAuditV2().to_report()

    assert report["verdict"] == "PASS"
    assert report["write_endpoints_allowed"] == []
    assert "GET /markets/{ticker}/orderbook" in report["audited_endpoints"]
    assert all(endpoint.startswith("GET ") for endpoint in report["audited_endpoints"])
