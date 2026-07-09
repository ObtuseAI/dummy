from __future__ import annotations

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from tests.v35_test_helpers import assert_current_test_report


def test_protected_hash_reverification_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["live_submit_hash"] == LIVE_SUBMIT_HASH
    assert report["caps_hash"] == CAPS_HASH
    assert report["live_submit_enabled"] is False
    assert report["execution_bridge_present"] is False


def test_live_submit_still_disabled_and_unchanged() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    ls = assert_v35_report_named("live_submit_hash_check_v1_report.json")
    assert ls["unchanged"] is True
    caps = assert_v35_report_named("caps_hash_check_v1_report.json")
    assert caps["unchanged"] is True
    enabled = assert_v35_report_named("live_submit_enabled_check_v1_report.json")
    assert enabled["live_submit_enabled"] is False
