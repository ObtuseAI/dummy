"""Council-of-specialists protocol and registry (Phase 0 skeleton).

The council architecture (docs/superpowers/specs/2026-07-12-council-of-
specialists-design.md) gives each vertical -- every sports league plus crypto
-- its own specialist subagent that owns the vertical end-to-end: pre-game
model view, live in-play view, independent sharp "book" estimator, feed
warming, and health. Specialists are advisory by construction: they forecast,
the core decides. No specialist ever touches the allocator, executor, or risk
brain, and every specialist fails closed -- missing data means abstain
(``None``), never a degraded guess.

Phase 0 wraps the shipped signal stack behind this protocol with zero
behavior change; later phases deepen each specialist independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from autonomy.ontology import MarketView, Signal


@dataclass(frozen=True)
class SpecialistHealth:
    """Small, JSON-able health snapshot for the dashboard council panel."""

    name: str
    status: str  # "ok" | "degraded" | "cold"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "details": dict(self.details)}


@runtime_checkable
class Specialist(Protocol):
    """Uniform per-vertical subagent interface.

    Every method is fail-closed: when the specialist has no view (missing
    feed, wrong market shape, game not in the right phase) it returns
    ``None`` and the caller's behavior is byte-identical to a run without
    the specialist.
    """

    name: str

    def applicable(self, market: MarketView) -> bool:
        """True when this market belongs to this specialist's vertical."""

    def forecast(self, market: MarketView) -> Signal | None:
        """The specialist's own pre-game model view (challenger evidence)."""

    def live_forecast(self, market: MarketView) -> Signal | None:
        """In-play view for an in-progress event; None means abstain."""

    def book(self, market: MarketView) -> float | None:
        """De-vigged independent sharp estimator P(YES); None means no book."""

    def on_cycle_start(self) -> None:
        """Warm/refresh this specialist's feeds for the coming pass."""

    def health(self) -> SpecialistHealth:
        """Cheap, non-fetching health snapshot."""


class SpecialistRegistry:
    """Routes each market to exactly one specialist.

    Registration order is the routing order; series prefixes are disjoint by
    design, so at most one specialist claims any market. A specialist that
    raises during routing or warmup is skipped -- one broken vertical must
    never take down the council.
    """

    def __init__(self) -> None:
        self._specialists: list[Specialist] = []

    def register(self, specialist: Specialist) -> None:
        self._specialists.append(specialist)

    def specialists(self) -> list[Specialist]:
        return list(self._specialists)

    def route(self, market: MarketView) -> Specialist | None:
        for specialist in self._specialists:
            try:
                if specialist.applicable(market):
                    return specialist
            except Exception:
                continue
        return None

    def on_cycle_start(self) -> None:
        for specialist in self._specialists:
            try:
                specialist.on_cycle_start()
            except Exception:
                continue

    def health_report(self) -> list[dict[str, Any]]:
        report: list[dict[str, Any]] = []
        for specialist in self._specialists:
            try:
                report.append(specialist.health().to_dict())
            except Exception as exc:
                report.append({
                    "name": getattr(specialist, "name", "unknown"),
                    "status": "degraded",
                    "details": {"error": type(exc).__name__},
                })
        return report
