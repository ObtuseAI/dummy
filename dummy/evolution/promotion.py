"""Human-review proposal artifacts; evolution never promotes itself."""

from __future__ import annotations

from typing import Any, Mapping

from dummy.world_model.models import digest_json


def promotion_proposal(
    family_report: Mapping[str, Any],
    *,
    candidate_id: str,
) -> dict[str, Any]:
    matches = tuple(
        item
        for item in family_report.get("candidate_reports", ())
        if item.get("candidate_id") == candidate_id
    )
    if len(matches) != 1:
        raise ValueError("promotion proposal requires one evaluated candidate")
    report = matches[0]
    evidence_gate_passed = (
        report.get("verdict") == "HELD_OUT_IMPROVEMENT_SUPPORTED"
        and report.get("eligible_for_human_review") is True
    )
    body: dict[str, Any] = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "family_report_id": family_report["family_report_id"],
        "candidate_report_id": report["report_id"],
        "status": (
            "READY_FOR_EXPLICIT_HUMAN_REVIEW"
            if evidence_gate_passed
            else "BLOCKED_BY_EVIDENCE_GATES"
        ),
        "evidence_gate_passed": evidence_gate_passed,
        "eligible_for_human_review": evidence_gate_passed,
        "eligible_for_promotion": False,
        "automatic_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
        "execution_authority": False,
        "incumbent_modified": False,
        "applied": False,
        "required_next_action": "EXPLICIT_REVIEWED_HUMAN_CHANGE",
    }
    body["proposal_id"] = digest_json(body)
    return body


__all__ = ["promotion_proposal"]
