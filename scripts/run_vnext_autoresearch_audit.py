"""Emit deterministic nested autoresearch policy and evidence artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.autoresearch.complexity_gate import (  # noqa: E402
    complexity_policy_manifest,
)
from dummy.autoresearch.context_distiller import (  # noqa: E402
    context_policy_manifest,
)
from dummy.autoresearch.ignition_test import evaluate_ignition  # noqa: E402
from dummy.autoresearch.orchestrator import lifecycle_manifest  # noqa: E402
from dummy.autoresearch.outer_researcher import (  # noqa: E402
    outer_researcher_manifest,
)
from dummy.autoresearch.private_evaluator import (  # noqa: E402
    private_evaluator_manifest,
)
from dummy.autoresearch.reward_hacking_detector import (  # noqa: E402
    reward_hacking_manifest,
)
from dummy.autoresearch.task_suite import (  # noqa: E402
    task_suite_policy_manifest,
)
from dummy.constitution import protected_manifest_digest  # noqa: E402
from dummy.world_model.models import digest_json  # noqa: E402


def autoresearch_policy_manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": 1,
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "name": "AIDE2_STYLE_FORECAST_RESEARCH_IMPROVEMENT_LOOP",
        "nested_loops": [
            {
                "level": 0,
                "purpose": "forecast_and_settle_markets",
                "authority": "SHADOW_AND_EXISTING_GOVERNED_RUNTIME_ONLY",
            },
            {
                "level": 1,
                "purpose": "improve_forecast_research_organisms",
                "authority": "PROPOSE_SIMULATE_EVALUATE",
            },
            {
                "level": 2,
                "purpose": "improve_how_organisms_are_improved",
                "authority": "PROPOSAL_ONLY_POLICY_GENOMES",
            },
            {
                "level": 3,
                "purpose": "test_whether_improvement_rate_accelerates",
                "authority": "OBSERVE_AND_REPORT_ONLY",
            },
        ],
        "evaluation_hierarchy": [
            "formal_invariants_and_deterministic_checks",
            "hidden_point_in_time_settlement_evidence",
            "external_held_out_generalization",
            "forward_paper_evidence",
            "independent_adversarial_models",
            "intrinsic_model_confidence",
        ],
        "components": {
            "outer_researcher": outer_researcher_manifest(),
            "task_suite": task_suite_policy_manifest(),
            "private_evaluator": private_evaluator_manifest(),
            "reward_hacking": reward_hacking_manifest(),
            "complexity": complexity_policy_manifest(),
            "context": context_policy_manifest(),
            "candidate_lifecycle": lifecycle_manifest(),
        },
        "protected_manifest_digest": protected_manifest_digest(),
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


def autoresearch_evidence_manifest() -> dict[str, object]:
    ignition = evaluate_ignition(()).to_dict()
    body: dict[str, object] = {
        "schema_version": 1,
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "mechanics_implemented": True,
        "genuine_private_candidate_trials": 0,
        "genuine_external_generalization_trials": 0,
        "forward_paper_candidate_settlements": 0,
        "ignition": ignition,
        "highest_supported_recursive_improvement_level": None,
        "status": "MECHANICS_VALIDATED_EMPIRICAL_GATES_OPEN",
        "performance_claim_supported": False,
        "self_improvement_claim_supported": False,
        "improved_improver_claim_supported": False,
        "accelerating_improvement_claim_supported": False,
        "live_readiness_changed": False,
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "execution_authority": False,
    }
    body["evidence_id"] = digest_json(body)
    return body


def build_outputs() -> dict[str, dict[str, object]]:
    return {
        "VNEXT_AUTORESEARCH_POLICY.json": autoresearch_policy_manifest(),
        "VNEXT_AUTORESEARCH_EVIDENCE.json": autoresearch_evidence_manifest(),
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    outputs = build_outputs()
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    print(
        json.dumps(
            {
                "outputs": [str(args.output_dir / name) for name in outputs],
                "genuine_private_candidate_trials": 0,
                "empirical_recursive_improvement_claim": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
