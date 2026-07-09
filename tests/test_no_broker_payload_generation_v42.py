from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_broker_payload_generation_v42() -> None:
    assert_current_test_report(__file__)["broker_payloads_created"] is False
