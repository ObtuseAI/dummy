from tests.v30_test_helpers import assert_v30_report_named


def test_v30_adapter_implementation_selection_v1_selects_small_safe_set_and_defers_rest() -> None:
    report = assert_v30_report_named(
        "v30_adapter_implementation_selection_v1_report.json",
        "adapter_implementation_selection_status",
        "selected_adapter_count",
        "deferred_adapter_spec_count",
    )

    assert report["adapter_implementation_selection_status"] == "PASS"
    assert report["v29_adapter_spec_ready_count"] >= 6
    assert report["selected_adapter_count"] == 4
    assert report["implemented_adapter_count"] == 4
    assert report["deferred_adapter_spec_count"] >= 2
    assert set(report["selected_adapter_domains"]) == {"weather", "crypto", "public_event", "kalshi"}
    assert "sports" in report["deferred_adapter_domains"]
    assert "trading" in report["deferred_adapter_domains"]
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_imported"] is False
    assert report["mined_repo_executed"] is False
    assert report["live_execution_enabled"] is False
