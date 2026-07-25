# Cross-Candidate Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Divide one capped budget across all simultaneously-qualifying candidates, weighted by each scope's demonstrated contested-Brier advantage, instead of letting the top-ranked candidate drain the pot.

**Architecture:** A pure `allocate()` function sits between a new "ask" pre-pass and the existing grant path. `Allocator.decide()` gains one optional upper bound; every existing cap, gate and firewall stays exactly where it is and still binds. `configs/allocation.json` follows the `autonomy/switches.py` pattern so Dummy Tote can change policy and throttle without a restart.

**Tech Stack:** Python 3, pytest, stdlib only. No new dependencies.

## Global Constraints

- `configs/caps.json` MUST NOT be modified. It is byte-sealed under `PROTECTED_CAPS_SHA256`; any byte change invalidates `caps_strict` and the live-authority chain.
- The allocator may only ever REDUCE a size. Pass 2 takes `min(allocated, budget.max_notional_cents)`.
- `Σ granted_cents <= pot_cents` is inviolable. Rounding residue is dropped, never redistributed.
- `min_weight` is a floor and MUST be `> 0`. Zero is an absorbing state that permanently freezes new scopes out.
- `throttle` is clamped to `[0.0, 1.0]`. No operator value may enlarge the pot.
- `configs/allocation.json` fails safe to `kelly_prorata` at stock defaults — NOT to "deploy everything". This is the opposite failure direction from `switches.py` and is deliberate.
- Spec: `docs/superpowers/specs/2026-07-24-candidate-allocation-design.md`

---

### Task 1: Pure allocation module

**Files:**
- Create: `autonomy/candidate_allocation.py`
- Test: `tests/test_candidate_allocation.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Ask(candidate_id: str, scope: str, ask_cents: int, price_cents: int)`, `Grant(candidate_id: str, granted_cents: int, weight: float, policy: str, reason: str)`, `POLICIES: frozenset[str]`, `allocate(asks: Sequence[Ask], pot_cents: int, weights: Mapping[str, float], policy: str, top_k: int = 5) -> list[Grant]`

- [ ] **Step 1: Write the failing tests**

```python
"""Cross-candidate allocation: dividing one pot among competing asks."""
from __future__ import annotations

import pytest

from autonomy.candidate_allocation import Ask, Grant, allocate

def _asks(*specs):
    return [Ask(candidate_id=cid, scope=scope, ask_cents=cents, price_cents=10)
            for cid, scope, cents in specs]

def _total(grants):
    return sum(g.granted_cents for g in grants)

class TestInvariants:
    def test_never_exceeds_the_pot(self):
        asks = _asks(("a", "s1", 800), ("b", "s2", 800), ("c", "s3", 800))
        for policy in ("kelly_prorata", "proportional", "top_k"):
            grants = allocate(asks, 1000, {"s1": 1.0, "s2": 1.0, "s3": 1.0}, policy)
            assert _total(grants) <= 1000, policy

    def test_never_raises_a_size_above_its_ask(self):
        asks = _asks(("a", "s1", 50), ("b", "s2", 50))
        for policy in ("kelly_prorata", "proportional", "top_k"):
            grants = allocate(asks, 10_000, {"s1": 1.0, "s2": 1.0}, policy)
            by_id = {g.candidate_id: g.granted_cents for g in grants}
            assert by_id["a"] <= 50 and by_id["b"] <= 50, policy

    def test_adding_a_candidate_never_increases_an_existing_grant(self):
        weights = {"s1": 1.0, "s2": 1.0, "s3": 1.0}
        for policy in ("kelly_prorata", "proportional", "top_k"):
            before = allocate(_asks(("a", "s1", 900), ("b", "s2", 900)),
                              1000, weights, policy, top_k=2)
            after = allocate(_asks(("a", "s1", 900), ("b", "s2", 900), ("c", "s3", 900)),
                             1000, weights, policy, top_k=2)
            b_before = {g.candidate_id: g.granted_cents for g in before}
            b_after = {g.candidate_id: g.granted_cents for g in after}
            for cid in ("a", "b"):
                assert b_after[cid] <= b_before[cid], f"{policy}/{cid}"

    def test_higher_weight_never_lowers_its_own_grant(self):
        asks = _asks(("a", "s1", 900), ("b", "s2", 900))
        low = allocate(asks, 1000, {"s1": 0.25, "s2": 1.0}, "kelly_prorata")
        high = allocate(asks, 1000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        a_low = next(g.granted_cents for g in low if g.candidate_id == "a")
        a_high = next(g.granted_cents for g in high if g.candidate_id == "a")
        assert a_high >= a_low

    def test_deterministic_across_calls(self):
        asks = _asks(("a", "s1", 500), ("b", "s1", 500), ("c", "s1", 500))
        first = allocate(asks, 700, {"s1": 1.0}, "kelly_prorata")
        second = allocate(asks, 700, {"s1": 1.0}, "kelly_prorata")
        assert [g.granted_cents for g in first] == [g.granted_cents for g in second]

class TestKellyProrata:
    def test_undersubscribed_deploys_less_than_the_pot(self):
        grants = allocate(_asks(("a", "s1", 100), ("b", "s2", 100)),
                          10_000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        assert _total(grants) == 200

    def test_oversubscribed_scales_everyone_down_proportionally(self):
        grants = allocate(_asks(("a", "s1", 1000), ("b", "s2", 1000)),
                          1000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 500 and by_id["b"] == 500

    def test_weight_shifts_the_split(self):
        grants = allocate(_asks(("a", "s1", 1000), ("b", "s2", 1000)),
                          1000, {"s1": 1.0, "s2": 0.25}, "kelly_prorata")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] > by_id["b"]

class TestProportional:
    def test_splits_the_pot_by_weight_share(self):
        grants = allocate(_asks(("a", "s1", 10_000), ("b", "s2", 10_000)),
                          1000, {"s1": 3.0, "s2": 1.0}, "proportional")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 750 and by_id["b"] == 250

    def test_clamps_to_the_ask_without_redistributing(self):
        grants = allocate(_asks(("a", "s1", 100), ("b", "s2", 10_000)),
                          1000, {"s1": 1.0, "s2": 1.0}, "proportional")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 100
        assert by_id["b"] == 500  # NOT 900 -- no redistribution

class TestTopK:
    def test_funds_only_the_top_k_by_weight(self):
        grants = allocate(
            _asks(("a", "s1", 300), ("b", "s2", 300), ("c", "s3", 300)),
            10_000, {"s1": 1.0, "s2": 0.5, "s3": 0.25}, "top_k", top_k=2)
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 300 and by_id["b"] == 300 and by_id["c"] == 0

class TestDegenerate:
    def test_zero_pot_grants_nothing(self):
        grants = allocate(_asks(("a", "s1", 100)), 0, {"s1": 1.0}, "kelly_prorata")
        assert _total(grants) == 0

    def test_negative_pot_grants_nothing(self):
        grants = allocate(_asks(("a", "s1", 100)), -5, {"s1": 1.0}, "kelly_prorata")
        assert _total(grants) == 0

    def test_no_asks_returns_empty(self):
        assert allocate([], 1000, {}, "kelly_prorata") == []

    def test_nonpositive_ask_is_excluded(self):
        grants = allocate(_asks(("a", "s1", 0), ("b", "s2", 100)),
                          1000, {"s1": 1.0, "s2": 1.0}, "kelly_prorata")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 0 and by_id["b"] == 100

    def test_missing_weight_is_treated_as_zero_contribution_not_a_crash(self):
        grants = allocate(_asks(("a", "unknown_scope", 100)),
                          1000, {}, "kelly_prorata")
        assert _total(grants) == 0

    def test_unknown_policy_falls_back_to_kelly_prorata(self):
        grants = allocate(_asks(("a", "s1", 1000), ("b", "s2", 1000)),
                          1000, {"s1": 1.0, "s2": 1.0}, "nonsense")
        by_id = {g.candidate_id: g.granted_cents for g in grants}
        assert by_id["a"] == 500 and by_id["b"] == 500
        assert all(g.policy == "kelly_prorata" for g in grants)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_candidate_allocation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'autonomy.candidate_allocation'`

- [ ] **Step 3: Write the implementation**

```python
"""Divide one capped pot among candidates competing in the same cycle.

Sizing a single order is ``autonomy.risk_brain``'s job and it does it well.
This module answers the question nothing else asks: when N candidates qualify
at once, who gets how much of the shared budget?

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_candidate_allocation.py -q`
Expected: PASS, 18 passed

- [ ] **Step 5: Commit**

```bash
git add autonomy/candidate_allocation.py tests/test_candidate_allocation.py
git commit -m "feat: pure cross-candidate allocation with three split policies"
```

---

### Task 2: Operator config

**Files:**
- Create: `autonomy/allocation_config.py`
- Create: `configs/allocation.json`
- Test: `tests/test_allocation_config.py`

**Interfaces:**
- Consumes: `POLICIES`, `DEFAULT_POLICY` from Task 1
- Produces: `AllocationConfig` with fields `policy: str`, `top_k: int`, `min_weight: float`, `target_advantage: float`, `throttle: float`; classmethod `AllocationConfig.load(path: Path | None = None) -> AllocationConfig`; `CONFIG_PATH: Path`

- [ ] **Step 1: Write the failing tests**

```python
"""Operator control over allocation: file, env override, and fail-safe defaults."""
from __future__ import annotations

import json

from autonomy.allocation_config import AllocationConfig


def _write(tmp_path, payload):
    path = tmp_path / "allocation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestDefaults:
    def test_missing_file_yields_stock_defaults(self, tmp_path):
        cfg = AllocationConfig.load(tmp_path / "absent.json")
        assert cfg.policy == "kelly_prorata"
        assert cfg.top_k == 5
        assert cfg.min_weight == 0.25
        assert cfg.target_advantage == 0.02
        assert cfg.throttle == 1.0

    def test_malformed_file_fails_safe_to_defaults_not_to_full_deployment(self, tmp_path):
        path = tmp_path / "allocation.json"
        path.write_text("{not json", encoding="utf-8")
        cfg = AllocationConfig.load(path)
        assert cfg.policy == "kelly_prorata"
        assert cfg.throttle == 1.0

    def test_unknown_policy_falls_back(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {"policy": "nonsense"}))
        assert cfg.policy == "kelly_prorata"


class TestFileValues:
    def test_reads_every_key(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {
            "policy": "top_k", "top_k": 3, "min_weight": 0.4,
            "target_advantage": 0.05, "throttle": 0.5,
        }))
        assert (cfg.policy, cfg.top_k, cfg.min_weight) == ("top_k", 3, 0.4)
        assert (cfg.target_advantage, cfg.throttle) == (0.05, 0.5)


class TestClamps:
    def test_throttle_clamped_to_unit_interval(self, tmp_path):
        assert AllocationConfig.load(_write(tmp_path, {"throttle": 5.0})).throttle == 1.0
        assert AllocationConfig.load(_write(tmp_path, {"throttle": -1.0})).throttle == 0.0

    def test_min_weight_never_zero(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {"min_weight": 0.0}))
        assert cfg.min_weight > 0.0

    def test_min_weight_capped_at_one(self, tmp_path):
        assert AllocationConfig.load(_write(tmp_path, {"min_weight": 9.0})).min_weight == 1.0

    def test_top_k_never_negative(self, tmp_path):
        assert AllocationConfig.load(_write(tmp_path, {"top_k": -3})).top_k == 0

    def test_garbage_types_fall_back_per_key(self, tmp_path):
        cfg = AllocationConfig.load(_write(tmp_path, {
            "top_k": "lots", "throttle": None, "min_weight": [],
        }))
        assert cfg.top_k == 5 and cfg.throttle == 1.0 and cfg.min_weight == 0.25


class TestEnvOverride:
    def test_env_beats_file(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"policy": "top_k", "throttle": 0.2})
        monkeypatch.setenv("DUMMY_ALLOC_POLICY", "proportional")
        monkeypatch.setenv("DUMMY_ALLOC_THROTTLE", "0.75")
        cfg = AllocationConfig.load(path)
        assert cfg.policy == "proportional" and cfg.throttle == 0.75

    def test_garbage_env_is_ignored_in_favour_of_the_file(self, tmp_path, monkeypatch):
        path = _write(tmp_path, {"throttle": 0.3})
        monkeypatch.setenv("DUMMY_ALLOC_THROTTLE", "banana")
        assert AllocationConfig.load(path).throttle == 0.3

    def test_env_throttle_is_clamped_too(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DUMMY_ALLOC_THROTTLE", "99")
        assert AllocationConfig.load(tmp_path / "absent.json").throttle == 1.0


class TestShippedConfig:
    def test_repo_config_parses_to_documented_defaults(self):
        from autonomy.allocation_config import CONFIG_PATH
        cfg = AllocationConfig.load(CONFIG_PATH)
        assert cfg.policy == "kelly_prorata"
        assert cfg.throttle == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_allocation_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'autonomy.allocation_config'`

- [ ] **Step 3: Write `configs/allocation.json`**

```json
{
  "policy": "kelly_prorata",
  "top_k": 5,
  "min_weight": 0.25,
  "target_advantage": 0.02,
  "throttle": 1.0
}
```

- [ ] **Step 4: Write the implementation**

```python
"""Operator control over how the cycle budget is split.

Follows ``autonomy/switches.py``: ``configs/allocation.json`` is the source of
truth, a per-key ``DUMMY_ALLOC_*`` environment variable overrides it, and the
file is read fresh every cycle so a scheduled task picks up an edit on its next
fire without a restart.

FAIL-SAFE DIRECTION DIFFERS FROM switches.py, deliberately.  ``switches.py``
fails all-ON because a corrupt file must never silently stop trading.  This
file fails to the DEFAULT POLICY at stock parameters, because a corrupt file
must never read as "deploy everything".  Same pattern, opposite direction, for
the same reason: degrade toward the safe outcome for the thing being
configured.

``throttle`` is clamped to [0, 1] and can only shrink the pot.  There is no
operator value here that enlarges it; enlarging requires the sealed-caps
ceremony in ``core/caps_authority.py``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autonomy.candidate_allocation import DEFAULT_POLICY, POLICIES

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "allocation.json"

DEFAULT_TOP_K = 5
DEFAULT_MIN_WEIGHT = 0.25
DEFAULT_TARGET_ADVANTAGE = 0.02
DEFAULT_THROTTLE = 1.0

# A weight floor of exactly zero is an absorbing state: a scope that can never
# be allocated can never settle, never accrue evidence, and never earn its way
# up.  Clamp to something small but non-zero instead.
MIN_WEIGHT_FLOOR = 0.01


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    return result if result == result and result not in (float("inf"), float("-inf")) else default


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        value = float(raw.strip())
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        return int(raw.strip())
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class AllocationConfig:
    policy: str = DEFAULT_POLICY
    top_k: int = DEFAULT_TOP_K
    min_weight: float = DEFAULT_MIN_WEIGHT
    target_advantage: float = DEFAULT_TARGET_ADVANTAGE
    throttle: float = DEFAULT_THROTTLE

    @classmethod
    def load(cls, path: Path | None = None) -> "AllocationConfig":
        target = Path(path) if path is not None else CONFIG_PATH
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except (OSError, ValueError, TypeError):
            raw = {}

        policy = os.environ.get("DUMMY_ALLOC_POLICY") or raw.get("policy")
        if policy not in POLICIES:
            policy = DEFAULT_POLICY

        top_k = _env_int("DUMMY_ALLOC_TOP_K")
        if top_k is None:
            top_k = _as_int(raw.get("top_k"), DEFAULT_TOP_K)

        min_weight = _env_float("DUMMY_ALLOC_MIN_WEIGHT")
        if min_weight is None:
            min_weight = _as_float(raw.get("min_weight"), DEFAULT_MIN_WEIGHT)

        target_advantage = _env_float("DUMMY_ALLOC_TARGET_ADVANTAGE")
        if target_advantage is None:
            target_advantage = _as_float(
                raw.get("target_advantage"), DEFAULT_TARGET_ADVANTAGE)

        throttle = _env_float("DUMMY_ALLOC_THROTTLE")
        if throttle is None:
            throttle = _as_float(raw.get("throttle"), DEFAULT_THROTTLE)

        return cls(
            policy=policy,
            top_k=max(0, top_k),
            min_weight=_clamp(min_weight, MIN_WEIGHT_FLOOR, 1.0),
            target_advantage=max(1e-6, target_advantage),
            throttle=_clamp(throttle, 0.0, 1.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "top_k": self.top_k,
            "min_weight": round(self.min_weight, 4),
            "target_advantage": round(self.target_advantage, 6),
            "throttle": round(self.throttle, 4),
        }


__all__ = ["CONFIG_PATH", "AllocationConfig"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_allocation_config.py -q`
Expected: PASS, 14 passed

- [ ] **Step 6: Commit**

```bash
git add autonomy/allocation_config.py configs/allocation.json tests/test_allocation_config.py
git commit -m "feat: operator-controlled allocation config, fail-safe to default policy"
```

---

### Task 3: Weight resolution from contested-Brier advantage

**Files:**
- Create: `autonomy/allocation_weights.py`
- Test: `tests/test_allocation_weights.py`

**Interfaces:**
- Consumes: `AllocationConfig` from Task 2
- Produces: `weight_for_advantage(advantage: float | None, *, min_weight: float, target_advantage: float) -> float`; `weights_for_scopes(scopes: Iterable[str], advantages: Mapping[str, float | None], *, config: AllocationConfig) -> dict[str, float]`

- [ ] **Step 1: Write the failing tests**

```python
"""Turning contested-Brier advantage into an allocation weight."""
from __future__ import annotations

from autonomy.allocation_config import AllocationConfig
from autonomy.allocation_weights import weight_for_advantage, weights_for_scopes

CFG = AllocationConfig(min_weight=0.25, target_advantage=0.02)


class TestWeightForAdvantage:
    def test_unknown_advantage_gets_the_floor_not_zero(self):
        assert weight_for_advantage(None, min_weight=0.25, target_advantage=0.02) == 0.25

    def test_negative_advantage_gets_the_floor(self):
        assert weight_for_advantage(-0.05, min_weight=0.25, target_advantage=0.02) == 0.25

    def test_zero_advantage_gets_the_floor(self):
        assert weight_for_advantage(0.0, min_weight=0.25, target_advantage=0.02) == 0.25

    def test_advantage_at_target_earns_full_weight(self):
        assert weight_for_advantage(0.02, min_weight=0.25, target_advantage=0.02) == 1.0

    def test_advantage_above_target_is_capped_at_one(self):
        assert weight_for_advantage(0.50, min_weight=0.25, target_advantage=0.02) == 1.0

    def test_partial_advantage_interpolates_above_the_floor(self):
        w = weight_for_advantage(0.01, min_weight=0.25, target_advantage=0.02)
        assert 0.25 < w < 1.0

    def test_monotone_in_advantage(self):
        weights = [weight_for_advantage(a, min_weight=0.25, target_advantage=0.02)
                   for a in (0.0, 0.005, 0.01, 0.015, 0.02, 0.03)]
        assert weights == sorted(weights)


class TestWeightsForScopes:
    def test_every_requested_scope_is_present(self):
        out = weights_for_scopes(["a", "b"], {"a": 0.02}, config=CFG)
        assert set(out) == {"a", "b"}

    def test_missing_scope_falls_to_the_floor(self):
        out = weights_for_scopes(["a", "b"], {"a": 0.02}, config=CFG)
        assert out["a"] == 1.0 and out["b"] == 0.25

    def test_no_weight_is_ever_zero(self):
        out = weights_for_scopes(["a", "b", "c"], {}, config=CFG)
        assert all(w > 0.0 for w in out.values())

    def test_non_numeric_advantage_is_treated_as_unknown(self):
        out = weights_for_scopes(["a"], {"a": "banana"}, config=CFG)
        assert out["a"] == 0.25

    def test_empty_scopes_returns_empty(self):
        assert weights_for_scopes([], {"a": 0.02}, config=CFG) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_allocation_weights.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'autonomy.allocation_weights'`

- [ ] **Step 3: Write the implementation**

```python
"""Allocation weight from a scope's demonstrated edge over the market.

The driver is CONTESTED BRIER ADVANTAGE: how much better the model's Brier
score is than the market's own price, on the same rows.  See
``autonomy/scope_analytics.py``, where ``brier_edge = market_brier -
model_brier_contested`` and a positive number means the model beat the line.

The LOWER 95% BOUND is used, not the point estimate -- the same quantity the
promotion gate already tests for ``> 0`` in ``autonomy/backtest.py``.  A scope
with twelve lucky rows must not size up on evidence its sample count cannot
support; the bound collapses toward the floor when n is small, which is exactly
the behaviour wanted.

The floor is never zero.  A scope that can never be allocated can never settle,
never accrue evidence, and never earn a higher weight -- zero is an absorbing
state.  Deciding whether a scope may trade at all belongs to the promotion and
tier gates; this module only sizes what those gates already passed.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from autonomy.allocation_config import AllocationConfig


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if result != result or abs(result) == float("inf"):
        return None
    return result


def weight_for_advantage(
    advantage: float | None, *, min_weight: float, target_advantage: float
) -> float:
    """Map a contested-Brier advantage onto ``[min_weight, 1.0]``.

    Unknown, non-positive, or unusable advantage all resolve to the floor.
    """
    value = _numeric(advantage)
    if value is None or value <= 0.0 or target_advantage <= 0.0:
        return min_weight
    fraction = min(1.0, value / target_advantage)
    return min_weight + (1.0 - min_weight) * fraction


def weights_for_scopes(
    scopes: Iterable[str],
    advantages: Mapping[str, Any],
    *,
    config: AllocationConfig,
) -> dict[str, float]:
    """Resolve a weight for every scope, defaulting unknowns to the floor."""
    return {
        scope: weight_for_advantage(
            advantages.get(scope),
            min_weight=config.min_weight,
            target_advantage=config.target_advantage,
        )
        for scope in scopes
    }


__all__ = ["weight_for_advantage", "weights_for_scopes"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_allocation_weights.py -q`
Expected: PASS, 12 passed

- [ ] **Step 5: Commit**

```bash
git add autonomy/allocation_weights.py tests/test_allocation_weights.py
git commit -m "feat: allocation weight from lower-95 contested Brier advantage"
```

---

### Task 4: Allocator honours an allocation cap

**Files:**
- Modify: `autonomy/allocator.py` (the `decide` signature, and line 223)
- Test: `tests/test_allocator_allocation_cap.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (deliberately — this keeps `allocator.py` free of allocation imports)
- Produces: `Allocator.decide(..., allocation_cap_cents: int | None = None)`. When not None, the granted notional is `min(budget.max_notional_cents, allocation_cap_cents)`.

- [ ] **Step 1: Write the failing test**

```python
"""The allocation cap is an additional upper bound on an already-approved size."""
from __future__ import annotations

import inspect

from autonomy.allocator import Allocator


def test_decide_accepts_an_allocation_cap():
    sig = inspect.signature(Allocator.decide)
    assert "allocation_cap_cents" in sig.parameters
    assert sig.parameters["allocation_cap_cents"].default is None


def test_allocation_cap_is_keyword_only():
    sig = inspect.signature(Allocator.decide)
    assert sig.parameters["allocation_cap_cents"].kind is inspect.Parameter.KEYWORD_ONLY
```

Add to the same file a behavioural test using the repo's existing allocator
fixtures. Locate them first:

```bash
grep -rln "Allocator(" tests/ | head -5
```

Reuse the construction pattern from whichever existing test file builds an
`Allocator` with a real `RiskBrain`, then assert:

```python
def test_cap_reduces_count_but_never_raises_it(<fixtures from the existing test>):
    uncapped = allocator.decide(market, forecast, state, 0)
    capped = allocator.decide(market, forecast, state, 0,
                              allocation_cap_cents=uncapped.notional_cents // 2)
    assert capped.count <= uncapped.count
    assert capped.notional_cents <= uncapped.notional_cents

def test_cap_above_the_budget_changes_nothing(<same fixtures>):
    uncapped = allocator.decide(market, forecast, state, 0)
    generous = allocator.decide(market, forecast, state, 0,
                                allocation_cap_cents=10_000_000)
    assert generous.count == uncapped.count

def test_zero_cap_abstains(<same fixtures>):
    decision = allocator.decide(market, forecast, state, 0, allocation_cap_cents=0)
    assert decision.count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_allocator_allocation_cap.py -q`
Expected: FAIL — `assert 'allocation_cap_cents' in sig.parameters`

- [ ] **Step 3: Modify `autonomy/allocator.py`**

Add the keyword-only parameter to `decide`. Find the signature (it currently
ends with `group_open_count`) and append:

```python
        *,
        allocation_cap_cents: int | None = None,
```

(If `group_exposure_cents` / `group_open_count` are already keyword-only after
a `*`, just add `allocation_cap_cents` alongside them rather than a second `*`.)

Then replace line 223:

```python
        count = budget.max_notional_cents // price
```

with:

```python
        # The cross-candidate allocator (autonomy/candidate_allocation) may cap
        # this candidate below what the risk brain alone would allow, so that a
        # top-ranked market cannot drain the cycle's whole pot.  It can only
        # ever REDUCE: the risk brain, the caps and the firewall all still bind
        # afterwards.
        grantable = budget.max_notional_cents
        if allocation_cap_cents is not None:
            grantable = min(grantable, max(0, int(allocation_cap_cents)))
        if grantable < price:
            return _abstain(
                market, forecast,
                f"allocation: granted {grantable}c below one contract at {price}c",
                budget.risk_snapshot, side=side, price_cents=price,
                ev_cents=ev, kelly=kelly,
            )
        count = grantable // price
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_allocator_allocation_cap.py -q`
Expected: PASS

- [ ] **Step 5: Verify no existing allocator behaviour regressed**

Run: `python -m pytest tests/ -q -k "allocator or risk_brain or brain"`
Expected: PASS, no failures. The new parameter defaults to `None`, so every
existing call site is unaffected.

- [ ] **Step 6: Commit**

```bash
git add autonomy/allocator.py tests/test_allocator_allocation_cap.py
git commit -m "feat: allocator accepts a cross-candidate allocation cap"
```

---

### Task 5: Two-pass wiring in the brain

**Files:**
- Modify: `autonomy/brain.py` (around the decision loop at line 1008)
- Test: `tests/test_brain_allocation_pass.py`

**Interfaces:**
- Consumes: `allocate`, `Ask` (Task 1); `AllocationConfig` (Task 2); `weights_for_scopes` (Task 3); `allocation_cap_cents` (Task 4)
- Produces: nothing downstream

**Implementation note for the engineer:** the existing loop accumulates
exposure as it goes (`cycle_group_cents`, `cycle_group_count`), which is what
makes allocation order-dependent today. Do NOT try to remove that
accumulation — it is doing real work for correlation caps. Instead compute the
asks in a cheap pre-pass, allocate once, then pass each market's grant into the
existing loop as `allocation_cap_cents`.

- [ ] **Step 1: Write the failing test**

```python
"""The brain divides one pot across the cycle instead of first-come-first-served."""
from __future__ import annotations

from autonomy.candidate_allocation import Ask, allocate


def test_two_candidates_cannot_both_take_the_whole_pot():
    """Regression for the greedy path: allocator.py:223 used to hand the first
    candidate the entire remaining budget."""
    asks = [Ask("first", "scope_a", 1000, 10), Ask("second", "scope_b", 1000, 10)]
    grants = allocate(asks, 1000, {"scope_a": 1.0, "scope_b": 1.0}, "kelly_prorata")
    assert sum(g.granted_cents for g in grants) <= 1000
    assert all(g.granted_cents > 0 for g in grants), "both must be funded"


def test_brain_module_imports_the_allocation_pass():
    import autonomy.brain as brain
    source = open(brain.__file__, encoding="utf-8").read()
    assert "candidate_allocation" in source
    assert "allocation_cap_cents" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_brain_allocation_pass.py -q`
Expected: FAIL on `test_brain_module_imports_the_allocation_pass`

- [ ] **Step 3: Add the pre-pass to `autonomy/brain.py`**

Immediately before the decision loop that contains `allocator.decide(` at
line 1008, insert:

```python
        # Cross-candidate allocation: divide ONE pot across everything that
        # qualifies this cycle, weighted by each scope's demonstrated
        # contested-Brier advantage.  Without this the loop below is greedy --
        # whoever is ranked first takes as much as its own caps allow and the
        # rest compete for the remainder.
        from autonomy.allocation_config import AllocationConfig
        from autonomy.allocation_weights import weights_for_scopes
        from autonomy.candidate_allocation import Ask, allocate

        alloc_config = AllocationConfig.load()
        stage_limits = STAGE_LIMITS[state.stage]
        pot_cents = int(
            max(0, int(state.bankroll_cents * float(stage_limits["total_frac"]))
                - state.open_exposure_cents)
            * alloc_config.throttle
        )
        alloc_asks = [
            Ask(
                candidate_id=market.ticker,
                scope=self._allocation_scope(market, forecast),
                ask_cents=int(stage_limits["order_abs_cents"]),
                price_cents=1,
            )
            for market, forecast, _signals in scored
        ]
        alloc_weights = weights_for_scopes(
            {a.scope for a in alloc_asks},
            self._scope_advantages(),
            config=alloc_config,
        )
        alloc_grants = {
            g.candidate_id: g.granted_cents
            for g in allocate(alloc_asks, pot_cents, alloc_weights,
                              alloc_config.policy, top_k=alloc_config.top_k)
        }
        report.notes.append(
            "allocation=" + json.dumps(
                {"policy": alloc_config.policy, "pot_cents": pot_cents,
                 "candidates": len(alloc_asks),
                 "granted_cents": sum(alloc_grants.values())},
                sort_keys=True)
        )
```

Then pass the grant into the existing call at line 1008:

```python
            decision = allocator.decide(
                market, forecast, state,
                self._market_exposure(state, market.ticker),
                group_exposure_cents=group_cents,
                group_open_count=group_count,
                allocation_cap_cents=alloc_grants.get(market.ticker),
            )
```

Ensure `STAGE_LIMITS` is imported in `brain.py`; if it is not, add
`from autonomy.risk_brain import STAGE_LIMITS` to the existing risk_brain
import.

- [ ] **Step 4: Add the two helper methods to the brain class**

```python
    def _allocation_scope(self, market, forecast) -> str:
        """The grading scope this candidate's weight is looked up under.

        Falls back to the ticker so an unmappable market still allocates (at
        the weight floor) rather than crashing the cycle.
        """
        try:
            from autonomy.taxonomy import grading_scope

            return grading_scope("fused", market.ticker, getattr(forecast, "features", None))
        except Exception:
            return market.ticker

    def _scope_advantages(self) -> dict[str, float]:
        """Per-scope contested-Brier advantage (lower 95% bound).

        Reads the latest dashboard snapshot rather than the ledger: this runs
        every cycle and must never take a ledger lock.  An absent or unreadable
        snapshot yields an empty map, which resolves every scope to the weight
        floor -- the honest "no evidence yet" answer.
        """
        try:
            snapshot = json.loads(
                Path("runtime/autonomy/latest_dashboard_snapshot.json")
                .read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return {}
        surface = snapshot.get("trust_surface_by_specialist")
        if not isinstance(surface, dict):
            return {}
        out: dict[str, float] = {}
        for bucket in surface.values():
            if not isinstance(bucket, dict):
                continue
            for scope, row in (bucket.get("scopes") or {}).items():
                if isinstance(row, dict):
                    value = row.get("contested_brier_advantage_lower95")
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        out[str(scope)] = float(value)
        return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_brain_allocation_pass.py -q`
Expected: PASS

- [ ] **Step 6: Run the full brain and allocator suites**

Run: `python -m pytest tests/ -q -k "brain or allocator or risk_brain or cycle"`
Expected: PASS. If a test fails because a cycle now deploys less, that is the
feature working — confirm the assertion was pinning greedy behaviour before
changing it, and say so in the commit.

- [ ] **Step 7: Commit**

```bash
git add autonomy/brain.py tests/test_brain_allocation_pass.py
git commit -m "feat: divide the cycle pot across candidates instead of first-come-first-served"
```

---

### Task 6: Dummy Tote control surface

**Files:**
- Modify: `desktop/dummy_tote/data.py` (read-only accessor)
- Modify: the tote view that already renders the switches card
- Test: `tests/test_tote_allocation_surface.py`

**Interfaces:**
- Consumes: `AllocationConfig` (Task 2)
- Produces: `read_allocation_config() -> dict`, `write_allocation_config(**changes) -> None`

**Implementation note:** `desktop/dummy_tote/data.py` is deliberately pure and
read-only for runtime artifacts. Allocation control is *operator config*, not a
runtime artifact — the same category as `configs/switches.json`, which the app
already writes. Put the writer next to the existing switch writer, not in
`data.py`. Locate it first:

```bash
grep -rn "switches" desktop/dummy_tote/ | head -20
```

- [ ] **Step 1: Write the failing test**

```python
"""The tote app can read and change allocation policy without a restart."""
from __future__ import annotations

import json

from autonomy.allocation_config import AllocationConfig


def test_round_trip_through_the_config_file(tmp_path):
    path = tmp_path / "allocation.json"
    path.write_text(json.dumps({
        "policy": "kelly_prorata", "top_k": 5, "min_weight": 0.25,
        "target_advantage": 0.02, "throttle": 1.0,
    }), encoding="utf-8")

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["policy"] = "top_k"
    payload["throttle"] = 0.5
    path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = AllocationConfig.load(path)
    assert cfg.policy == "top_k" and cfg.throttle == 0.5


def test_written_config_survives_a_reload_unchanged(tmp_path):
    path = tmp_path / "allocation.json"
    original = AllocationConfig(policy="proportional", top_k=3, min_weight=0.4,
                                target_advantage=0.05, throttle=0.75)
    path.write_text(json.dumps(original.to_dict()), encoding="utf-8")
    assert AllocationConfig.load(path) == original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tote_allocation_surface.py -q`
Expected: FAIL — `to_dict` round-trip mismatch or missing writer

- [ ] **Step 3: Add the writer next to the existing switch writer**

Mirror whatever the switch writer does (atomic tmp + `os.replace`), writing
`AllocationConfig.to_dict()` to `configs/allocation.json`. Do not invent a new
persistence pattern.

- [ ] **Step 4: Add the tote UI control**

A policy selector (three options), a throttle slider bound to `[0.0, 1.0]`, and
a read-only display of the last cycle's `allocation=` note from the report, so
a shrunken size is visible rather than mysterious.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_tote_allocation_surface.py -q`
Expected: PASS

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q -p no:randomly`
Expected: PASS. Check `PIPESTATUS[0]` if you pipe the output — piping through
`tail` reports `tail`'s exit code, not pytest's.

- [ ] **Step 7: Commit**

```bash
git add desktop/dummy_tote tests/test_tote_allocation_surface.py
git commit -m "feat: allocation policy and throttle controls in Dummy Tote"
```

---

## Self-review notes

**Spec coverage:** pot definition → Task 5; three policies → Task 1; weights from
lower-95 contested Brier → Task 3; operator config with env override and inverted
fail-safe → Task 2; caps untouched and reduce-only → Task 4 constraint plus the
`min` in step 3; failure-mode table → Tasks 1–3 degenerate tests; property tests →
Task 1; tote surface → Task 6.

**Known gap, deliberate:** Task 5's `ask_cents` uses the stage's flat
`order_abs_cents` rather than a per-candidate Kelly ask. A true Kelly ask needs
the price/EV computation that currently lives inside `decide()`, and extracting
it is a refactor worth its own task. The flat ask still fixes the three defects
in the spec (order-dependence, pot-draining, N-blindness); it just weights on
scope quality rather than on per-candidate Kelly. Extracting `_price_and_kelly()`
so the pre-pass can compute real Kelly asks is the natural follow-up.
