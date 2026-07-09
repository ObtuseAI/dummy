from tests.v29_test_helpers import assert_v29_report_named


def test_adapter_spec_factory_v1_creates_in_house_specs_without_mined_code_or_execution_bridge() -> None:
    report = assert_v29_report_named(
        "adapter_spec_factory_v1_report.json",
        "adapter_spec_factory_status",
        "adapter_spec_ready_count",
        "adapter_specs",
    )

    assert report["adapter_spec_factory_status"] == "PASS"
    assert report["adapter_spec_ready_count"] >= 5
    assert report["mined_repo_code_copied"] is False
    assert report["blind_mined_code_copied"] is False
    assert report["adapter_spec_to_execution_bridge_present"] is False

    domains = {spec["domain"] for spec in report["adapter_specs"]}
    assert {"weather", "crypto", "event_market"} <= domains
    assert any(spec["domain"] == "sports" and spec["integration_probe_mode"] == "FIXTURE_ONLY" for spec in report["adapter_specs"])
    for spec in report["adapter_specs"]:
        assert spec["in_house_only"] is True
        assert spec["live_execution_enabled"] is False
        assert spec["mined_repo_import_required"] is False
        assert spec["no_execution_proof_required"] is True
        assert spec["timeout_seconds"] <= 6
        assert spec["expected_input"]
        assert spec["expected_output"]
