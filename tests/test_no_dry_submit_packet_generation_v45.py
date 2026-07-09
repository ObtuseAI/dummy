from __future__ import annotations
from tests.v45_test_helpers import assert_current_test_report
def test_no_dry_submit_packet_generation_v45_report() -> None:
    assert_current_test_report(__file__)
