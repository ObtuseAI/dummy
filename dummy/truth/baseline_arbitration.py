"""Require independent incumbent and market-prior baselines for claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cluster_statistics import TruthValidationError


@dataclass(frozen=True, slots=True)
class BaselineSet:
    incumbent_id: str
    market_prior_id: str
    candidate_id: str

    def __post_init__(self) -> None:
        values = (self.incumbent_id, self.market_prior_id, self.candidate_id)
        if any(not value.strip() for value in values) or len(set(values)) != 3:
            raise TruthValidationError(
                "candidate, incumbent, and market prior must be distinct"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "incumbent_id": self.incumbent_id,
            "market_prior_id": self.market_prior_id,
            "candidate_controls_its_baseline": False,
        }


__all__ = ["BaselineSet"]
