from __future__ import annotations

from predator_mesh.v13.endpoint_audit import KalshiOrderbookEndpointProof


def test_kalshi_orderbook_endpoint_proof_is_read_only_get() -> None:
    proof = KalshiOrderbookEndpointProof().to_dict()

    assert proof["endpoint"] == "GET /markets/{ticker}/orderbook"
    assert proof["read_only"] is True
    assert proof["request_timeout_s"] <= 10
    assert proof["direct_order_or_cancel"] is False
