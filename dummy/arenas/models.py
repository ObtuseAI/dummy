"""Immutable scenario and replay contracts for Phase 7 adversarial arenas."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from dummy.constitution import Authority
from dummy.world_model.models import digest_json


class ArenaDomain(str, Enum):
    FORECAST = "forecast"
    SPORTS = "sports"
    CRYPTO = "crypto"
    METACOGNITIVE = "metacognitive"


class ArenaCategory(str, Enum):
    ADVERSARIAL = "adversarial"
    CALIBRATION = "calibration"
    DRIFT = "drift"
    EXECUTION = "execution"
    LEAKAGE = "leakage"
    LIQUIDITY = "liquidity"
    MARKET_PRIOR = "market_prior"
    META = "meta"
    REGIME = "regime"


class StressSignal(str, Enum):
    CONCENTRATION = "concentration"
    DATA_INTEGRITY = "data_integrity"
    EXECUTION_REALISM = "execution_realism"
    LEAKAGE = "leakage"
    LIQUIDITY = "liquidity"
    MARKET_PRIOR_CONFLICT = "market_prior_conflict"
    METACOGNITIVE = "metacognitive"
    REGIME_SHIFT = "regime_shift"
    STALE_OR_MISSING = "stale_or_missing"
    VOLATILITY_SHOCK = "volatility_shock"


class ArenaResponse(str, Enum):
    ABSTAIN = "abstain"
    CAP_INFLUENCE = "cap_influence"
    INCREASE_MARKET_ANCHOR = "increase_market_anchor"
    MARK_EXECUTION_IRRELEVANT = "mark_execution_irrelevant"
    QUARANTINE = "quarantine"
    REDUCE_RESOURCE_BUDGET = "reduce_resource_budget"
    REQUEST_EVIDENCE = "request_evidence"
    REQUEST_REFRESH = "request_refresh"
    VETO = "veto"
    WIDEN_UNCERTAINTY = "widen_uncertainty"


@dataclass(frozen=True, slots=True)
class ArenaScenario:
    scenario_id: str
    name: str
    domain: ArenaDomain
    category: ArenaCategory
    signal: StressSignal
    severity: float
    expected_responses: tuple[ArenaResponse, ...]
    evidence_ids: tuple[str, ...]
    empirical: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("arena scenario name must be non-empty")
        severity = float(self.severity)
        if not math.isfinite(severity) or not 0.0 < severity <= 1.0:
            raise ValueError("arena severity must be in (0, 1]")
        responses = tuple(sorted(self.expected_responses, key=lambda item: item.value))
        evidence_ids = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not responses or len(responses) != len(set(responses)):
            raise ValueError("arena scenario requires unique expected responses")
        if (
            not evidence_ids
            or any(not item for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise ValueError("arena scenario requires evidence IDs")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "expected_responses", responses)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        if self.empirical:
            raise ValueError("checked-in Phase 7 scenarios are mechanical, not empirical")
        if self.scenario_id != digest_json(self.semantic_dict()):
            raise ValueError("arena scenario ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "name": self.name,
            "domain": self.domain.value,
            "category": self.category.value,
            "signal": self.signal.value,
            "severity": self.severity,
            "expected_responses": [item.value for item in self.expected_responses],
            "evidence_ids": list(self.evidence_ids),
            "empirical": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"scenario_id": self.scenario_id, **self.semantic_dict()}


@dataclass(frozen=True, slots=True)
class ArenaInput:
    forecast_probability: float
    market_prior: float
    uncertainty: float
    evidence_ids: tuple[str, ...]
    authority: Authority = Authority.SIMULATE

    def __post_init__(self) -> None:
        for field_name in ("forecast_probability", "market_prior", "uncertainty"):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("arena input probabilities must be in [0, 1]")
            object.__setattr__(self, field_name, value)
        evidence_ids = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if (
            not evidence_ids
            or any(not item for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise ValueError("arena input requires evidence IDs")
        if self.authority > Authority.SIMULATE:
            raise ValueError("arena authority cannot exceed SIMULATE")
        object.__setattr__(self, "evidence_ids", evidence_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "forecast_probability": self.forecast_probability,
            "market_prior": self.market_prior,
            "uncertainty": self.uncertainty,
            "evidence_ids": list(self.evidence_ids),
            "authority": self.authority.name,
        }


@dataclass(frozen=True, slots=True)
class ArenaResult:
    result_id: str
    scenario_id: str
    input_digest: str
    responses: tuple[ArenaResponse, ...]
    stressed_probability: float
    stressed_uncertainty: float
    evidence_ids: tuple[str, ...]
    authority_before: Authority
    authority_after: Authority
    passed: bool
    empirical_claim_supported: bool = False

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or len(self.input_digest) != 64:
            raise ValueError("arena result requires scenario and input identities")
        responses = tuple(sorted(self.responses, key=lambda item: item.value))
        evidence_ids = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not responses or len(responses) != len(set(responses)):
            raise ValueError("arena result requires unique responses")
        if (
            not evidence_ids
            or any(not item for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise ValueError("arena result requires unique evidence IDs")
        for value in (self.stressed_probability, self.stressed_uncertainty):
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError("arena result probabilities must be in [0, 1]")
        if self.authority_after > self.authority_before:
            raise ValueError("arena result expanded authority")
        if self.authority_after > Authority.SIMULATE:
            raise ValueError("arena result exceeds research authority")
        if self.empirical_claim_supported:
            raise ValueError("mechanical arena replay cannot support an empirical claim")
        object.__setattr__(self, "responses", responses)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        if self.result_id != digest_json(self.semantic_dict()):
            raise ValueError("arena result ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scenario_id": self.scenario_id,
            "input_digest": self.input_digest,
            "responses": [item.value for item in self.responses],
            "stressed_probability": self.stressed_probability,
            "stressed_uncertainty": self.stressed_uncertainty,
            "evidence_ids": list(self.evidence_ids),
            "authority_before": self.authority_before.name,
            "authority_after": self.authority_after.name,
            "passed": self.passed,
            "read_only": True,
            "empirical_claim_supported": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"result_id": self.result_id, **self.semantic_dict()}


__all__ = [
    "ArenaCategory",
    "ArenaDomain",
    "ArenaInput",
    "ArenaResponse",
    "ArenaResult",
    "ArenaScenario",
    "StressSignal",
]
