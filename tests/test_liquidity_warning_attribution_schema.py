from __future__ import annotations


def test_liquidity_warning_attribution_schema_keeps_one_sided_warning_visible() -> None:
    from predator_mesh.v17.v16_integration import LiquidityWarningAttributionSchema

    report = LiquidityWarningAttributionSchema().to_report()

    assert "one_sided_real_book_warning" in report["warning_types"]
    assert report["proof_refs_supported"] is True
