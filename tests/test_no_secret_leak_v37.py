from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_secret_leak_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["secret_values_exposed"] is False
    assert report["raw_prompt_leaked"] is False
