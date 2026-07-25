"""Divide one capped pot among candidates competing in the same cycle.

Sizing a single order is ``autonomy.risk_brain``'s job and it does it well.
This module answers the question nothing else asks: when N candidates qualify
at once, who gets how much of the shared budget?

Before this existed the answer was "whoever was ranked first, as much as its
own caps allowed" -- ``autonomy/allocator.py`` handed each candidate the entire
remaining budget in turn, so a top-ranked market could drain the cycle and
leave a near-equal rival with nothing.

Pure by construction -- no clock, no filesystem, no state.  Weight resolution
lives in ``autonomy.allocation_weights`` so the split rules can be tested
without any calibration fixtures.

Two invariants hold for every policy and every input:

  * ``sum(granted) <= pot_cents`` -- rounding residue is dropped, never
    redistributed.  A pot that can overshoot by a cent is a pot with no
    ceiling.
  * ``granted_i <= ask_i`` -- this layer only ever reduces.  It sits in front
    of the risk brain and the firewall, both of which still bind afterwards.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

DEFAULT_POLICY = "kelly_prorata"
POLICIES = frozenset({"kelly_prorata", "proportional", "top_k"})


@dataclass(frozen=True)
class Ask:
    """One candidate's request for budget, produced by the allocator pre-pass."""

    candidate_id: str
    scope: str
    ask_cents: int
    price_cents: int


@dataclass(frozen=True)
class Grant:
    """What the candidate actually gets, and why -- safe to log or render."""

    candidate_id: str
    granted_cents: int
    weight: float
    policy: str
    reason: str


def _zero(ask: Ask, weight: float, policy: str, reason: str) -> Grant:
    return Grant(ask.candidate_id, 0, weight, policy, reason)


def allocate(
    asks: Sequence[Ask],
    pot_cents: int,
    weights: Mapping[str, float],
    policy: str,
    top_k: int = 5,
) -> list[Grant]:
    """Split *pot_cents* across *asks*, weighted by scope.

    An unrecognized *policy* falls back to ``kelly_prorata`` rather than
    raising: a bad operator edit must degrade to the default, never halt a
    cycle.
    """
    if policy not in POLICIES:
        policy = DEFAULT_POLICY

    # Order is fixed up front so ties break on candidate_id, not dict order.
    ordered = sorted(asks, key=lambda a: a.candidate_id)

    if pot_cents <= 0:
        return [_zero(a, float(weights.get(a.scope, 0.0)), policy, "pot exhausted")
                for a in ordered]

    live = [a for a in ordered if a.ask_cents > 0]
    dead = [a for a in ordered if a.ask_cents <= 0]
    grants = [_zero(a, float(weights.get(a.scope, 0.0)), policy, "no ask") for a in dead]

    if not live:
        return grants

    if policy == "top_k":
        grants.extend(_top_k(live, pot_cents, weights, top_k))
    elif policy == "proportional":
        grants.extend(_proportional(live, pot_cents, weights))
    else:
        grants.extend(_kelly_prorata(live, pot_cents, weights))

    return sorted(grants, key=lambda g: g.candidate_id)


def _kelly_prorata(
    live: list[Ask], pot_cents: int, weights: Mapping[str, float]
) -> list[Grant]:
    """Each ask scaled by its weight; scaled down again if the total overflows.

    Under-subscribed cycles deliberately deploy less than the pot.  Kelly has
    already answered what each edge is worth; inflating those sizes because
    nothing else showed up would size on availability rather than on edge.
    """
    raw = {a.candidate_id: a.ask_cents * float(weights.get(a.scope, 0.0)) for a in live}
    total = sum(raw.values())
    if total <= 0:
        return [_zero(a, float(weights.get(a.scope, 0.0)), "kelly_prorata",
                      "zero weighted ask") for a in live]

    scale = min(1.0, pot_cents / total)
    grants: list[Grant] = []
    spent = 0
    for ask in live:
        weight = float(weights.get(ask.scope, 0.0))
        cents = int(raw[ask.candidate_id] * scale)
        cents = min(cents, ask.ask_cents, max(0, pot_cents - spent))
        spent += cents
        reason = ("weighted ask" if scale >= 1.0
                  else f"weighted ask scaled {scale:.3f} (pot oversubscribed)")
        grants.append(Grant(ask.candidate_id, cents, weight, "kelly_prorata", reason))
    return grants


def _proportional(
    live: list[Ask], pot_cents: int, weights: Mapping[str, float]
) -> list[Grant]:
    """Share of the pot by weight, clamped to the ask.

    The clamp residue is NOT redistributed.  Redistribution turns this into
    iterative water-filling, whose outcome nobody can predict by eye -- and
    being predictable by eye is the whole reason this policy exists.
    """
    total_weight = sum(float(weights.get(a.scope, 0.0)) for a in live)
    if total_weight <= 0:
        return [_zero(a, float(weights.get(a.scope, 0.0)), "proportional",
                      "zero total weight") for a in live]

    grants: list[Grant] = []
    spent = 0
    for ask in live:
        weight = float(weights.get(ask.scope, 0.0))
        share = int(pot_cents * (weight / total_weight))
        cents = min(share, ask.ask_cents, max(0, pot_cents - spent))
        spent += cents
        reason = (f"{weight / total_weight:.1%} weight share"
                  if cents == share else "weight share clamped to ask")
        grants.append(Grant(ask.candidate_id, cents, weight, "proportional", reason))
    return grants


def _top_k(
    live: list[Ask], pot_cents: int, weights: Mapping[str, float], top_k: int
) -> list[Grant]:
    """Fund the highest-weighted *top_k* asks in full; starve the tail.

    Ranked on ``(-weight, candidate_id)`` so a field of equally unproven
    scopes at the weight floor still ranks deterministically.
    """
    ranked = sorted(live, key=lambda a: (-float(weights.get(a.scope, 0.0)), a.candidate_id))
    funded = {a.candidate_id for a in ranked[: max(0, top_k)]}

    grants: list[Grant] = []
    spent = 0
    for ask in ranked:
        weight = float(weights.get(ask.scope, 0.0))
        if ask.candidate_id not in funded:
            grants.append(Grant(ask.candidate_id, 0, weight, "top_k",
                                f"outside top {top_k} by weight"))
            continue
        cents = min(ask.ask_cents, max(0, pot_cents - spent))
        spent += cents
        reason = (f"top {top_k} by weight" if cents == ask.ask_cents
                  else f"top {top_k}, truncated by remaining pot")
        grants.append(Grant(ask.candidate_id, cents, weight, "top_k", reason))
    return grants


__all__ = ["Ask", "Grant", "POLICIES", "DEFAULT_POLICY", "allocate"]
