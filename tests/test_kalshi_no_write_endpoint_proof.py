from __future__ import annotations

from predator_mesh.v13.endpoint_audit import KalshiNoWriteEndpointProof


def test_kalshi_no_write_endpoint_proof_blocks_submit_and_cancel_bypass() -> None:
    proof = KalshiNoWriteEndpointProof().to_dict()

    assert proof["direct_create_order_allowed"] is False
    assert proof["direct_cancel_order_allowed"] is False
    assert proof["write_methods_used"] == []
    assert proof["verdict"] == "PASS"
