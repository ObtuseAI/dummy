from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_v35_sprint_queue_v12_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v35_sprint_queue_v12_status"] == "PASS"
    assert report["operator_action"].startswith("set DUMMY_PUBLIC_PROBE_MODE=1")
    assert report["risk_guard"] == "no live trading, no browser, no mined code"
    assert report["execution_bridge_present"] is False
    assert any(t["status"] == "NEXT" for t in report["tasks"])
