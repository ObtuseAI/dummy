"""Typed execution-policy abstraction for the Phase-A execution tournament.

The Wave-1 adverse-selection diagnosis
(``docs/EXECUTION_ADVERSE_SELECTION_2026-07-16.md``) established that Dummy's
maker-first execution channel converts a modestly *positive*-skill forecast
surface into a losing book: maker fills run -14.7% Brier vs market while the
unfilled surface runs +6.5%, fast (<=60s) fills are 11% win / -300c, and every
fill carries +13.3c of pure adverse information. The taker counterfactual over
the full actionable surface is near breakeven.

This module makes *execution policy* a first-class, typed object so the
tournament can score maker-only (the incumbent control), taker-only, taker with
a walk-forward-selected edge threshold, an adverse-guarded maker, and a hybrid
patient-then-take policy against one another over the same actionable surface.

``ExecutionPolicy`` is consumed in two places:

  * ``autonomy.executor.Executor`` accepts an optional policy. The control
    policy (:meth:`ExecutionPolicy.maker_only_control`, cohort ``C0``) is a
    strict no-op -- the executor takes exactly the pre-existing code path, byte
    for byte, so C0 reproduces current behavior (regression-tested in
    ``tests/test_execution_policy.py``). Only non-control policies consult the
    new guard hooks.
  * ``autonomy.execution_tournament`` replays the ledger's actionable surface
    under each cohort to accrue per-cohort fill-conditioned evidence.

Nothing here places an order, moves capital, or switches the live policy. A
tournament winner is evidence only; promoting a cohort to the live execution
policy is a separate decision that flows through the auto-promotion ladder or
an explicit operator config change (see
:data:`POLICY_SWITCH_AUTHORITY`).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

# The tournament ranks cohorts; it never rewires the live executor. A cohort is
# adopted as the live execution policy only through the auto-promotion ladder
# (``autonomy/auto_promotion.py`` fusion-membership governance, which already
# gates behavior changes on cluster-robust contested evidence) or an explicit,
# reviewed operator config edit. The report states this so a green cohort is
# never mistaken for an automatic switch.
POLICY_SWITCH_AUTHORITY = "auto_promotion_ladder_or_explicit_operator_config"

# Execution modes.
MODE_MAKER = "maker"
MODE_TAKER = "taker"
MODE_HYBRID = "hybrid"
MODES = frozenset({MODE_MAKER, MODE_TAKER, MODE_HYBRID})

# Canonical cohort identifiers.
COHORT_CONTROL = "C0"
COHORT_TAKER = "C1"
COHORT_TAKER_WALK_FORWARD = "C2"
COHORT_ADVERSE_GUARD_MAKER = "C3"
COHORT_HYBRID = "C4"
COHORT_ORDER = (
    COHORT_CONTROL,
    COHORT_TAKER,
    COHORT_TAKER_WALK_FORWARD,
    COHORT_ADVERSE_GUARD_MAKER,
    COHORT_HYBRID,
)


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """One execution policy: how a priced decision reaches (or refuses) a fill.

    All parameters are inert for the control policy; each non-default field
    turns on exactly one guarded or taker behavior so a cohort is fully
    described by its field values (and serializes losslessly to the report).
    """

    cohort: str
    label: str
    mode: str

    # --- Taker gating (C1, C2) --------------------------------------------- #
    # Cross the best ask at decision time only when EV net of the taker fee and
    # the observed half-spread clears this floor (cents). ``None`` means the
    # cohort does not take.
    taker_min_ev_cents: float | None = None
    # Additional minimum |model - market| edge (cents) required before a taker
    # cross. C2 fills this per fold from the walk-forward selector; C1 leaves it
    # at 0 (EV floor only).
    taker_min_edge_cents: float = 0.0
    # True when ``taker_min_edge_cents`` was chosen out-of-sample by the
    # walk-forward machinery rather than hardcoded (C2). Purely descriptive; the
    # report discloses the per-fold picks.
    edge_threshold_walk_forward_selected: bool = False

    # --- Adverse-selection maker guards (C3) ------------------------------- #
    # Treat a maker fill witnessed within this many seconds of submit as
    # marketable-at-submit (stale/adverse) and refuse it. ``None`` disables.
    fast_cross_guard_seconds: float | None = None
    # Re-read the book immediately before submit and refuse a quote already
    # within one tick of crossing (the live ``quote_fn`` guard, extended to the
    # shadow book so paper evidence honors the same guard).
    presubmit_book_recheck: bool = False
    # Do not rest a maker quote when |model - market| exceeds this many cents:
    # the wider the divergence, the more the fill is adverse information rather
    # than value. ``None`` disables.
    divergence_cap_cents: float | None = None

    # --- Hybrid patient-then-take (C4) ------------------------------------- #
    # Rest as a maker for this many seconds; if still unfilled and a fresh book
    # read still clears ``taker_min_ev_cents`` net of the taker fee, cross;
    # otherwise cancel. ``None`` means the policy never escalates to a take.
    rest_seconds_before_take: float | None = None

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"unknown execution mode: {self.mode!r}")
        if self.cohort not in COHORT_ORDER and not self.cohort.startswith("C2:"):
            raise ValueError(f"unknown cohort id: {self.cohort!r}")
        if self.taker_min_edge_cents < 0:
            raise ValueError("taker_min_edge_cents must be non-negative")

    # ------------------------------------------------------------------ #
    # Semantics
    # ------------------------------------------------------------------ #

    def is_control(self) -> bool:
        """True for the incumbent maker-only control (C0) -- the executor no-op.

        The executor uses this to guarantee C0 takes the pre-existing code path
        with zero new branches: control means maker mode, no taker escalation,
        and no guards armed.
        """
        return (
            self.mode == MODE_MAKER
            and self.fast_cross_guard_seconds is None
            and not self.presubmit_book_recheck
            and self.divergence_cap_cents is None
            and self.rest_seconds_before_take is None
            and self.taker_min_ev_cents is None
        )

    def takes_liquidity(self) -> bool:
        """True when the policy can cross the spread (taker or hybrid escalation)."""
        return self.mode in {MODE_TAKER, MODE_HYBRID} or (
            self.rest_seconds_before_take is not None
        )

    def with_edge_threshold(self, threshold_cents: float) -> ExecutionPolicy:
        """Return a copy with a walk-forward-selected taker edge threshold (C2)."""
        return replace(
            self,
            taker_min_edge_cents=float(threshold_cents),
            edge_threshold_walk_forward_selected=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort": self.cohort,
            "label": self.label,
            "mode": self.mode,
            "taker_min_ev_cents": self.taker_min_ev_cents,
            "taker_min_edge_cents": self.taker_min_edge_cents,
            "edge_threshold_walk_forward_selected": (
                self.edge_threshold_walk_forward_selected
            ),
            "fast_cross_guard_seconds": self.fast_cross_guard_seconds,
            "presubmit_book_recheck": self.presubmit_book_recheck,
            "divergence_cap_cents": self.divergence_cap_cents,
            "rest_seconds_before_take": self.rest_seconds_before_take,
            "is_control": self.is_control(),
            "takes_liquidity": self.takes_liquidity(),
        }

    # ------------------------------------------------------------------ #
    # Canonical cohorts (diagnosis section 7)
    # ------------------------------------------------------------------ #

    @classmethod
    def maker_only_control(cls) -> ExecutionPolicy:
        """C0: current allocator/executor behavior, unchanged. The control."""
        return cls(
            cohort=COHORT_CONTROL,
            label="maker-only control (incumbent)",
            mode=MODE_MAKER,
        )

    @classmethod
    def taker_only(cls, taker_min_ev_cents: float = 3.0) -> ExecutionPolicy:
        """C1: cross the best ask when EV net of taker fee + half-spread clears MIN_EV."""
        return cls(
            cohort=COHORT_TAKER,
            label="taker-only (cross at decision time, MIN_EV net of taker fee)",
            mode=MODE_TAKER,
            taker_min_ev_cents=float(taker_min_ev_cents),
        )

    @classmethod
    def taker_walk_forward(
        cls,
        edge_threshold_cents: float | None = None,
        taker_min_ev_cents: float = 3.0,
    ) -> ExecutionPolicy:
        """C2: taker with a per-fold walk-forward-selected minimum edge threshold.

        ``edge_threshold_cents`` is ``None`` until the fold selector supplies it;
        the tournament never hardcodes the in-sample optimum (5-8c region).
        """
        policy = cls(
            cohort=COHORT_TAKER_WALK_FORWARD,
            label="taker with walk-forward edge threshold",
            mode=MODE_TAKER,
            taker_min_ev_cents=float(taker_min_ev_cents),
            edge_threshold_walk_forward_selected=True,
        )
        if edge_threshold_cents is not None:
            policy = policy.with_edge_threshold(edge_threshold_cents)
        return policy

    @classmethod
    def adverse_guard_maker(
        cls,
        fast_cross_guard_seconds: float = 60.0,
        divergence_cap_cents: float = 10.0,
    ) -> ExecutionPolicy:
        """C3: maker with the fast-cross guard, presubmit recheck, and divergence cap."""
        return cls(
            cohort=COHORT_ADVERSE_GUARD_MAKER,
            label="adverse-guard maker (fast-cross + divergence cap)",
            mode=MODE_MAKER,
            fast_cross_guard_seconds=float(fast_cross_guard_seconds),
            presubmit_book_recheck=True,
            divergence_cap_cents=float(divergence_cap_cents),
        )

    @classmethod
    def hybrid_patient_then_take(
        cls,
        rest_seconds_before_take: float = 60.0,
        taker_min_ev_cents: float = 3.0,
    ) -> ExecutionPolicy:
        """C4: rest 60s as a maker, then take if the fresh book is still positive-EV."""
        return cls(
            cohort=COHORT_HYBRID,
            label="hybrid patient-then-take (rest 60s, then cross if EV holds)",
            mode=MODE_HYBRID,
            rest_seconds_before_take=float(rest_seconds_before_take),
            taker_min_ev_cents=float(taker_min_ev_cents),
        )


def default_cohorts() -> tuple[ExecutionPolicy, ...]:
    """The canonical C0-C4 tournament field, control first."""
    return (
        ExecutionPolicy.maker_only_control(),
        ExecutionPolicy.taker_only(),
        ExecutionPolicy.taker_walk_forward(),
        ExecutionPolicy.adverse_guard_maker(),
        ExecutionPolicy.hybrid_patient_then_take(),
    )


__all__ = [
    "COHORT_ADVERSE_GUARD_MAKER",
    "COHORT_CONTROL",
    "COHORT_HYBRID",
    "COHORT_ORDER",
    "COHORT_TAKER",
    "COHORT_TAKER_WALK_FORWARD",
    "ExecutionPolicy",
    "MODES",
    "MODE_HYBRID",
    "MODE_MAKER",
    "MODE_TAKER",
    "POLICY_SWITCH_AUTHORITY",
    "default_cohorts",
]
