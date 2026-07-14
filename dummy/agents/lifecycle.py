"""Explicit, deterministic lifecycle state for vNext agents."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


_TRANSITION_NAMESPACE = uuid.UUID("fbf18ac7-0a5d-54aa-85d2-4d7c2d9b0df9")


class LifecycleTransitionError(ValueError):
    """An agent attempted an invalid or unauthorized state transition."""


class AgentState(str, Enum):
    REGISTERED = "REGISTERED"
    WARMING = "WARMING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    ABSTAINING = "ABSTAINING"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"


_TRANSITIONS = {
    AgentState.REGISTERED: frozenset(
        {AgentState.WARMING, AgentState.QUARANTINED, AgentState.RETIRED}
    ),
    AgentState.WARMING: frozenset(
        {
            AgentState.READY,
            AgentState.DEGRADED,
            AgentState.ABSTAINING,
            AgentState.QUARANTINED,
            AgentState.RETIRED,
        }
    ),
    AgentState.READY: frozenset(
        {
            AgentState.ACTIVE,
            AgentState.DEGRADED,
            AgentState.ABSTAINING,
            AgentState.QUARANTINED,
            AgentState.RETIRED,
        }
    ),
    AgentState.ACTIVE: frozenset(
        {
            AgentState.READY,
            AgentState.DEGRADED,
            AgentState.ABSTAINING,
            AgentState.QUARANTINED,
            AgentState.RETIRED,
        }
    ),
    AgentState.DEGRADED: frozenset(
        {
            AgentState.WARMING,
            AgentState.ABSTAINING,
            AgentState.QUARANTINED,
            AgentState.RETIRED,
        }
    ),
    AgentState.ABSTAINING: frozenset(
        {AgentState.WARMING, AgentState.QUARANTINED, AgentState.RETIRED}
    ),
    AgentState.QUARANTINED: frozenset(
        {AgentState.WARMING, AgentState.RETIRED}
    ),
    AgentState.RETIRED: frozenset(),
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleTransitionError("lifecycle timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class LifecycleRecord:
    transition_id: str
    sequence: int
    agent_id: str
    previous: AgentState
    current: AgentState
    at: datetime
    reason: str
    evidence_ids: tuple[str, ...]
    review_authorized: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "transition_id": self.transition_id,
            "sequence": self.sequence,
            "agent_id": self.agent_id,
            "previous": self.previous.value,
            "current": self.current.value,
            "at": self.at.isoformat().replace("+00:00", "Z"),
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "review_authorized": self.review_authorized,
        }


class AgentLifecycle:
    """Small state machine whose history is deterministic from its inputs."""

    def __init__(self, agent_id: str) -> None:
        if not agent_id.strip():
            raise LifecycleTransitionError("agent_id must be non-empty")
        self.agent_id = agent_id
        self._state = AgentState.REGISTERED
        self._history: list[LifecycleRecord] = []

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def history(self) -> tuple[LifecycleRecord, ...]:
        return tuple(self._history)

    def transition(
        self,
        target: AgentState,
        *,
        at: datetime,
        reason: str,
        evidence_ids: tuple[str, ...] = (),
        review_authorized: bool = False,
    ) -> LifecycleRecord:
        if not reason.strip():
            raise LifecycleTransitionError("transition reason must be non-empty")
        if target not in _TRANSITIONS[self._state]:
            raise LifecycleTransitionError(
                f"invalid transition {self._state.value}->{target.value}"
            )
        when = _utc(at)
        if self._history and when < self._history[-1].at:
            raise LifecycleTransitionError("lifecycle time moved backward")
        evidence = tuple(evidence_ids)
        if any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise LifecycleTransitionError("evidence_ids must be non-empty strings")
        if len(set(evidence)) != len(evidence):
            raise LifecycleTransitionError("evidence_ids contains duplicates")
        if target in {
            AgentState.DEGRADED,
            AgentState.QUARANTINED,
            AgentState.RETIRED,
        } and not evidence:
            raise LifecycleTransitionError(
                f"{target.value} transition requires evidence_ids"
            )
        if self._state is AgentState.QUARANTINED and target is AgentState.WARMING:
            if not review_authorized:
                raise LifecycleTransitionError(
                    "quarantine release requires explicit review authorization"
                )
            if not evidence:
                raise LifecycleTransitionError(
                    "quarantine release requires review evidence"
                )

        sequence = len(self._history) + 1
        semantic = json.dumps(
            {
                "agent_id": self.agent_id,
                "sequence": sequence,
                "previous": self._state.value,
                "current": target.value,
                "at": when.isoformat(),
                "reason": reason.strip(),
                "evidence_ids": list(evidence),
                "review_authorized": review_authorized,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        record = LifecycleRecord(
            transition_id=str(uuid.uuid5(_TRANSITION_NAMESPACE, semantic)),
            sequence=sequence,
            agent_id=self.agent_id,
            previous=self._state,
            current=target,
            at=when,
            reason=reason.strip(),
            evidence_ids=evidence,
            review_authorized=review_authorized,
        )
        self._history.append(record)
        self._state = target
        return record
