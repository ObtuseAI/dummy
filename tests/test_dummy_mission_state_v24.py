from tests.v24_test_helpers import assert_current_test_report


def test_v24_mission_state_tracks_open_source_progress_and_safety() -> None:
    report = assert_current_test_report(__file__)
    assert report["open_source_source_doctrine_status"] == "PASS"
    assert report["source_universe_reclassification_status"] == "PASS"
    assert report["keyless_public_source_expansion_status"] == "PASS"
    assert report["public_proxy_terrain_status"] == "PASS"
    assert report["nasdaq_open_proxy_status"] == "NO_TRADE_EDGE_INSUFFICIENT"
    assert report["oil_open_proxy_status"] == "NO_TRADE_EDGE_INSUFFICIENT"
    assert report["open_data_replay_dataset_status"] == "PASS"
    assert report["replay_score_count"] >= 1
    assert report["live_forecast_count"] >= 1
    assert report["live_scored_count"] == 0
    assert report["optional_premium_demotion_status"] == "PASS"
    assert report["source_truth_v6_status"] == "PASS"
    assert report["open_source_compounding_v8_status"] == "PASS"
    assert report["live_submit_enabled"] is False
    assert report["caps_config_status"] == "PASS"
    assert report["direct_order_bypass_status"] == "PASS"
    assert report["direct_cancel_bypass_status"] == "PASS"
