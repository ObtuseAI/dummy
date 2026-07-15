"""Emit deterministic Phase 6 memory, genome, and evolution evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.constitution import (  # noqa: E402
    protected_manifest_dict,
    protected_manifest_digest,
)
from dummy.evolution import (  # noqa: E402
    EVALUATOR_VERSION,
    evaluate_evolution_family,
)
from dummy.genome import (  # noqa: E402
    GeneCategory,
    MutationLevel,
    genome_catalog_manifest,
)
from dummy.memory import (  # noqa: E402
    GENESIS_HASH,
    EvidenceReality,
    MemoryKind,
)
from dummy.world_model.models import digest_json  # noqa: E402


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def memory_policy_manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": 1,
        "phase": 6,
        "memory_kinds": [item.value for item in MemoryKind],
        "evidence_realities": [item.value for item in EvidenceReality],
        "ledger": {
            "append_only": True,
            "hash_chained": True,
            "content_addressed_records": True,
            "causal_parents_must_preexist": True,
            "recorded_time_monotonic": True,
            "empty_head_hash": GENESIS_HASH,
        },
        "realized_truth_rules": {
            "settlement_requires_verified_provenance": True,
            "witnessed_fill_separate_from_simulation": True,
            "simulated_fill_realized_capital_pnl": False,
            "theory_never_promotion_eligible": True,
        },
        "performance_claim_supported": False,
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


def evolution_policy_manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": 1,
        "phase": 6,
        "evaluator_version": EVALUATOR_VERSION,
        "recursive_levels": [
            {"level": int(item), "name": item.name} for item in MutationLevel
        ],
        "gene_categories": [item.value for item in GeneCategory],
        "evaluation": {
            "event_cluster_purge": True,
            "selection_evidence_purge": True,
            "cluster_interval": "EVENT_CLUSTER_BOOTSTRAP",
            "one_sided_test": "EVENT_CLUSTER_SIGN_FLIP",
            "multiple_testing": "HOLM_BONFERRONI",
            "transfer_required": True,
            "deterministic_replay_required": True,
            "governance_preservation_required": True,
            "fill_truth_separate": True,
        },
        "mutation": {
            "source_edits_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "candidate_controls_evaluator": False,
            "protected_manifest_digest": protected_manifest_digest(),
        },
        "retirement_and_rollback": {
            "deterministic_records": True,
            "proposal_only_until_registry_integration": True,
            "authority_direction": "CONTRACTION_ONLY",
            "reversible_state_recorded": True,
            "last_healthy_state_recorded": True,
        },
        "promotion_authority": "HUMAN_ONLY",
        "execution_authority": False,
        "held_out_improvement_claim_supported": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    outputs = {
        "VNEXT_PROTECTED_SURFACES.json": protected_manifest_dict(),
        "VNEXT_PHASE6_MEMORY_POLICY.json": memory_policy_manifest(),
        "VNEXT_PHASE6_GENOME_CATALOG.json": genome_catalog_manifest(),
        "VNEXT_PHASE6_EVOLUTION_POLICY.json": evolution_policy_manifest(),
        "VNEXT_PHASE6_EVOLUTION_EVIDENCE.json": evaluate_evolution_family(()),
    }
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    print(
        json.dumps(
            {
                "outputs": [str(args.output_dir / name) for name in outputs],
                "evolution_candidate_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
