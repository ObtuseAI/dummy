from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_fuzzy_ack_probe_run_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["accepted_ack"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
