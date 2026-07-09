from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_nonempty_orderbook_proof_counts_bid_and_ask_depth() -> None:
    proof = real_snapshot().nonempty_proof.to_report()

    assert proof["nonempty"] is True
    assert proof["bid_depth"] > 0
    assert proof["ask_depth"] > 0
    assert proof["verdict"] == "PASS"
