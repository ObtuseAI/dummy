from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_outcome_fabrication_v20_report_passes() -> None:
    report = assert_security_report("generate_no_outcome_fabrication_report_v20")
    assert report["fabricated_outcomes"] is False

