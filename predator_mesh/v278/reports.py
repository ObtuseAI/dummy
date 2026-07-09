"""DUMMY v278 execute-once authority rehearsal V2 (fixture + non-broker double only) — no real order, does not inflate real proof score."""

from __future__ import annotations

from typing import Any

from predator_mesh import final_console_common as fcc
from predator_mesh.v278 import MILESTONE

WORKSTREAM = "v278: Execute-Once Authority Rehearsal V2 Fixture Only"
DASH_TITLE = "Dummy V278 Execute-Once Authority Rehearsal V2"
MISSION_KEY = "dummy_mission_state_report_v278"
CONTROLLER_KEY = "execute_once_authority_rehearsal_v2_controller_status"

REHEARSAL_CASES = [
    {"case": "absent_authority", "expected": "BLOCKED_FAIL_CLOSED", "submitted": False},
    {"case": "exact_full_authority_fixture", "expected": "SUBMITTED_AUTOLOCKED_NON_BROKER_DOUBLE", "submitted": True},
    {"case": "missing_env_gate", "expected": "BLOCKED_NO_ENV_GATE", "submitted": False},
    {"case": "wrong_env_ack", "expected": "BLOCKED_WRONG_ACK", "submitted": False},
    {"case": "fuzzy_approval", "expected": "REJECTED_APPROVAL_PHRASE_INVALID", "submitted": False},
    {"case": "broad_approval", "expected": "REJECTED_BROAD_APPROVAL", "submitted": False},
    {"case": "no_adapter", "expected": "BLOCKED_NO_ADAPTER", "submitted": False},
    {"case": "market_order", "expected": "REJECTED_MARKET_ORDER", "submitted": False},
    {"case": "repeat_attempt", "expected": "BLOCKED_AUTO_LOCKED", "submitted": False},
    {"case": "stale_proof_lock", "expected": "BLOCKED_STALE_PROOF_LOCK", "submitted": False},
]

FULL_AUTHORITY_FIXTURE = {
    "uses_non_broker_double": True,
    "submitted_autolocked": True,
    "real_live_orders": 0,
    "real_broker_contacted": False,
    "market_order": False,
    "fixture_only": True,
}

REPORT_GROUPS: dict[str, list[str]] = {
    "execute-once-authority-rehearsal-v2": ["v278_execute_once_authority_rehearsal_v2_controller_report.json"],
    "v277-baseline": ["v277_baseline_readback_v1_report.json"],
    "rehearsal-cases": ["v278_rehearsal_cases_report.json"],
    "full-authority-fixture": ["v278_full_authority_fixture_report.json"],
    "no-fixture-inflation-proof": ["v278_no_fixture_inflation_proof_report.json"],
    "no-submit-proof": ["v278_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v278_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v238_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v237_report.json"],
    "mission-state": ["dummy_mission_state_report_v278.json", "dashboard_v278_report_v1.json", "completion_oriented_next_action_v278_report.json"],
}

V278_ROUTES = [f"/api/v278/{g}" for g in REPORT_GROUPS]
SUMMARY_FIELDS = [["Mission", "mission_state_verdict"], ["Rehearsal", CONTROLLER_KEY], ["Next Action", "current_next_action"]]


def _controller(baseline_status: str, **kw: Any) -> dict[str, Any]:
    return {
        "status": "PASS_EXECUTE_ONCE_AUTHORITY_REHEARSAL_V2_COMPLETE_FIXTURE_ONLY",
        "verdict": "PASS",
        "fields": {
            "rehearsal_cases": REHEARSAL_CASES,
            "rehearsal_case_count": len(REHEARSAL_CASES),
            "full_authority_fixture": FULL_AUTHORITY_FIXTURE,
            "fixture_proof_inflates_real_score": False,
            "no_fixture_inflation_proof_status": "PASS_NO_FIXTURE_INFLATION",
            "no_submit_proof_status": "PASS_NO_SUBMIT",
            "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        },
        "blockers": [],
        "next_action": "EXECUTE_ONCE_AUTHORITY_REHEARSAL_V2_COMPLETE_FIXTURE_ONLY_NEXT_RUN_EXECUTE_ONCE_WITH_REAL_AUTHORITY_NO_SUBMIT_BY_DUMMY",
    }


_BUNDLE = fcc.StageBundle(
    version=278, milestone=MILESTONE, workstream=WORKSTREAM, dash_title=DASH_TITLE,
    controller_key=CONTROLLER_KEY, report_groups=REPORT_GROUPS, index_keys=[CONTROLLER_KEY, "current_next_action"],
    controller_fn=_controller, summary_fields=SUMMARY_FIELDS, routes=V278_ROUTES,
)

DEFAULT_REQUIRED_REPORT_NAMES = _BUNDLE.required
FINAL_NAME = _BUNDLE.final_name
MISSION_NAME = _BUNDLE.mission_name
INDEX_KEYS = _BUNDLE.index_keys
VERIFICATION_COMMANDS = _BUNDLE.verification_commands


class V278ReportFactory:
    def __init__(self, **kw: Any) -> None:
        self.kw = kw

    def build(self) -> dict[str, dict[str, Any]]:
        return _BUNDLE.build_reports(**self.kw)
