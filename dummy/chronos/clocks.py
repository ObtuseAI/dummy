"""Clock domains and verified point-in-time decision timelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ClockDomain(str, Enum):
    QUOTE = "quote"
    ONE_MINUTE = "one_minute"
    FIVE_MINUTE = "five_minute"
    FIFTEEN_MINUTE = "fifteen_minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    EXPIRY = "expiry"
    SETTLEMENT = "settlement"
    PREGAME = "pregame"
    LINEUP_CONFIRMATION = "lineup_confirmation"
    WARMUP = "warmup"
    GAME_START = "game_start"
    POSSESSION = "possession"
    INNING = "inning"
    PERIOD = "period"
    HALFTIME = "halftime"
    OVERTIME = "overtime"
    CALIBRATION = "calibration"
    TRUST_UPDATE = "trust_update"
    DRIFT_DETECTION = "drift_detection"
    EVOLUTION = "evolution"
    PROMOTION_REVIEW = "promotion_review"
    LEDGER_RETENTION = "ledger_retention"


class TimestampSource(str, Enum):
    EXCHANGE = "exchange"
    PROVIDER_VERIFIED = "provider_verified"
    LOCAL_RECEIPT = "local_receipt"
    DECISION_ENGINE = "decision_engine"
    MARKET_SCHEDULE = "market_schedule"
    SETTLEMENT_FEED = "settlement_feed"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("causal timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class TimeEvidence:
    at: datetime
    source: TimestampSource
    provenance: str
    verified: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "at", _aware_utc(self.at))
        if not self.provenance.strip():
            raise ValueError("timestamp provenance must be non-empty")
        if self.source is TimestampSource.LOCAL_RECEIPT and not self.verified:
            raise ValueError("local receipt timestamps are verified by definition")


@dataclass(frozen=True, slots=True)
class CausalTimeline:
    domain: ClockDomain
    observed: TimeEvidence
    received: TimeEvidence
    decided: TimeEvidence
    published: TimeEvidence | None = None
    market_close: TimeEvidence | None = None
    settled: TimeEvidence | None = None

    def __post_init__(self) -> None:
        replay_evidence = {
            "observation": self.observed,
            "receipt": self.received,
            "decision": self.decided,
            "publication": self.published,
            "market close": self.market_close,
            "settlement": self.settled,
        }
        for label, evidence in replay_evidence.items():
            if evidence is not None and not evidence.verified:
                raise ValueError(
                    f"unverified {label} timestamp cannot enter replay"
                )
        if self.received.source is not TimestampSource.LOCAL_RECEIPT:
            raise ValueError("received timestamp must use LOCAL_RECEIPT")
        if self.observed.at > self.received.at:
            raise ValueError("observation occurs after local receipt")
        if self.published is not None:
            if not self.observed.at <= self.published.at <= self.received.at:
                raise ValueError("publication time violates causal order")
        if self.received.at > self.decided.at:
            raise ValueError("decision occurs before local receipt")
        if self.market_close is not None and self.decided.at > self.market_close.at:
            raise ValueError("decision occurs after market close")
        if self.settled is not None:
            if self.market_close is None:
                raise ValueError("settlement requires market close evidence")
            if self.settled.at < self.market_close.at:
                raise ValueError("settlement occurs before market close")

    def to_dict(self) -> dict[str, object]:
        def encode(value: TimeEvidence | None) -> dict[str, object] | None:
            if value is None:
                return None
            return {
                "at": value.at.isoformat().replace("+00:00", "Z"),
                "source": value.source.value,
                "provenance": value.provenance,
                "verified": value.verified,
            }

        return {
            "domain": self.domain.value,
            "observed": encode(self.observed),
            "published": encode(self.published),
            "received": encode(self.received),
            "decided": encode(self.decided),
            "market_close": encode(self.market_close),
            "settled": encode(self.settled),
        }
