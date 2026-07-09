from __future__ import annotations

from predator_mesh.v12.calibration import LiquidityCalibrationStore


def test_liquidity_calibration_store_records_v12_null_realized_fill_outcome() -> None:
    report = LiquidityCalibrationStore().to_report()

    assert report["verdict"] == "PASS"
    assert report["records"][0]["realized_fill_outcome"] is None
    assert report["records"][0]["future_reconciliation_placeholder"] is True
    assert report["records"][0]["shadow_order_digest"]
