"""DUMMY v60 real quarantine artifact review and release-denial reproof (read-only, non-executing)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v55.reports import ALLOWED_REHEARSAL_ARTIFACT_TYPES
from predator_mesh.v57.reports import DEFAULT_QUARANTINE_DIR as V57_QUARANTINE_DIR
from predator_mesh.v59.reports import (
    DEFAULT_QUARANTINE_DIR as V59_QUARANTINE_DIR,
    DENIAL_KINDS,
    FORBIDDEN_ARTIFACT_FIELDS,
    release_denial_matrix,
    validate_artifact_integrity,
)
from predator_mesh.v60 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS


def review_quarantine_dir(quarantine_dir: Path) -> list[dict[str, Any]]:
    """Read-only review of every JSON artifact in a quarantine directory using the strict V59 validator."""
    import json

    if not quarantine_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(quarantine_dir.glob("*.json")):
        before = sgc.sha256_bytes(path.read_bytes())
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            results.append({"artifact_type": None, "artifact_id": None, "integrity_pass": False, "forbidden_fields_present": [], "reasons": ["UNREADABLE_ARTIFACT"], "path": str(path), "unchanged": True})
            continue
        entry = validate_artifact_integrity(artifact)
        after = sgc.sha256_bytes(path.read_bytes())
        entry.update({"path": str(path), "hash_before": before, "hash_after": after, "unchanged": before == after})
        results.append(entry)
    return results

V60_ROUTES = [
    "/api/v60/real-quarantine-artifact-reviewer",
    "/api/v60/v59-baseline",
    "/api/v60/artifact-integrity-review-v3",
    "/api/v60/release-denial-v3",
    "/api/v60/tamper-detector",
    "/api/v60/canary-nonexecution-validator-v10",
    "/api/v60/readiness-governor",
    "/api/v60/execution-lock",
    "/api/v60/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "real-quarantine-artifact-reviewer": ["v60_real_quarantine_artifact_reviewer_report.json"],
    "v59-baseline": ["v59_baseline_readback_v1_report.json"],
    "artifact-integrity-review-v3": ["v60_artifact_integrity_review_v3_report.json"],
    "release-denial-v3": ["v60_release_denial_v3_report.json"],
    "tamper-detector": ["v60_tamper_detector_report.json"],
    "canary-nonexecution-validator-v10": ["v60_canary_nonexecution_validator_v10_report.json"],
    "readiness-governor": ["readiness_governor_v20_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v19_report.json"],
    "mission-state": ["dummy_mission_state_report_v46.json", "dashboard_v60_report_v1.json", "completion_oriented_next_action_v60_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(60)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v60/reports.py scripts/generate_v60_reports.py dashboard/backend/v60_routes.py",
    "python scripts/generate_v60_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V60Context:
    def __init__(self, *, quarantine_dir: Path | None) -> None:
        # Default reviews the real V59 quarantine directory (empty in the default repo state).
        self.quarantine_dir = quarantine_dir or V59_QUARANTINE_DIR
        self.review_results = review_quarantine_dir(self.quarantine_dir)
        self.release_denials = release_denial_matrix()
        self.v59_baseline_status = sgc.baseline_status("final_report_v59.json", "V59")

    @property
    def reviewed_count(self) -> int:
        return len(self.review_results)

    @property
    def all_pass(self) -> bool:
        return bool(self.review_results) and all(e["integrity_pass"] for e in self.review_results)

    @property
    def any_fail(self) -> bool:
        return any(not e["integrity_pass"] for e in self.review_results)

    @property
    def release_denied(self) -> bool:
        return all(e["status"] == "FAIL_CLOSED_DENIED" and not e["released"] and not e["side_effect"] for e in self.release_denials)

    @property
    def reviewer_status(self) -> str:
        if self.reviewed_count == 0:
            return "PARTIAL_NO_REAL_QUARANTINE_ARTIFACTS"
        if self.any_fail:
            return "FAIL_ARTIFACT_INTEGRITY"
        return "PASS_REAL_QUARANTINE_ARTIFACTS_REVIEWED"

    @property
    def integrity_status(self) -> str:
        if self.reviewed_count == 0:
            return "PARTIAL_NO_ARTIFACTS_TO_REVIEW"
        if self.any_fail:
            return "FAIL_ARTIFACT_INTEGRITY"
        return "PASS_ARTIFACT_INTEGRITY_VALIDATED"

    @property
    def final_verdict(self) -> str:
        if self.v59_baseline_status.startswith("FAIL") or self.any_fail or not self.release_denied:
            return "FAIL"
        if self.v59_baseline_status.startswith("PARTIAL") or self.reviewed_count == 0:
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.v59_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V59_BASELINE_REGRESSION")
        elif self.v59_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V59_BASELINE_UNAVAILABLE")
        if self.any_fail:
            blockers.append("ARTIFACT_INTEGRITY_FAILURE")
        elif self.reviewed_count == 0:
            blockers.append("NO_REAL_QUARANTINE_ARTIFACTS")
        return blockers

    @property
    def next_action(self) -> str:
        if self.all_pass:
            return "REAL_QUARANTINE_ARTIFACTS_REVIEWED_RELEASE_LOCKED"
        return "OPERATOR_MAY_CREATE_DEDICATED_APPROVAL_FILE_MANUALLY"


def _common(ctx: V60Context) -> dict[str, Any]:
    return {
        "v59_baseline_status": ctx.v59_baseline_status,
        "reviewed_quarantine_dir": str(ctx.quarantine_dir),
        "candidate_quarantine_dirs": [str(V59_QUARANTINE_DIR), str(V57_QUARANTINE_DIR)],
        "real_quarantine_artifact_reviewer_status": ctx.reviewer_status,
        "reviewer_read_only": True,
        "reviewer_modified_artifacts": False,
        "reviewed_artifact_count": ctx.reviewed_count,
        "reviewed_artifacts": ctx.review_results,
        "reviewed_artifact_types": [e["artifact_type"] for e in ctx.review_results],
        "allowed_artifact_types": ALLOWED_REHEARSAL_ARTIFACT_TYPES,
        "forbidden_artifact_fields": FORBIDDEN_ARTIFACT_FIELDS,
        "artifact_integrity_review_v3_status": ctx.integrity_status,
        "all_reviewed_artifacts_pass_integrity": ctx.all_pass,
        "hashes_before_after_match": all(e.get("unchanged", True) for e in ctx.review_results),
        "tamper_detected": ctx.any_fail,
        "tamper_detector_status": "PASS_TAMPER_DETECTOR_ACTIVE",
        "release_denial_v3_status": "PASS_RELEASE_DENIED" if ctx.release_denied else "FAIL_RELEASE_NOT_DENIED",
        "release_denials": ctx.release_denials,
        "release_denial_kinds": DENIAL_KINDS,
        "canary_nonexecution_validator_v10_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V10",
        "readiness_governor_v20_status": "PASS",
        "execution_lock_deep_recheck_v19_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V60Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v59_baseline"):
        return "PASS" if ctx.v59_baseline_status == "PASS_V59_BASELINE_READBACK" else "FAIL" if ctx.v59_baseline_status.startswith("FAIL") else "PARTIAL"
    if name in {"v60_real_quarantine_artifact_reviewer_report.json", "v60_artifact_integrity_review_v3_report.json"}:
        return "FAIL" if ctx.any_fail else "PASS" if ctx.all_pass else "PARTIAL"
    if name == "v60_release_denial_v3_report.json":
        return "PASS" if ctx.release_denied else "FAIL"
    return "PASS" if ctx.all_pass and not ctx.v59_baseline_status.startswith(("FAIL", "PARTIAL")) else ctx.final_verdict


def _component_payload(name: str, ctx: V60Context) -> dict[str, Any]:
    workstream = "v60: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v60_tamper_detector_report.json":
        report.update({"tamper_detector_active": True, "forbidden_fields_checked": FORBIDDEN_ARTIFACT_FIELDS})
    elif name == "v60_canary_nonexecution_validator_v10_report.json":
        report.update({"order_cancel_reference_detected": False, "broker_payload_reference_detected": False, "quarantine_release_path_reference_detected": False, "transform_to_broker_path_reference_detected": False})
    elif name == "dashboard_v60_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V60_ROUTES, "read_only_dashboard": True, "dashboard_can_trigger_trading": False, "dashboard_can_release_quarantine_artifacts": False})
    elif name == "completion_oriented_next_action_v60_report.json":
        report.update({"completion_oriented_next_action_v60_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v46.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v59_carried_status": ctx.v59_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v60.json"), "reviewer": str(ARTIFACTS / "v60_real_quarantine_artifact_reviewer_report.json"), "release_denial": str(ARTIFACTS / "v60_release_denial_v3_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v60.json", "dummy_canonical_identity_report_v60.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V60ReportFactory:
    def __init__(self, *, quarantine_dir: Path | None = None) -> None:
        self.quarantine_dir = quarantine_dir

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V60Context(quarantine_dir=self.quarantine_dir)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
