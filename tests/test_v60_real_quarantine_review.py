from __future__ import annotations

from predator_mesh.v59.reports import _build_quarantine_instances, _write_quarantine_instances
from predator_mesh.v55.reports import _approval_hash
from archive.report_scripts.generate_v60_reports import generate_all_v60_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe
from tests.v59_test_helpers import approval_input

APPROVAL = approval_input()


def _write_real_artifacts(quarantine_dir):
    instances = _build_quarantine_instances(APPROVAL, _approval_hash(APPROVAL))
    return _write_quarantine_instances(instances, quarantine_dir)


def test_v60_default_has_no_real_quarantine_artifacts() -> None:
    reports = generate_all_v60_reports_for_tests()
    reviewer = reports["v60_real_quarantine_artifact_reviewer_report.json"]
    assert_staged_safe(reviewer)
    assert reviewer["v59_baseline_status"] == "PASS_V59_BASELINE_READBACK"
    assert reviewer["real_quarantine_artifact_reviewer_status"] == "PARTIAL_NO_REAL_QUARANTINE_ARTIFACTS"
    assert reviewer["reviewed_artifact_count"] == 0
    final = reports["final_report_v60.json"]
    assert final["verdict"] == "PARTIAL"
    assert "NO_REAL_QUARANTINE_ARTIFACTS" in final["current_blockers"]


def test_v60_reviews_real_artifacts_and_denies_release(tmp_path) -> None:
    quarantine_dir = tmp_path / "quarantine"
    _write_real_artifacts(quarantine_dir)
    before = {p.name: p.read_bytes() for p in quarantine_dir.glob("*.json")}
    reports = generate_all_v60_reports_for_tests(quarantine_dir=quarantine_dir)
    reviewer = reports["v60_real_quarantine_artifact_reviewer_report.json"]
    integrity = reports["v60_artifact_integrity_review_v3_report.json"]
    denial = reports["v60_release_denial_v3_report.json"]
    assert reviewer["real_quarantine_artifact_reviewer_status"] == "PASS_REAL_QUARANTINE_ARTIFACTS_REVIEWED"
    assert reviewer["reviewed_artifact_count"] == 4
    assert integrity["artifact_integrity_review_v3_status"] == "PASS_ARTIFACT_INTEGRITY_VALIDATED"
    assert integrity["hashes_before_after_match"] is True
    assert denial["release_denial_v3_status"] == "PASS_RELEASE_DENIED"
    assert reports["final_report_v60.json"]["verdict"] == "PASS"
    after = {p.name: p.read_bytes() for p in quarantine_dir.glob("*.json")}
    assert before == after


def test_v60_tamper_detector_flags_forbidden_fields(tmp_path) -> None:
    import json

    quarantine_dir = tmp_path / "q"
    _write_real_artifacts(quarantine_dir)
    tampered = _build_quarantine_instances(APPROVAL, _approval_hash(APPROVAL))[0]
    tampered["broker_payload"] = {"order_id": "X1"}
    (quarantine_dir / "tampered.json").write_text(json.dumps(tampered), encoding="utf-8")
    reports = generate_all_v60_reports_for_tests(quarantine_dir=quarantine_dir)
    reviewer = reports["v60_real_quarantine_artifact_reviewer_report.json"]
    assert reviewer["real_quarantine_artifact_reviewer_status"] == "FAIL_ARTIFACT_INTEGRITY"
    assert reviewer["tamper_detected"] is True
    assert reports["final_report_v60.json"]["verdict"] == "FAIL"


def test_v60_safety_and_locks() -> None:
    reports = generate_all_v60_reports_for_tests()
    for name, report in reports.items():
        if name == "final_report_v60.json":
            continue
        assert_staged_safe(report)
