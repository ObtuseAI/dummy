from __future__ import annotations


def test_no_trade_attribution_scores_saved_capital_and_missed_opportunity() -> None:
    from predator_mesh.v17.decisions import DecisionLedger, NoTradeReason

    ledger = DecisionLedger()
    record = ledger.record_no_trade(
        market_id="KXDEMO-TRUTH",
        forecast_snapshot_id="forecast-1",
        reasons=[NoTradeReason.REAL_TERRAIN_WARNING, NoTradeReason.SPREAD_TOO_WIDE],
        proof_refs=["no-trade-proof"],
    )
    attribution = ledger.attribute_no_trade(record.record_id, avoided_loss=True)

    assert attribution.outcome == "GOOD_SAVE"
    assert attribution.evidence_backed is True
    assert ledger.no_trade_attribution_report()["good_save_count"] == 1
