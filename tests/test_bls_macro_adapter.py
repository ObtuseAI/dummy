from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_bls_macro_adapter_is_official_public_readonly() -> None:
    report = assert_v20_report("bls_macro_adapter_report_v1.json", "legality_class")
    assert report["legality_class"].startswith("OFFICIAL_PUBLIC")

