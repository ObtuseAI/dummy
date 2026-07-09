from __future__ import annotations

from predator_mesh.v11.post_trade import PostTradeLedgerSkeleton


def test_fill_attribution_schema_contains_expected_and_realized_drag() -> None:
    report = PostTradeLedgerSkeleton().schema_report()
    fields = set(report["schema_fields"])

    assert report["verdict"] == "PASS"
    assert "expected_price" in fields
    assert "simulated_fill_price" in fields
    assert "expected_fill_drag" in fields
    assert "realized_simulated_fill_drag" in fields
    assert "expected_edge_after_fill_drag" in fields
