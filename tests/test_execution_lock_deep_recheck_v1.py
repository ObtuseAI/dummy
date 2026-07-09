from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_execution_lock_deep_recheck_v1_blocks_every_execution_artifact() -> None:
    report = assert_current_test_report(__file__)
    assert report["execution_lock_status"] == "PASS"
    assert report["order_tickets_created"] is False
    assert report["broker_payloads_created"] is False
    assert report["execution_rehearsal_created"] is False
