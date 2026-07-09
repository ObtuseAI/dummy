from __future__ import annotations
from tests.v44_test_helpers import assert_current_test_report
def test_no_fuzzy_ack_probe_run_v44_report() -> None:
    assert_current_test_report(__file__)
