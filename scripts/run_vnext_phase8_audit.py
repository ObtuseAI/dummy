"""Emit deterministic Phase 8 benchmark, claim, and promotion reviews."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.benchmarks import benchmark_catalog_manifest  # noqa: E402
from dummy.claims import (  # noqa: E402
    EvidenceRequirement,
    current_governance_evidence,
    review_claims,
)
from dummy.constitution import Authority, evaluate_mutation_proposal  # noqa: E402
from dummy.promotion import build_promotion_review  # noqa: E402
from dummy.world_model.models import digest_json  # noqa: E402
from scripts.run_vnext_phase6_audit import (  # noqa: E402
    evolution_policy_manifest,
    memory_policy_manifest,
)
from scripts.run_vnext_phase7_audit import build_outputs as phase7_outputs  # noqa: E402


FORBIDDEN_IMPORTS = (
    "dotenv",
    "execution",
    "kalshi",
    "live_firewall",
    "model_router.credential_source",
    "core.proof_authority",
    "core.proof_lock",
    "core.second_proof_lock",
    "core.second_proof_runner",
)


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _credential_import_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted((ROOT / "dummy").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if any(
                    module == prefix or module.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_IMPORTS
                ):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:{module}"
                    )
    return violations


def governance_evidence_manifest(
    *,
    phase7: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], frozenset[EvidenceRequirement]]:
    memory = memory_policy_manifest()
    evolution = evolution_policy_manifest()
    arena = phase7["VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json"]
    homeostasis = phase7["VNEXT_PHASE7_HOMEOSTASIS_POLICY.json"]
    mutation_paths = (
        "dummy/claims/evaluator.py",
        "dummy/promotion/review.py",
        "dummy/arenas/runner.py",
        "dummy/homeostasis/controller.py",
        "dummy/observatory/models.py",
    )
    mutation_checks = {
        path: not evaluate_mutation_proposal(
            [path], proposer_authority=Authority.RECOMMEND
        ).allowed
        for path in mutation_paths
    }
    import_violations = _credential_import_violations()
    checks = {
        EvidenceRequirement.FILL_TRUTH_SEPARATION: bool(
            memory["realized_truth_rules"]["witnessed_fill_separate_from_simulation"]
        )
        and not bool(
            memory["realized_truth_rules"]["simulated_fill_realized_capital_pnl"]
        ),
        EvidenceRequirement.EXECUTION_REALISM: bool(
            evolution["evaluation"]["fill_truth_separate"]
        )
        and not bool(evolution["mutation"]["runtime_application"]),
        EvidenceRequirement.DETERMINISTIC_REPLAY: arena["deterministic_count"]
        == arena["scenario_count"],
        EvidenceRequirement.GOVERNANCE_TESTS: all(mutation_checks.values()),
        EvidenceRequirement.AUTHORITY_NONEXPANSION: not bool(
            homeostasis["authority_expansion_allowed"]
        ),
        EvidenceRequirement.CREDENTIAL_ISOLATION: not import_violations,
    }
    verified = frozenset(requirement for requirement, passed in checks.items() if passed)
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 8,
        "checks": {item.value: checks[item] for item in sorted(checks, key=lambda item: item.value)},
        "mutation_protection": mutation_checks,
        "credential_import_violations": import_violations,
        "verified_requirements": sorted(item.value for item in verified),
        "candidate_controls_audit": False,
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body, verified


def build_outputs() -> dict[str, dict[str, Any]]:
    outputs = phase7_outputs()
    governance, verified = governance_evidence_manifest(phase7=outputs)
    claim_evidence = current_governance_evidence(verified_requirements=verified)
    claim_review = review_claims(claim_evidence)
    promotion_review = build_promotion_review(claim_review).to_dict()
    outputs.update(
        {
            "VNEXT_PHASE8_BENCHMARK_CATALOG.json": benchmark_catalog_manifest(),
            "VNEXT_PHASE8_GOVERNANCE_EVIDENCE.json": governance,
            "VNEXT_PHASE8_CLAIM_REVIEW.json": claim_review,
            "VNEXT_PHASE8_PROMOTION_REVIEW.json": promotion_review,
        }
    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    outputs = build_outputs()
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    claims = outputs["VNEXT_PHASE8_CLAIM_REVIEW.json"]
    print(
        json.dumps(
            {
                "outputs": [str(args.output_dir / name) for name in outputs],
                "performance_supported_count": claims["performance_supported_count"],
                "governance_supported_count": claims["governance_supported_count"],
                "material_improvement_established": claims[
                    "material_improvement_established"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
