from tests.v25_test_helpers import assert_current_test_report


def test_v25_mission_state_tracks_market_class_generalization_and_safety() -> None:
    report = assert_current_test_report(__file__)
    assert report["verdict"] == "PARTIAL"
    assert report["market_class_ontology_status"] == "PASS"
    assert report["market_class_registry_status"] == "PASS"
    assert report["evidence_to_market_mapper_status"] == "PASS"
    assert report["settlement_mapping_status"] == "PASS"
    assert report["forecast_cadence_status"] == "PASS"
    assert report["forecast_cadence_counts"]["forecast_count"] >= 3
    assert report["forecast_cadence_counts"]["no_trade_count"] >= 3
    assert report["no_trade_quality_status"] == "PASS"
    assert report["live_observer_loop_status"] in {"PASS", "PARTIAL"}
    assert report["live_forecast_count"] >= 3
    assert report["live_unresolved_count"] >= 1
    assert report["live_scored_count"] == 0
    assert report["market_class_scoring_status"] == "PASS"
    assert report["replay_factory_status"] == "PASS"
    assert report["replay_count"] >= 8
    assert report["replay_scored_count"] >= 8
    assert report["calibration_v5_status"] == "PASS"
    assert report["source_truth_v7_status"] == "PASS"
    assert report["approved_market_class_discovery_status"] == "PASS"
    assert report["source_stack_builder_status"] == "PASS"
    assert report["forecast_ledger_status"] == "PASS"
    assert report["open_source_adapter_acceleration_status"] == "PASS"
    assert report["compounding_v9_status"] == "PASS"
    assert report["market_class_scoreboard_v10_status"] == "PASS"
    assert report["no_example_market_canonical_center_status"] == "PASS"
    assert report["live_submit_flag_status"] == "enabled=false"
    assert report["caps_config_status"] == "PASS"
    assert report["direct_order_bypass_status"] == "PASS"
    assert report["direct_cancel_bypass_status"] == "PASS"
