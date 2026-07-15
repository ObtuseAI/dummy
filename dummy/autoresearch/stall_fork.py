"""Deterministic stall-triggered champion forks into a different strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dummy.world_model.models import digest_json

from .lineage_bandit import LineageState
from .models import AutoresearchValidationError


@dataclass(frozen=True, slots=True)
class StallFork:
    fork_id: str
    source_lineage_id: str
    global_champion_candidate_id: str
    target_lineage_id: str
    target_strategy: str
    observed_window: tuple[float, ...]
    applied: bool = False

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source_lineage_id": self.source_lineage_id,
            "global_champion_candidate_id": self.global_champion_candidate_id,
            "target_lineage_id": self.target_lineage_id,
            "target_strategy": self.target_strategy,
            "observed_window": list(self.observed_window),
            "applied": self.applied,
            "automatic_promotion": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"fork_id": self.fork_id, **self.semantic_dict()}


def propose_stall_fork(
    stalled_lineage: LineageState,
    *,
    global_champion_candidate_id: str,
    target_lineage_id: str,
    target_strategy: str,
    window: int = 4,
    minimum_improvement: float = 0.0025,
) -> StallFork | None:
    if window < 2 or not global_champion_candidate_id.strip():
        raise AutoresearchValidationError("stall fork inputs are invalid")
    if target_lineage_id == stalled_lineage.lineage_id:
        raise AutoresearchValidationError("stall fork requires a distinct lineage")
    recent = stalled_lineage.private_rewards[-window:]
    if len(recent) < window:
        return None
    first_best = max(recent[: max(1, window // 2)])
    second_best = max(recent[max(1, window // 2) :])
    if second_best - first_best >= minimum_improvement:
        return None
    semantic = {
        "schema_version": 1,
        "source_lineage_id": stalled_lineage.lineage_id,
        "global_champion_candidate_id": global_champion_candidate_id,
        "target_lineage_id": target_lineage_id,
        "target_strategy": target_strategy,
        "observed_window": list(recent),
        "applied": False,
        "automatic_promotion": False,
    }
    return StallFork(
        fork_id=digest_json(semantic),
        source_lineage_id=stalled_lineage.lineage_id,
        global_champion_candidate_id=global_champion_candidate_id,
        target_lineage_id=target_lineage_id,
        target_strategy=target_strategy,
        observed_window=recent,
    )


__all__ = ["StallFork", "propose_stall_fork"]
