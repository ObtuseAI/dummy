from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_dummy_canonical_identity_v20_report_passes() -> None:
    report = assert_security_report("generate_dummy_canonical_identity_report_v20")
    assert report["canonical_name"] == "Dummy"
