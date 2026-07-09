from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_no_real_probe_run_to_execution_bridge_v36() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_order_cancel"] is True
    assert report["no_live_submit_or_caps_touch"] is True
    assert report["no_execution_clients_imported"] is True
    assert report["execution_bridge_present"] is False
