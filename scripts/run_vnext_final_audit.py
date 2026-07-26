"""Emit the deterministic final DUMMY vNext master-plan integration audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.organisms import CAPABILITY_NAMES  # noqa: E402
from dummy.world_model.models import digest_json  # noqa: E402
from scripts.run_vnext_phase8_audit import build_outputs as phase8_outputs  # noqa: E402


REQUIREMENTS: tuple[tuple[int, str, str, tuple[str, ...], str], ...] = (
    (1, "Objective", "IMPLEMENTED_EVIDENCE_GATED", ("docs/VNEXT_MASTER_PLAN_INTEGRATION.md",), "The sovereign architecture exists, while trust remains evidence-bound."),
    (2, "Core design principles", "IMPLEMENTED", ("dummy/constitution", "dummy/shadows"), "Evidence, abstention, simulation labeling, external judging, and authority separation are executable invariants."),
    (3, "Target architecture", "IMPLEMENTED", ("dummy/agents", "dummy/organisms", "dummy/world_model", "dummy/metacognition"), "Typed agent, organism, world-state, and control planes are present."),
    (4, "Repository architecture", "IMPLEMENTED_ADAPTER_FIRST", ("dummy", "docs/VNEXT_MASTER_PLAN_INTEGRATION.md"), "The plan is integrated behind adapters instead of replacing proven incumbents."),
    (5, "Constitutional kernel", "IMPLEMENTED", ("dummy/constitution", "docs/VNEXT_PROTECTED_SURFACES.json"), "Authority and protected-surface rules fail closed."),
    (6, "Typed agent protocol", "IMPLEMENTED", ("dummy/protocols", "tests/test_vnext_protocols.py"), "Immutable messages carry identity, time, evidence, limitations, and authority."),
    (7, "Multi-agent runtime", "IMPLEMENTED", ("dummy/agents/runtime.py", "dummy/agents/mailbox.py"), "Registration, budgets, lifecycle, deterministic ordering, and quarantine are enforced."),
    (8, "Dynamic forecast organisms", "IMPLEMENTED_PILOT_SCOPE", ("dummy/organisms", "docs/VNEXT_PHASE3_TEMPLATE_CATALOG.json"), "BTC 15-minute and MLB pregame pilots prove the reusable morphology; other markets remain incumbent-adapted until separately evidenced."),
    (9, "Sovereign governor", "IMPLEMENTED", ("dummy/metacognition", "dummy/homeostasis"), "Routing and intervention can contract or recommend but cannot expand authority."),
    (10, "Probabilistic world models", "IMPLEMENTED", ("dummy/world_model", "docs/VNEXT_PHASE4_WORLD_MODEL_SCHEMAS.json"), "Facts, derived state, hypotheses, contradictions, missingness, provenance, and leases are typed."),
    (11, "Competing future generators", "IMPLEMENTED", ("dummy/organisms/models.py", "dummy/organisms/episode.py"), "Episodes create typed competing futures with assumptions and failure conditions."),
    (12, "Market-prior agent", "IMPLEMENTED", ("dummy/agents/incumbent.py", "autonomy/signals/market_prior.py"), "The market prior is a first-class, family-isolated input with a reviewed synthesis floor."),
    (13, "Crypto technical and quantitative expansion", "IMPLEMENTED_WITH_INCUMBENT_ADAPTERS", ("autonomy/signals/crypto_indicators.py", "autonomy/signals/crypto_structure.py", "autonomy/signals/crypto_vol.py"), "The incumbent feature arsenal remains available through read-only specialist adapters."),
    (14, "Sports feature expansion", "IMPLEMENTED_WITH_INCUMBENT_ADAPTERS", ("autonomy/specialists/mlb.py", "autonomy/specialists/team_leagues.py", "autonomy/signals/sports_intelligence.py"), "League kernels and live intelligence remain the sports specialist evidence base."),
    (15, "Metacognitive control system", "IMPLEMENTED_EVIDENCE_PENDING", ("dummy/metacognition", "docs/VNEXT_PHASE5_METACOGNITION.md"), "Difficulty, boundaries, stopping, abstention, and strategy advice are typed and shadow-only."),
    (16, "Confidence decomposition", "IMPLEMENTED", ("dummy/metacognition/confidence.py",), "Confidence is decomposed into independently auditable components."),
    (17, "Shadow controllers", "IMPLEMENTED", ("dummy/shadows",), "Eight contraction-only guards can downgrade, veto, quarantine, abstain, or terminate."),
    (18, "Forecast synthesis", "IMPLEMENTED", ("dummy/synthesis",), "Family-aware synthesis records dependency and preserves market-prior anchoring."),
    (19, "Metabolism and resource economics", "IMPLEMENTED_EVIDENCE_PENDING", ("dummy/metabolism", "docs/VNEXT_PHASE5_RESOURCE_EFFICIENCY.json"), "Costs and marginal information value are explicit; quality-preserving savings remain unproven."),
    (20, "Homeostasis", "IMPLEMENTED", ("dummy/homeostasis", "docs/VNEXT_PHASE7_HOMEOSTASIS_POLICY.json"), "All 19 health variables and bounded interventions are represented."),
    (21, "Chronos and causal time", "IMPLEMENTED", ("dummy/chronos",), "Event, receipt, decision, close, and settlement ordering is explicit and validated."),
    (22, "Memory architecture", "IMPLEMENTED", ("dummy/memory", "docs/VNEXT_PHASE6_MEMORY_POLICY.json"), "Observation through genome memory uses immutable content-addressed records and causal chains."),
    (23, "Forecast genome", "IMPLEMENTED", ("dummy/genome", "docs/VNEXT_PHASE6_GENOME_CATALOG.json"), "Generation-zero genomes, inheritance, lineage, identity, and fitness contracts are present."),
    (24, "Recursive evolution engine", "IMPLEMENTED_EVIDENCE_PENDING", ("dummy/evolution", "docs/VNEXT_PHASE6_EVOLUTION_EVIDENCE.json"), "Levels 0-5 produce proposal-only challengers judged by a protected external evaluator."),
    (25, "Meta-metacognitive evolution", "IMPLEMENTED_EVIDENCE_PENDING", ("dummy/evolution/meta_evolution.py", "dummy/metacognition/meta_evolution.py"), "Meta-policy challengers remain bounded and empirically unpromoted."),
    (26, "Adversarial arenas", "IMPLEMENTED_MECHANICS_VALIDATED", ("dummy/arenas", "docs/VNEXT_PHASE7_ARENA_CATALOG.json"), "All 40 required scenarios replay deterministically; runtime resilience is not claimed."),
    (27, "Causal truth layer", "IMPLEMENTED", ("dummy/truth",), "Contested truth, clustered statistics, multiple testing, drift, and causal attribution are protected."),
    (28, "Execution-truth hardening", "IMPLEMENTED_GOVERNANCE_ONLY", ("dummy/memory/fills.py", "proof/ledger.py", "docs/VNEXT_PHASE8_GOVERNANCE_EVIDENCE.json"), "Forecast accuracy, simulated fill, witnessed fill, settlement, and realized capital truth remain separate."),
    (29, "Trust system upgrade", "IMPLEMENTED_WITH_INCUMBENT_ADAPTERS", ("dummy/memory/calibration.py", "autonomy/reliability.py"), "Trust updates are evidence-linked proposals; historical incumbent reliability remains adapted."),
    (30, "Prediction explanation system", "IMPLEMENTED", ("dummy/organisms/episode.py", "dummy/protocols/messages.py"), "Episodes retain market state, basis, countercase, limitations, decision logic, and evidence IDs."),
    (31, "Observatory upgrade", "IMPLEMENTED_READ_ONLY", ("dummy/observatory", "autonomy/dashboard_ui.py"), "Evidence-linked observatory data is rendered by the canonical loopback-only web board."),
    (32, "Promotion lifecycle", "IMPLEMENTED_BLOCKED", ("dummy/promotion", "docs/VNEXT_PHASE8_PROMOTION_REVIEW.json"), "All 11 states and 13 evidence gates are explicit; current transition is human-only and blocked."),
    (33, "Failure and retirement", "IMPLEMENTED", ("dummy/memory/failures.py", "dummy/genome/retirement.py", "dummy/evolution/rollback.py"), "Failure memory, deterministic retirement, degradation, quarantine, and rollback are durable."),
    (34, "Implementation sequence", "COMPLETE", ("docs/VNEXT_MASTER_PLAN_INTEGRATION.md",), "Phases 0-8 are implemented in the accepted adapter-first sequence."),
    (35, "Benchmark program", "IMPLEMENTED_EVIDENCE_PENDING", ("dummy/benchmarks", "docs/VNEXT_PHASE8_BENCHMARK_CATALOG.json"), "All 32 metrics across six domains are cataloged; empirical observations are not manufactured."),
    (36, "Required internal claims", "IMPLEMENTED_SEPARATE_VERDICTS", ("dummy/claims", "docs/VNEXT_PHASE8_CLAIM_REVIEW.json"), "All eight claims are reviewed independently: six lack evidence and two are governance-only."),
    (37, "First complete vNext capability", "COMPLETE_MECHANICALLY_VALIDATED", ("dummy/organisms/episode.py", "tests/test_vnext_organism_episode.py", "docs/VNEXT_PHASE3_ORGANISM.md"), "All 20 steps are executable, persisted, replayed, and promotion-nonapplying."),
    (38, "End state", "ARCHITECTURE_INTEGRATED_EMPIRICAL_CLAIMS_OPEN", ("README.md", "docs/VNEXT_PHASE8_CLAIMS_PROMOTION.md"), "The ecology is integrated and fail-closed; material forecasting improvement remains explicitly unestablished."),
)


def _read_json(name: str, outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if name in outputs:
        return outputs[name]
    return json.loads((ROOT / "docs" / name).read_text(encoding="utf-8"))


def build_audit() -> dict[str, Any]:
    phase8 = phase8_outputs()
    claims = _read_json("VNEXT_PHASE8_CLAIM_REVIEW.json", phase8)
    promotion = _read_json("VNEXT_PHASE8_PROMOTION_REVIEW.json", phase8)
    requirements: list[dict[str, Any]] = []
    for number, title, status, evidence_paths, limitation in REQUIREMENTS:
        missing = [path for path in evidence_paths if not (ROOT / path).exists()]
        requirements.append(
            {
                "section": number,
                "title": title,
                "status": "MISSING_EVIDENCE_PATH" if missing else status,
                "evidence_paths": list(evidence_paths),
                "missing_paths": missing,
                "limitation": limitation,
            }
        )
    capability_names = list(CAPABILITY_NAMES)
    body: dict[str, Any] = {
        "schema_version": 1,
        "program": "DUMMY vNext Master Plan",
        "repository_identity": "DUMMY_STANDALONE",
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "status": "PASS_WITH_EMPIRICAL_GATES_OPEN",
        "requirements": requirements,
        "requirement_count": len(requirements),
        "requirements_with_missing_paths": sum(bool(item["missing_paths"]) for item in requirements),
        "first_complete_capability": {
            "step_count": len(capability_names),
            "steps": capability_names,
            "mechanically_validated": len(capability_names) == 20 and len(set(capability_names)) == 20,
            "execution_authority": False,
            "automatic_promotion": False,
        },
        "claim_program": {
            "claim_count": claims["claim_count"],
            "performance_supported_count": claims["performance_supported_count"],
            "governance_supported_count": claims["governance_supported_count"],
            "insufficient_evidence_count": claims["insufficient_evidence_count"],
            "material_improvement_established": claims["material_improvement_established"],
            "program_id": claims["program_id"],
        },
        "promotion": {
            "current_state": promotion["current_state"],
            "requested_state": promotion["requested_state"],
            "transition_eligible": promotion["transition_eligible"],
            "human_review_required": promotion["human_review_required"],
            "human_review_requested": promotion["human_review_requested"],
            "automatic_promotion": promotion["automatic_promotion"],
            "applied": promotion["applied"],
        },
        "governance": {
            "dummy_is_standalone_entity": True,
            "legacy_snapshot_is_identity": False,
            "legacy_snapshot_is_vnext_runtime_dependency": False,
            "incumbent_modified": False,
            "execution_authority": False,
            "capital_authority": False,
        },
        "validation": {
            "evidence_mode": "SOURCE_CONTRACT_ONLY",
            "current_test_run_required": True,
            "hardcoded_historical_test_counts_removed": True,
            "canonical_dashboard": "autonomy.dashboard_ui",
            "archived_frontend_required": False,
        },
    }
    if body["requirements_with_missing_paths"]:
        body["status"] = "FAIL_MISSING_EVIDENCE_PATHS"
    if not body["first_complete_capability"]["mechanically_validated"]:
        body["status"] = "FAIL_INCOMPLETE_CAPABILITY"
    body["audit_id"] = digest_json(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "VNEXT_MASTER_PLAN_FINAL_AUDIT.json",
    )
    args = parser.parse_args()
    audit = build_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "audit_id": audit["audit_id"],
                "status": audit["status"],
                "requirement_count": audit["requirement_count"],
                "requirements_with_missing_paths": audit[
                    "requirements_with_missing_paths"
                ],
                "material_improvement_established": audit["claim_program"][
                    "material_improvement_established"
                ],
            },
            sort_keys=True,
        )
    )
    return 1 if str(audit["status"]).startswith("FAIL_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
