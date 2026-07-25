from __future__ import annotations

from core.caps_authority import CAPS_CONFIG_INTACT_STATES
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from tests.v35_test_helpers import (
    CAPS_INTACT_REPORT_STATUSES,
    assert_current_test_report,
)


def test_protected_hash_reverification_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["live_submit_hash"] == LIVE_SUBMIT_HASH
    assert report["caps_hash"] == CAPS_HASH
    assert report["live_submit_enabled"] is False
    assert report["caps_config_integrity_valid"] is True
    # Caps config must be INTACT. Whether an operator has registered is their
    # prerogative and moves this between the two intact states; pinning
    # REVIEW_REQUIRED asserted they had not exercised a sanctioned path, which
    # turned red the moment they did. CONFIG_INTEGRITY_BLOCKED still fails
    # here, so tamper detection is unchanged.
    assert report["caps_authority_state"] in CAPS_CONFIG_INTACT_STATES
    assert isinstance(report["caps_authority_registration_valid"], bool)
    assert report["legacy_caps_authority_invalidated"] is True
    # The invariant that actually matters, true in either intact state.
    assert report["execution_authority"] is False
    assert report["execution_bridge_present"] is False


def test_live_submit_still_disabled_and_unchanged() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    ls = assert_v35_report_named("live_submit_hash_check_v1_report.json")
    assert ls["unchanged"] is True
    caps = assert_v35_report_named("caps_hash_check_v1_report.json")
    assert caps["unchanged"] is True
    assert caps["caps_hash_check_v1_status"] in CAPS_INTACT_REPORT_STATUSES
    assert isinstance(caps["caps_authority_registration_valid"], bool)
    assert caps["execution_authority"] is False
    enabled = assert_v35_report_named("live_submit_enabled_check_v1_report.json")
    assert enabled["live_submit_enabled"] is False
