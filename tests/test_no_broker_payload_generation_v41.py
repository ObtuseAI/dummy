from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_broker_payload_generation_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["broker_payloads_created"] is False
