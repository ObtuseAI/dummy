from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_caps_config_modification_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["caps_unchanged"] is True
    assert report["configs_caps_modified"] is False
