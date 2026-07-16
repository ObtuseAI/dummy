from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_blunder_separation_v20_report_passes() -> None:
    report = assert_security_report("generate_blunder_separation_recheck_v20")
    assert report["canonical_blunder_modified"] is False
