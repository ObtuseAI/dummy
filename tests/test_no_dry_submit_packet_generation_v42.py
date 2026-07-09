from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_dry_submit_packet_generation_v42() -> None:
    assert_current_test_report(__file__)["dry_submit_packets_created"] is False
