"""Fail-closed mutation boundaries for recursive research."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Iterable

from dummy.constitution.authority import Authority


class SurfaceCategory(str, Enum):
    ADVERSARIAL_EVALUATION = "adversarial_evaluation"
    CAUSAL_REPLAY = "causal_replay"
    CONSTITUTION = "constitution"
    CREDENTIALS = "credentials"
    EXECUTION = "execution"
    FILL_TRUTH = "fill_truth"
    OBSERVABILITY = "observability"
    PROMOTION = "promotion"
    SETTLEMENT_TRUTH = "settlement_truth"


@dataclass(frozen=True, slots=True)
class ProtectedSurface:
    path: str
    category: SurfaceCategory
    reason: str


PROTECTED_SURFACES = (
    ProtectedSurface(
        "dummy/constitution",
        SurfaceCategory.CONSTITUTION,
        "Evolution cannot modify its authority or evaluator protections.",
    ),
    ProtectedSurface(
        "autonomy/ledger.py",
        SurfaceCategory.SETTLEMENT_TRUTH,
        "Append-only observations, decisions, fills, and outcomes are authoritative.",
    ),
    ProtectedSurface(
        "autonomy/reconciler.py",
        SurfaceCategory.SETTLEMENT_TRUTH,
        "Settlement reconciliation must remain outside the mutation surface.",
    ),
    ProtectedSurface(
        "autonomy/backtest.py",
        SurfaceCategory.SETTLEMENT_TRUTH,
        "The primary evidence evaluator cannot be changed by its candidates.",
    ),
    ProtectedSurface(
        "autonomy/evolution_lab.py",
        SurfaceCategory.SETTLEMENT_TRUTH,
        "Candidate evaluation and held-out fold rules are protected.",
    ),
    ProtectedSurface(
        "dummy/memory",
        SurfaceCategory.CAUSAL_REPLAY,
        "Append-only vNext memory, provenance, and hash-chain rules are authoritative.",
    ),
    ProtectedSurface(
        "dummy/truth",
        SurfaceCategory.CAUSAL_REPLAY,
        "Cluster inference and multiple-testing correction cannot be candidate-controlled.",
    ),
    ProtectedSurface(
        "dummy/genome/schema.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "Genome identity and authority fields are outside the mutation surface.",
    ),
    ProtectedSurface(
        "dummy/genome/registry.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "Genome lineage registration and scope isolation are externally governed.",
    ),
    ProtectedSurface(
        "dummy/genome/lineage.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "Candidate lineages cannot rewrite their ancestry.",
    ),
    ProtectedSurface(
        "dummy/genome/fitness.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "Candidates cannot alter the contract that records their held-out fitness.",
    ),
    ProtectedSurface(
        "dummy/genome/mutation.py",
        SurfaceCategory.CONSTITUTION,
        "Mutation levels and constitutional checks cannot be self-modified.",
    ),
    ProtectedSurface(
        "dummy/genome/retirement.py",
        SurfaceCategory.PROMOTION,
        "Retirement evidence and reversibility rules cannot be weakened by candidates.",
    ),
    ProtectedSurface(
        "dummy/evolution/evaluator.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "The external vNext evaluator cannot be changed by evaluated candidates.",
    ),
    ProtectedSurface(
        "dummy/evolution/candidate.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "Held-out purge and point-in-time input rules cannot be candidate-controlled.",
    ),
    ProtectedSurface(
        "dummy/evolution/archive.py",
        SurfaceCategory.CAUSAL_REPLAY,
        "Archived evolutionary evidence is immutable to candidates.",
    ),
    ProtectedSurface(
        "dummy/evolution/promotion.py",
        SurfaceCategory.PROMOTION,
        "Evolution produces human-review proposals and cannot grant promotion.",
    ),
    ProtectedSurface(
        "dummy/evolution/rollback.py",
        SurfaceCategory.PROMOTION,
        "Rollback remains a deterministic contraction-only governance action.",
    ),
    ProtectedSurface(
        "dummy/arenas",
        SurfaceCategory.ADVERSARIAL_EVALUATION,
        "Candidates cannot rewrite their adversarial scenarios or arena judge.",
    ),
    ProtectedSurface(
        "dummy/homeostasis",
        SurfaceCategory.CONSTITUTION,
        "Candidates cannot weaken health thresholds or expand intervention authority.",
    ),
    ProtectedSurface(
        "dummy/observatory",
        SurfaceCategory.OBSERVABILITY,
        "Evidence-linked projections cannot be rewritten by evaluated candidates.",
    ),
    ProtectedSurface(
        "dummy/benchmarks",
        SurfaceCategory.CAUSAL_REPLAY,
        "Candidates cannot redefine the benchmark on which they are judged.",
    ),
    ProtectedSurface(
        "dummy/claims",
        SurfaceCategory.CAUSAL_REPLAY,
        "Required internal claims and their evidence floor are externally governed.",
    ),
    ProtectedSurface(
        "dummy/promotion",
        SurfaceCategory.PROMOTION,
        "Lifecycle gates and human-only review packets cannot be candidate-controlled.",
    ),
    ProtectedSurface(
        "autonomy/promotion.py",
        SurfaceCategory.PROMOTION,
        "Promotion is human-only and automatic changes may only demote.",
    ),
    ProtectedSurface(
        "autonomy/canary.py",
        SurfaceCategory.PROMOTION,
        "Canary and scale evidence floors may not be weakened.",
    ),
    ProtectedSurface(
        "proof/ledger.py",
        SurfaceCategory.FILL_TRUTH,
        "Execution proof records are authoritative evidence.",
    ),
    ProtectedSurface(
        "live_firewall",
        SurfaceCategory.EXECUTION,
        "All live orders must remain behind the hardened firewall.",
    ),
    ProtectedSurface(
        "execution",
        SurfaceCategory.EXECUTION,
        "Execution adapters are outside recursive research authority.",
    ),
    ProtectedSurface(
        "core/proof_authority.py",
        SurfaceCategory.EXECUTION,
        "Operator authority is explicit, typed, and externally granted.",
    ),
    ProtectedSurface(
        "core/proof_lock.py",
        SurfaceCategory.EXECUTION,
        "Proof consumption locks must remain fail closed.",
    ),
    ProtectedSurface(
        "core/second_proof_lock.py",
        SurfaceCategory.EXECUTION,
        "One-shot authority locks cannot be mutated by research.",
    ),
    ProtectedSurface(
        "core/second_proof_runner.py",
        SurfaceCategory.EXECUTION,
        "The live proof runner is isolated from forecasting evolution.",
    ),
    ProtectedSurface(
        "configs/live_submit.json",
        SurfaceCategory.EXECUTION,
        "Live-submit state requires explicit operator action.",
    ),
    ProtectedSurface(
        "configs/caps.json",
        SurfaceCategory.EXECUTION,
        "Capital and order caps are operator-controlled.",
    ),
    ProtectedSurface(
        "core/secret_guard.py",
        SurfaceCategory.CREDENTIALS,
        "Secret registration and redaction are protected.",
    ),
    ProtectedSurface(
        "model_router/credential_source.py",
        SurfaceCategory.CREDENTIALS,
        "Credential discovery is not available to research agents.",
    ),
    ProtectedSurface(
        "kalshi/client.py",
        SurfaceCategory.CREDENTIALS,
        "Authenticated broker transport remains outside research authority.",
    ),
)

EVOLVABLE_ROOTS = (
    "dummy/agents",
    "dummy/organisms",
    "dummy/forecasting",
    "dummy/world_model",
    "dummy/adversarial",
    "dummy/metacognition",
    "dummy/shadows",
    "dummy/genome",
    "dummy/evolution",
    "autonomy/signals",
    "autonomy/specialists",
)


@dataclass(frozen=True, slots=True)
class MutationDecision:
    allowed: bool
    normalized_paths: tuple[str, ...]
    blocked_paths: tuple[str, ...]
    reasons: tuple[str, ...]


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    candidate = PurePosixPath(normalized)
    if not normalized or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe repository path: {path!r}")
    return candidate.as_posix().rstrip("/")


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def evaluate_mutation_proposal(
    paths: Iterable[str],
    *,
    proposer_authority: Authority,
) -> MutationDecision:
    """Evaluate an automatic mutation proposal.

    Unknown roots fail closed.  Human-reviewed source changes occur outside
    this API; this function never grants an exception for protected surfaces.
    """

    normalized_paths = tuple(sorted({_normalize_path(path) for path in paths}))
    if not normalized_paths:
        return MutationDecision(False, (), (), ("empty_mutation_proposal",))

    blocked: list[str] = []
    reasons: list[str] = []

    if proposer_authority > Authority.RECOMMEND:
        reasons.append("mutation_proposer_exceeds_recommend_authority")

    for path in normalized_paths:
        surface = next(
            (item for item in PROTECTED_SURFACES if _under(path, item.path)),
            None,
        )
        if surface is not None:
            blocked.append(path)
            reasons.append(f"protected:{surface.category.value}:{surface.path}")
            continue
        if not any(_under(path, root) for root in EVOLVABLE_ROOTS):
            blocked.append(path)
            reasons.append(f"outside_evolvable_roots:{path}")

    return MutationDecision(
        allowed=not blocked and not reasons,
        normalized_paths=normalized_paths,
        blocked_paths=tuple(sorted(set(blocked))),
        reasons=tuple(sorted(set(reasons))),
    )


def protected_manifest_dict() -> dict[str, object]:
    return {
        "schema_version": 1,
        "promotion_authority": "HUMAN_ONLY",
        "automatic_mutation_authority": "RECOMMEND_MAXIMUM",
        "protected_surfaces": [
            {
                "path": surface.path,
                "category": surface.category.value,
                "reason": surface.reason,
            }
            for surface in PROTECTED_SURFACES
        ],
        "evolvable_roots": list(EVOLVABLE_ROOTS),
    }


def protected_manifest_digest() -> str:
    payload = json.dumps(
        protected_manifest_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
