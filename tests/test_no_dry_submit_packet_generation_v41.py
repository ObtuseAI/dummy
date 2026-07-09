from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_dry_submit_packet_generation_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["dry_submit_packets_created"] is False
