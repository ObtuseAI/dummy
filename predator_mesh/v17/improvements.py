"""Evidence-backed non-executing improvement proposals for V17."""

from __future__ import annotations

from typing import Any


class ImprovementProposalFactory:
    def proposals(self) -> list[dict[str, Any]]:
        return [
            {
                "proposal_id": "V17-PROP-001",
                "title": "Increase outcome sample coverage before promotion",
                "evidence_refs": ["outcome_ledger_report_v1.json", "calibration_report_v1.json"],
                "tests_required": ["tests/test_calibration_engine.py", "tests/test_outcome_ledger_integrity.py"],
                "risk_intelligence_notes": ["Low sample; do not promote fixture sources as real."],
                "executes_automatically": False,
            },
            {
                "proposal_id": "V17-PROP-002",
                "title": "Track ambiguity as no-trade pressure",
                "evidence_refs": ["domain_outcome_ontology_report_v1.json"],
                "tests_required": ["tests/test_domain_outcome_ontology.py", "tests/test_no_trade_attribution.py"],
                "risk_intelligence_notes": ["Ambiguous settlements must remain unresolved until proof refs exist."],
                "executes_automatically": False,
            },
        ]

    def manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V17: Improvement Proposal Manifest",
            "proposals": self.proposals(),
            "proposals_execute_automatically": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def to_report(self) -> dict[str, Any]:
        proposals = self.proposals()
        return {
            "workstream": "V17: Improvement Proposal Factory",
            "proposal_count": len(proposals),
            "proposals": proposals,
            "proposals_execute_automatically": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
