from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_readonly_orderbook_endpoint_proof_v2_rejects_order_and_cancel_paths() -> None:
    proof = real_snapshot().endpoint_proof.to_report()

    assert proof["read_only_endpoints_only"] is True
    assert proof["order_endpoints_called"] == []
    assert proof["cancel_endpoints_called"] == []
    assert proof["verdict"] == "PASS"
