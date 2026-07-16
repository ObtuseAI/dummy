from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_fixture_claimed_real_v20_report_passes() -> None:
    report = assert_security_report("generate_no_fixture_claimed_real_report_v20")
    assert report["fixture_evidence_claimed_real"] is False
