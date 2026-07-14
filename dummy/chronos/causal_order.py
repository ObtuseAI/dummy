"""Deterministic causal-parent validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


class CausalOrderError(ValueError):
    """The supplied event sequence cannot be replayed causally."""


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CausalOrderError("causal event timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CausalEvent:
    event_id: str
    occurred_at: datetime
    recorded_at: datetime
    causal_parents: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise CausalOrderError("event_id must be non-empty")
        occurred = _aware_utc(self.occurred_at)
        recorded = _aware_utc(self.recorded_at)
        if occurred > recorded:
            raise CausalOrderError("event occurred after it was recorded")
        if len(set(self.causal_parents)) != len(self.causal_parents):
            raise CausalOrderError("causal parent list contains duplicates")
        if self.event_id in self.causal_parents:
            raise CausalOrderError("event cannot be its own parent")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "recorded_at", recorded)
        object.__setattr__(self, "causal_parents", tuple(self.causal_parents))


def validate_causal_order(events: Iterable[CausalEvent]) -> tuple[CausalEvent, ...]:
    """Validate a replay sequence and return its frozen order."""

    ordered = tuple(events)
    seen: dict[str, CausalEvent] = {}
    for event in ordered:
        if event.event_id in seen:
            raise CausalOrderError(f"duplicate event_id: {event.event_id}")
        for parent_id in event.causal_parents:
            parent = seen.get(parent_id)
            if parent is None:
                raise CausalOrderError(
                    f"parent {parent_id} missing before {event.event_id}"
                )
            if parent.recorded_at > event.recorded_at:
                raise CausalOrderError(
                    f"parent {parent_id} recorded after child {event.event_id}"
                )
        seen[event.event_id] = event
    return ordered
