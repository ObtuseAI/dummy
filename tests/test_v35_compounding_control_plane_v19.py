from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v35_compounding_control_plane_v19_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v35_compounding_control_plane_v19_status"] == "PASS"
    assert report["next_bundle_recommendation"].startswith("DUMMY_V36")
    assert report["execution_bridge_present"] is False
    assert "exact-gate real read-only public probe run" in report["enabled_probe_queue"]
