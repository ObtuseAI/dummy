from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_order_ticket_generation_v42() -> None:
    assert_current_test_report(__file__)["order_tickets_created"] is False
