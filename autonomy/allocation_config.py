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
import math
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
    return result if math.isfinite(result) else default


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
    return value if math.isfinite(value) else None


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


__all__ = ["CONFIG_PATH", "AllocationConfig", "MIN_WEIGHT_FLOOR"]
