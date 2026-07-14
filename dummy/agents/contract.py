"""Versioned, immutable contracts for deterministic forecast agents."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum

from dummy import VNEXT_MATURITY
from dummy.chronos import ClockDomain
from dummy.constitution import RESEARCH_AUTHORITY_CEILING, Authority
from dummy.protocols import MessageType, required_authority


_AGENT_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


class ContractValidationError(ValueError):
    """An agent contract is unsafe, incomplete, or nondeterministic."""


class AgentRole(str, Enum):
    OBSERVER = "observer"
    FEATURE_EXTRACTOR = "feature_extractor"
    MARKET_PRIOR = "market_prior"
    SPECIALIST = "specialist"
    CALIBRATOR = "calibrator"
    ADVERSARY = "adversary"
    SYNTHESIZER = "synthesizer"
    SHADOW = "shadow"
    EXECUTION_TRUTH = "execution_truth"
    SETTLEMENT_GRADER = "settlement_grader"
    HEALTH_GUARD = "health_guard"


class AgentVertical(str, Enum):
    SYSTEM = "system"
    MARKET = "market"
    CRYPTO = "crypto"
    MLB = "mlb"
    NBA = "nba"
    NFL = "nfl"
    NCAAF = "ncaaf"
    NHL = "nhl"
    NCAAMB = "ncaamb"
    SPORTS = "sports"
    WEATHER = "weather"
    COMMODITIES = "commodities"
    OTHER = "other"


def _unique_sorted(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(sorted(value.strip() for value in values))
    if any(not value for value in normalized):
        raise ContractValidationError(f"{field_name} contains an empty value")
    if len(set(normalized)) != len(normalized):
        raise ContractValidationError(f"{field_name} contains duplicates")
    return normalized


def _unique_message_types(
    values: tuple[MessageType, ...],
    field_name: str,
) -> tuple[MessageType, ...]:
    normalized = tuple(sorted(values, key=lambda item: item.value))
    if len(set(normalized)) != len(normalized):
        raise ContractValidationError(f"{field_name} contains duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class AgentBudget:
    max_messages_per_invocation: int = 1
    max_payload_bytes: int = 64 * 1024
    max_evidence_items: int = 64
    max_wall_time_ms: int = 5_000

    def __post_init__(self) -> None:
        for field_name in (
            "max_messages_per_invocation",
            "max_payload_bytes",
            "max_evidence_items",
            "max_wall_time_ms",
        ):
            if getattr(self, field_name) <= 0:
                raise ContractValidationError(f"{field_name} must be positive")

    def to_dict(self) -> dict[str, int]:
        return {
            "max_messages_per_invocation": self.max_messages_per_invocation,
            "max_payload_bytes": self.max_payload_bytes,
            "max_evidence_items": self.max_evidence_items,
            "max_wall_time_ms": self.max_wall_time_ms,
        }


@dataclass(frozen=True, slots=True)
class AgentContract:
    agent_id: str
    role: AgentRole
    vertical: AgentVertical
    supported_market_types: tuple[str, ...]
    input_types: tuple[MessageType, ...]
    output_types: tuple[MessageType, ...]
    clock_domain: ClockDomain
    authority: Authority
    evidence_requirements: tuple[str, ...]
    fail_closed_on: tuple[str, ...]
    budget: AgentBudget
    calibration_identity: str
    source_family: str
    version: str
    dependencies: tuple[str, ...] = ()
    max_input_age_ms: int = 60_000
    maturity: str = VNEXT_MATURITY
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not _AGENT_ID.fullmatch(self.agent_id):
            raise ContractValidationError(f"invalid agent_id: {self.agent_id!r}")
        if not _VERSION.fullmatch(self.version):
            raise ContractValidationError(f"invalid version: {self.version!r}")
        if self.schema_version != 1:
            raise ContractValidationError("unsupported agent contract schema")
        if self.max_input_age_ms <= 0:
            raise ContractValidationError("max_input_age_ms must be positive")
        if self.maturity != VNEXT_MATURITY:
            raise ContractValidationError(
                f"vNext agents must use maturity {VNEXT_MATURITY}"
            )
        if self.authority > RESEARCH_AUTHORITY_CEILING:
            raise ContractValidationError(
                f"{self.agent_id} exceeds research authority ceiling "
                f"{RESEARCH_AUTHORITY_CEILING.name}"
            )
        if not self.calibration_identity.strip():
            raise ContractValidationError("calibration_identity must be non-empty")
        if not self.source_family.strip():
            raise ContractValidationError("source_family must be non-empty")

        market_types = _unique_sorted(
            self.supported_market_types,
            "supported_market_types",
        )
        if not market_types:
            raise ContractValidationError("supported_market_types must be non-empty")
        inputs = _unique_message_types(self.input_types, "input_types")
        outputs = _unique_message_types(self.output_types, "output_types")
        if not outputs:
            raise ContractValidationError("output_types must be non-empty")
        for message_type in outputs:
            exercised = required_authority(message_type)
            if exercised > self.authority:
                raise ContractValidationError(
                    f"{message_type.value} requires {exercised.name}; "
                    f"contract grants {self.authority.name}"
                )

        requirements = _unique_sorted(
            self.evidence_requirements,
            "evidence_requirements",
        )
        fail_closed = _unique_sorted(self.fail_closed_on, "fail_closed_on")
        if not fail_closed:
            raise ContractValidationError("fail_closed_on must be non-empty")
        dependencies = _unique_sorted(self.dependencies, "dependencies")
        if self.agent_id in dependencies:
            raise ContractValidationError("agent cannot depend on itself")

        object.__setattr__(self, "supported_market_types", market_types)
        object.__setattr__(self, "input_types", inputs)
        object.__setattr__(self, "output_types", outputs)
        object.__setattr__(self, "evidence_requirements", requirements)
        object.__setattr__(self, "fail_closed_on", fail_closed)
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "calibration_identity", self.calibration_identity.strip())
        object.__setattr__(self, "source_family", self.source_family.strip())

    def supports_market_type(self, market_type: str) -> bool:
        return "*" in self.supported_market_types or market_type in self.supported_market_types

    def to_dict(self) -> dict[str, object]:
        input_schemas = [
            {
                "message_type": item.value,
                "schema_id": f"dummy.protocols.{item.value.lower()}",
                "schema_version": 1,
            }
            for item in self.input_types
        ]
        output_schemas = [
            {
                "message_type": item.value,
                "schema_id": f"dummy.protocols.{item.value.lower()}",
                "schema_version": 1,
            }
            for item in self.output_types
        ]
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "role": self.role.value,
            "vertical": self.vertical.value,
            "supported_market_types": list(self.supported_market_types),
            "input_types": [item.value for item in self.input_types],
            "output_types": [item.value for item in self.output_types],
            "input_schemas": input_schemas,
            "output_schemas": output_schemas,
            "clock_domain": self.clock_domain.value,
            "authority": self.authority.name,
            "evidence_requirements": list(self.evidence_requirements),
            "fail_closed_on": list(self.fail_closed_on),
            "budget": self.budget.to_dict(),
            "calibration_identity": self.calibration_identity,
            "source_family": self.source_family,
            "version": self.version,
            "dependencies": list(self.dependencies),
            "max_input_age_ms": self.max_input_age_ms,
            "maturity": self.maturity,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
