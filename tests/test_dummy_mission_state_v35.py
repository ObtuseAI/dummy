from __future__ import annotations

from tests.v35_test_helpers import (
    CAPS_INTACT_REPORT_STATUSES,
    assert_current_test_report,
)


def test_dummy_mission_state_v35_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["mission_state_verdict"] == "PARTIAL"
    assert report["v34_qc_confirmation_status"] == "PASS"
    assert report["dispatch_overlap_fix_verification_status"] == "PASS_VERIFIED"
    assert report["dead_constant_removal_verification_status"] == "PASS_VERIFIED"
    assert report["frontend_build_status"] == "PASS"
    assert report["v34_route_api_smoke_status"] == "PASS"
    # Caps config INTACT, in either registered or unregistered state -- see
    # CAPS_CONFIG_INTACT_STATES. CONFIG_INTEGRITY_BLOCKED still fails.
    assert report["protected_hash_reverification_status"] in CAPS_INTACT_REPORT_STATUSES
    assert report["no_execution_bridge_deep_recheck_status"] == "PASS"
    assert report["live_submit_flag_status"] == "PASS_DISABLED"
    assert report["caps_config_status"] in CAPS_INTACT_REPORT_STATUSES
    assert isinstance(report["caps_authority_registration_valid"], bool)
    assert report["execution_authority"] is False
    assert report["no_browser_pageagent_dom_status"] == "PASS"
    assert report["no_mined_repo_execution_status"] == "PASS"
    assert report["blunder_separation_status"] == "PASS"
    assert report["canonical_identity_status"] == "PASS"
    assert report["execution_bridge_present"] is False
    assert "enabled path uses fake transport only" in " ".join(report["partial_reasons"])
    # This reason is emitted only while no valid operator caps registration
    # exists, and correctly disappears once one is issued. Asserting it
    # unconditionally meant the report going *right* failed the test, so assert
    # the relationship instead -- which still catches the reason being dropped
    # while the registration is genuinely missing.
    registration_reason_present = (
        "fresh external authority registration is required"
        in " ".join(report["partial_reasons"])
    )
    assert registration_reason_present is (
        report["caps_authority_registration_valid"] is False
    )
