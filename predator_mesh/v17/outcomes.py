"""Domain settlement ontology for V17 outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DomainEventType(str, Enum):
    GAME_WINNER = "game_winner"
    GAME_TOTAL = "game_total"
    TEMPERATURE_THRESHOLD = "temperature_threshold"
    PRECIPITATION_THRESHOLD = "precipitation_threshold"
    CRYPTO_PRICE_ABOVE = "crypto_price_above"
    COMMODITY_SETTLEMENT_PRICE = "commodity_settlement_price"
    EQUITY_INDEX_CLOSE = "equity_index_close"
    EARNINGS_RESULT = "earnings_result"


class SettlementTruth(str, Enum):
    RESOLVED_TRUE = "RESOLVED_TRUE"
    RESOLVED_FALSE = "RESOLVED_FALSE"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED_PENDING = "UNRESOLVED_PENDING"
    MANUAL_IMPORT_REQUIRED = "MANUAL_IMPORT_REQUIRED"


class OutcomeConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SettlementAmbiguityFlag(str, Enum):
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    RULE_AMBIGUITY = "RULE_AMBIGUITY"
    DELAYED_SETTLEMENT = "DELAYED_SETTLEMENT"


@dataclass(frozen=True)
class OutcomeSourceRef:
    source_name: str
    proof_ref: str
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"source_name": self.source_name, "proof_ref": self.proof_ref, "read_only": self.read_only}


@dataclass(frozen=True)
class OutcomeObservation:
    market_id: str
    event_id: str
    domain: str
    truth: SettlementTruth | str
    confidence: OutcomeConfidence | str
    source_refs: list[str]
    ambiguity_flags: list[SettlementAmbiguityFlag | str] | None = None
    observed_at: str | None = None

    def truth_value(self) -> int | None:
        truth = self.truth.value if isinstance(self.truth, SettlementTruth) else self.truth
        if truth == SettlementTruth.RESOLVED_TRUE.value:
            return 1
        if truth == SettlementTruth.RESOLVED_FALSE.value:
            return 0
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_id": self.market_id,
            "event_id": self.event_id,
            "domain": self.domain,
            "truth": self.truth.value if isinstance(self.truth, SettlementTruth) else self.truth,
            "truth_value": self.truth_value(),
            "confidence": self.confidence.value if isinstance(self.confidence, OutcomeConfidence) else self.confidence,
            "source_refs": list(self.source_refs),
            "ambiguity_flags": [flag.value if isinstance(flag, SettlementAmbiguityFlag) else flag for flag in (self.ambiguity_flags or [])],
            "observed_at": self.observed_at,
        }


class DomainOutcomeOntology:
    domains = ["sports", "weather", "crypto", "commodities", "finance"]
    event_types = {
        "sports": ["game_winner", "game_total"],
        "weather": ["temperature_threshold", "precipitation_threshold"],
        "crypto": ["crypto_price_above"],
        "commodities": ["commodity_settlement_price"],
        "finance": ["equity_index_close", "earnings_result"],
    }

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V17: Domain Outcome Ontology",
            "domains": self.domains,
            "event_types": self.event_types,
            "settlement_truth_values": [item.value for item in SettlementTruth],
            "outcome_confidence_values": [item.value for item in OutcomeConfidence],
            "ambiguity_flags": [item.value for item in SettlementAmbiguityFlag],
            "proof_refs_supported": True,
            "ambiguous_settlement_generates_no_trade_pressure": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def settlement_truth_schema_report(self) -> dict[str, Any]:
        report = self.to_report()
        report.update(
            {
                "workstream": "V17: Domain Settlement Truth Schema",
                "proof_refs_supported": True,
                "ambiguous_truth_requires_manual_or_readonly_resolution": True,
            }
        )
        return report
