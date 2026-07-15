"""Contraction-only shadow review contracts for DUMMY vNext."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class ShadowValidationError(ValueError):
    """A guard finding or review attempts an invalid or expansive action."""


class GuardKind(str):
    PROVENANCE = "provenance"
    LEAKAGE = "leakage"
    CONFIDENCE = "confidence"
    DUPLICATION = "duplication"
    RESOURCE = "resource"
    MARKET_PRIOR = "market_prior"
    REGIME = "regime"
    AUTHORITY = "authority"


class GuardAction(IntEnum):
    OBSERVE = 0
    DOWNGRADE = 10
    REQUEST_EVIDENCE = 20
    REQUIRE_MARKET_PRIOR = 30
    QUARANTINE_SOURCE = 40
    VETO = 50
    REQUIRE_ABSTENTION = 60
    TERMINATE = 70


@dataclass(frozen=True, slots=True)
class GuardFinding:
    guard: str
    action: GuardAction
    reason: str
    severity: float
    influence_cap: float = 1.0
    affected_families: tuple[str, ...] = ()
    affected_agent_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.guard not in {
            GuardKind.PROVENANCE,
            GuardKind.LEAKAGE,
            GuardKind.CONFIDENCE,
            GuardKind.DUPLICATION,
            GuardKind.RESOURCE,
            GuardKind.MARKET_PRIOR,
            GuardKind.REGIME,
            GuardKind.AUTHORITY,
        }:
            raise ShadowValidationError(f"unknown guard kind: {self.guard}")
        if not self.reason.strip():
            raise ShadowValidationError("guard finding reason is required")
        if not 0.0 <= float(self.severity) <= 1.0:
            raise ShadowValidationError("guard severity must be in [0, 1]")
        if not 0.0 <= float(self.influence_cap) <= 1.0:
            raise ShadowValidationError(
                "shadow guards may only retain or reduce influence"
            )
        for field_name in (
            "affected_families",
            "affected_agent_ids",
            "evidence_ids",
        ):
            values = tuple(sorted(str(item).strip() for item in getattr(self, field_name)))
            if any(not item for item in values) or len(set(values)) != len(values):
                raise ShadowValidationError(f"{field_name} must be unique and non-empty")
            object.__setattr__(self, field_name, values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "guard": self.guard,
            "action": self.action.name,
            "reason": self.reason,
            "severity": self.severity,
            "influence_cap": self.influence_cap,
            "affected_families": list(self.affected_families),
            "affected_agent_ids": list(self.affected_agent_ids),
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GuardFinding:
        return cls(
            guard=str(data["guard"]),
            action=GuardAction[str(data["action"])],
            reason=str(data["reason"]),
            severity=float(data["severity"]),
            influence_cap=float(data.get("influence_cap", 1.0)),
            affected_families=tuple(data.get("affected_families", ())),
            affected_agent_ids=tuple(data.get("affected_agent_ids", ())),
            evidence_ids=tuple(data.get("evidence_ids", ())),
        )


@dataclass(frozen=True, slots=True)
class ShadowReview:
    findings: tuple[GuardFinding, ...]
    market_prior_floor: float
    execution_authority: bool = False
    promotion_authority: str = "HUMAN_ONLY"

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.market_prior_floor) <= 1.0:
            raise ShadowValidationError("market-prior floor must be in [0, 1]")
        if self.execution_authority is not False:
            raise ShadowValidationError("shadow review cannot grant execution authority")
        if self.promotion_authority != "HUMAN_ONLY":
            raise ShadowValidationError("shadow review cannot grant promotion authority")
        findings = tuple(
            sorted(
                self.findings,
                key=lambda item: (item.guard, item.action, item.reason),
            )
        )
        guards = tuple(item.guard for item in findings)
        if len(set(guards)) != len(guards):
            raise ShadowValidationError("each shadow guard must report exactly once")
        object.__setattr__(self, "findings", findings)

    @property
    def action(self) -> GuardAction:
        return max((item.action for item in self.findings), default=GuardAction.OBSERVE)

    @property
    def hard_veto(self) -> bool:
        return self.action >= GuardAction.VETO

    @property
    def requires_abstention(self) -> bool:
        return self.action >= GuardAction.VETO

    @property
    def family_influence_caps(self) -> dict[str, float]:
        caps: dict[str, float] = {}
        for finding in self.findings:
            for family in finding.affected_families:
                caps[family] = min(caps.get(family, 1.0), finding.influence_cap)
        return dict(sorted(caps.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.name,
            "hard_veto": self.hard_veto,
            "requires_abstention": self.requires_abstention,
            "market_prior_floor": self.market_prior_floor,
            "family_influence_caps": self.family_influence_caps,
            "findings": [item.to_dict() for item in self.findings],
            "execution_authority": self.execution_authority,
            "promotion_authority": self.promotion_authority,
            "authority_can_only_contract": True,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShadowReview:
        if data.get("execution_authority") is not False:
            raise ShadowValidationError("serialized shadow review expands authority")
        return cls(
            findings=tuple(
                GuardFinding.from_dict(item) for item in data.get("findings", ())
            ),
            market_prior_floor=float(data["market_prior_floor"]),
            execution_authority=False,
            promotion_authority=str(data.get("promotion_authority", "")),
        )
