"""Emit deterministic Phase 5 policy and held-out evidence reports."""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.metacognition import (  # noqa: E402
    ConfidenceDecomposition,
    KnowledgeBoundary,
    MetacognitiveEvaluationCase,
    abstention_value_report,
    confidence_calibration_report,
    resource_efficiency_report,
    unavailable_meta_calibration,
)
from dummy.shadows import (  # noqa: E402
    REVIEWED_MARKET_PRIOR_FLOOR,
    GuardAction,
    GuardKind,
)
from dummy.synthesis import FamilyCapPolicy  # noqa: E402
from dummy.world_model.models import digest_json  # noqa: E402


GUARDS = (
    GuardKind.AUTHORITY,
    GuardKind.CONFIDENCE,
    GuardKind.DUPLICATION,
    GuardKind.LEAKAGE,
    GuardKind.MARKET_PRIOR,
    GuardKind.PROVENANCE,
    GuardKind.REGIME,
    GuardKind.RESOURCE,
)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _cases(path: Path | None) -> tuple[MetacognitiveEvaluationCase, ...]:
    if path is None:
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("evaluation input must be a JSON list")
    return tuple(MetacognitiveEvaluationCase.from_dict(item) for item in raw)


def control_policy_manifest() -> dict[str, object]:
    policy = FamilyCapPolicy(market_prior_floor=REVIEWED_MARKET_PRIOR_FLOOR)
    calibration = unavailable_meta_calibration()
    body: dict[str, object] = {
        "schema_version": 1,
        "phase": 5,
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "implementation_status": "IMPLEMENTED_VALIDATED_EVIDENCE_GATE_PENDING",
        "guards": list(GUARDS),
        "allowed_guard_actions": [action.name for action in GuardAction],
        "guard_authority": "CONTRACTION_ONLY",
        "forbidden_guard_actions": [
            "increase_influence",
            "increase_confidence",
            "grant_execution_authority",
            "grant_promotion_authority",
            "increase_resource_budget",
        ],
        "synthesis": {
            "policy_version": policy.policy_version,
            "market_prior_floor": policy.market_prior_floor,
            "non_market_family_cap": policy.non_market_family_cap,
            "uncalibrated_advisory_cap": policy.uncalibrated_advisory_cap,
            "stale_source_weight": 0.0,
            "alias_deduplication_key": "family_id",
            "disagreement_response": "WIDEN_UNCERTAINTY",
        },
        "metacognition": {
            "confidence_components": [
                item.name for item in fields(ConfidenceDecomposition)
            ],
            "confidence_aggregation": "minimum_critical_component",
            "knowledge_boundary_states": [item.value for item in KnowledgeBoundary],
            "calibration": calibration.to_dict(),
            "uncalibrated_control": "SHADOW_ONLY_EXCEPT_SAFETY_CONTRACTION",
        },
        "information_gain": {
            "status": "UNCALIBRATED_PROXY",
            "unknown_compute_response": "REFUSE_UTILITY_CLAIM_AND_NARROW_SCOPE",
        },
        "execution_authority": False,
        "promotion_authority": "HUMAN_ONLY",
        "performance_claim_supported": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--minimum-cases", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    cases = _cases(args.cases)
    outputs = {
        "VNEXT_PHASE5_CONTROL_POLICY.json": control_policy_manifest(),
        "VNEXT_PHASE5_ABSTENTION_VALUE.json": abstention_value_report(
            cases,
            minimum_cases=args.minimum_cases,
        ),
        "VNEXT_PHASE5_RESOURCE_EFFICIENCY.json": resource_efficiency_report(
            cases,
            minimum_cases=args.minimum_cases,
        ),
        "VNEXT_PHASE5_METACOGNITION_CALIBRATION.json": (
            confidence_calibration_report(
                cases,
                minimum_cases=args.minimum_cases,
            )
        ),
    }
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    print(
        json.dumps(
            {
                "case_count": len(cases),
                "outputs": [str(args.output_dir / name) for name in outputs],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
