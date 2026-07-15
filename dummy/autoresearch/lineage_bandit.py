"""Bandit allocation across lineages with greedy selection inside each arm."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from dummy.world_model.models import digest_json

from .models import AutoresearchValidationError


@dataclass(frozen=True, slots=True)
class LineageState:
    lineage_id: str
    strategy: str
    private_rewards: tuple[float, ...] = ()
    uncertainty: float = 1.0
    novelty: float = 1.0
    stagnation: float = 0.0
    transfer_potential: float = 0.0
    resource_efficiency: float = 1.0
    candidate_scores: tuple[tuple[str, float], ...] = ()
    champion_candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not self.lineage_id.strip() or not self.strategy.strip():
            raise AutoresearchValidationError("lineage identity is required")
        for field_name in (
            "uncertainty",
            "novelty",
            "stagnation",
            "transfer_potential",
            "resource_efficiency",
        ):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value < 0.0:
                raise AutoresearchValidationError(f"invalid lineage field: {field_name}")
        if any(not math.isfinite(float(value)) for value in self.private_rewards):
            raise AutoresearchValidationError("lineage rewards must be finite")
        if len({candidate for candidate, _ in self.candidate_scores}) != len(
            self.candidate_scores
        ):
            raise AutoresearchValidationError("lineage candidate IDs must be unique")

    @property
    def mean_reward(self) -> float:
        return (
            sum(self.private_rewards) / len(self.private_rewards)
            if self.private_rewards
            else 0.0
        )

    def greedy_candidate(self) -> str | None:
        if not self.candidate_scores:
            return self.champion_candidate_id
        return max(self.candidate_scores, key=lambda item: (item[1], item[0]))[0]


@dataclass(frozen=True, slots=True)
class LineageAllocation:
    allocation_id: str
    selected_lineage_id: str
    selected_parent_candidate_id: str | None
    arm_scores: tuple[tuple[str, float], ...]
    policy: str = "ucb_lineage_greedy_within_lineage_v1"

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "selected_lineage_id": self.selected_lineage_id,
            "selected_parent_candidate_id": self.selected_parent_candidate_id,
            "arm_scores": [list(item) for item in self.arm_scores],
            "policy": self.policy,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"allocation_id": self.allocation_id, **self.semantic_dict()}


def allocate_lineage(states: tuple[LineageState, ...]) -> LineageAllocation:
    if not states or len({item.lineage_id for item in states}) != len(states):
        raise AutoresearchValidationError("lineage arms must be non-empty and unique")
    total_trials = sum(len(item.private_rewards) for item in states)
    scores: list[tuple[str, float]] = []
    for state in states:
        if not state.private_rewards:
            score = 1_000_000.0 + state.novelty + state.uncertainty
        else:
            exploration = math.sqrt(
                2.0 * math.log(max(2, total_trials)) / len(state.private_rewards)
            )
            score = (
                state.mean_reward
                + exploration
                + 0.20 * state.uncertainty
                + 0.20 * state.novelty
                + 0.10 * state.stagnation
                + 0.20 * state.transfer_potential
                + 0.10 * state.resource_efficiency
            )
        scores.append((state.lineage_id, round(score, 12)))
    ordered_scores = tuple(sorted(scores))
    selected_id = max(scores, key=lambda item: (item[1], item[0]))[0]
    selected = next(item for item in states if item.lineage_id == selected_id)
    semantic = {
        "schema_version": 1,
        "selected_lineage_id": selected_id,
        "selected_parent_candidate_id": selected.greedy_candidate(),
        "arm_scores": [list(item) for item in ordered_scores],
        "policy": "ucb_lineage_greedy_within_lineage_v1",
    }
    return LineageAllocation(
        allocation_id=digest_json(semantic),
        selected_lineage_id=selected_id,
        selected_parent_candidate_id=selected.greedy_candidate(),
        arm_scores=ordered_scores,
    )


__all__ = ["LineageAllocation", "LineageState", "allocate_lineage"]
