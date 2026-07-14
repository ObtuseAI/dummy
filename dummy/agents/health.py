"""Deterministic agent health evaluation and quarantine recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARMING = "WARMING"
    DEGRADED = "DEGRADED"
    ABSTAINING = "ABSTAINING"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("health timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class AgentHealth:
    agent_id: str
    status: HealthStatus
    evaluated_at: datetime
    consecutive_failures: int
    invalid_outputs: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    reasons: tuple[str, ...]
    metrics: Mapping[str, int | float | str | bool | None]

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent_id must be non-empty")
        if self.consecutive_failures < 0 or self.invalid_outputs < 0:
            raise ValueError("health counters cannot be negative")
        object.__setattr__(self, "evaluated_at", _utc(self.evaluated_at))
        object.__setattr__(self, "last_success_at", _utc(self.last_success_at))
        object.__setattr__(self, "last_failure_at", _utc(self.last_failure_at))
        reasons = tuple(sorted(set(reason.strip() for reason in self.reasons)))
        if any(not reason for reason in reasons):
            raise ValueError("health reasons must be non-empty")
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(
            self,
            "metrics",
            MappingProxyType(dict(sorted(self.metrics.items()))),
        )

    def to_dict(self) -> dict[str, object]:
        def encode(value: datetime | None) -> str | None:
            return value.isoformat().replace("+00:00", "Z") if value else None

        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "evaluated_at": encode(self.evaluated_at),
            "consecutive_failures": self.consecutive_failures,
            "invalid_outputs": self.invalid_outputs,
            "last_success_at": encode(self.last_success_at),
            "last_failure_at": encode(self.last_failure_at),
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class HealthPolicy:
    degrade_after_failures: int = 1
    quarantine_after_failures: int = 5
    quarantine_after_invalid_outputs: int = 2
    stale_after: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if self.degrade_after_failures <= 0:
            raise ValueError("degrade_after_failures must be positive")
        if self.quarantine_after_failures < self.degrade_after_failures:
            raise ValueError("quarantine threshold must not precede degradation")
        if self.quarantine_after_invalid_outputs <= 0:
            raise ValueError("invalid-output threshold must be positive")
        if self.stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")

    def evaluate(
        self,
        *,
        agent_id: str,
        now: datetime,
        consecutive_failures: int,
        invalid_outputs: int,
        last_success_at: datetime | None,
        last_failure_at: datetime | None,
        warming: bool = False,
    ) -> AgentHealth:
        current = _utc(now)
        success = _utc(last_success_at)
        reasons: list[str] = []
        status = HealthStatus.HEALTHY
        if warming and success is None:
            status = HealthStatus.WARMING
            reasons.append("no_successful_invocation")
        if success is not None and current - success > self.stale_after:
            status = HealthStatus.ABSTAINING
            reasons.append("stale_success_lease")
        if consecutive_failures >= self.degrade_after_failures:
            status = HealthStatus.DEGRADED
            reasons.append("consecutive_failures")
        if (
            consecutive_failures >= self.quarantine_after_failures
            or invalid_outputs >= self.quarantine_after_invalid_outputs
        ):
            status = HealthStatus.QUARANTINED
            if consecutive_failures >= self.quarantine_after_failures:
                reasons.append("failure_threshold")
            if invalid_outputs >= self.quarantine_after_invalid_outputs:
                reasons.append("invalid_output_threshold")
        return AgentHealth(
            agent_id=agent_id,
            status=status,
            evaluated_at=current,
            consecutive_failures=consecutive_failures,
            invalid_outputs=invalid_outputs,
            last_success_at=success,
            last_failure_at=last_failure_at,
            reasons=tuple(reasons),
            metrics={},
        )
