from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_unapproved_source_activation_v20_report_passes() -> None:
    report = assert_security_report("generate_no_unapproved_source_activation_report_v20")
    assert report["unapproved_sources_activated"] == []

