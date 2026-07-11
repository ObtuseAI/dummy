from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v61_reports import generate_all_v61_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def test_v61_design_only_passes_and_is_nonexecutable() -> None:
    reports = generate_all_v61_reports_for_tests()
    controller = reports["v61_local_rehearsal_design_controller_report.json"]
    spec = reports["v61_rehearsal_design_spec_report.json"]
    assert_staged_safe(controller)
    assert controller["v60_baseline_status"] == "PASS_V60_BASELINE_READBACK"
    assert controller["local_rehearsal_design_controller_status"] == "PASS_LOCAL_REHEARSAL_DESIGN_NONEXECUTABLE"
    assert controller["runnable_rehearsal_created"] is False
    assert controller["runnable_rehearsal_path_present"] is False
    assert spec["spec"]["executable"] is False
    final = reports["final_report_v61.json"]
    assert final["verdict"] == "PASS"


def test_v61_future_phrase_is_distinct_and_not_required_for_design() -> None:
    reports = generate_all_v61_reports_for_tests()
    policy = reports["v61_future_approval_phrase_policy_report.json"]
    assert policy["phrase"] == sgc.LOCAL_REHEARSAL_DESIGN_PHRASE
    assert policy["phrase_distinct_from_inert_artifact_phrase"] is True
    assert policy["future_approval_phrase_required_for_design_reports"] is False
    assert policy["future_approval_phrase_required_for_runnable_artifact"] is True


def test_v61_safety_and_locks() -> None:
    reports = generate_all_v61_reports_for_tests()
    for name, report in reports.items():
        if name == "final_report_v61.json":
            continue
        assert_staged_safe(report)
