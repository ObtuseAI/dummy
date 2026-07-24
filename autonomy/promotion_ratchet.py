"""Per-scope promotion ratchet: cheap to earn once, dearer to earn again.

Owner directive 2026-07-24 (Wave-86): "if it has a minimal positive ROI it has
a place. if its roi turns negative it gets demoted and the threshold gets
raised for a second promotion. all autonomously."

This is what makes a LOW first bar defensible. A scope that has never failed
enters on minimal positive evidence. Every autonomous demotion is remembered,
and each subsequent attempt must clear a strictly harder bar -- more independent
clusters and a higher ROI floor. A source that keeps decaying prices itself out
of the ensemble without anyone intervening, while a genuinely good source that
got unlucky once can still earn its way back.

Two properties this file exists to guarantee:

* The ratchet only ever tightens. Requirements are a pure function of the
  recorded demotion count, so nothing can quietly reset a scope's history and
  re-enter at the easy bar.
* Re-promotion stays POSSIBLE. The pre-existing rule was that a demotion never
  un-sticks until a human clears it, which under autonomous operation would
  mean a single bad patch banned a source forever. Here a demotion raises the
  price instead of closing the door.

Fusion membership only. Nothing here confers session, execution, or capital
authority.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RATCHET_PATH = Path("runtime/autonomy/promotion_ratchet.json")

#: Multiplier applied to the required independent-cluster count per prior
#: demotion. 2.0 means attempt 2 needs double the evidence of attempt 1.
CLUSTER_RATCHET_FACTOR = 2.0

#: Additive ROI floor per prior demotion, in the same units as the forward
#: evidence CI (dollars per contract). Attempt 1 needs only "> 0"; each later
#: attempt must clear a visibly larger margin, not merely a positive point
#: estimate on a noisy sample.
ROI_RATCHET_STEP = 0.01

#: Hard stop. A scope demoted this many times has told us what it is.
MAX_ATTEMPTS = 5

__all__ = [
    "CLUSTER_RATCHET_FACTOR",
    "MAX_ATTEMPTS",
    "ROI_RATCHET_STEP",
    "RatchetState",
    "load_ratchet",
    "record_demotion",
    "requirements_for",
    "save_ratchet",
]


class RatchetState(dict):
    """``{scope: {"demotions": int, "last_demoted_at": iso, "history": [...]}}``."""


def load_ratchet(path: Path | str = DEFAULT_RATCHET_PATH) -> RatchetState:
    try:
        blob = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return RatchetState()
    scopes = blob.get("scopes") if isinstance(blob, dict) else None
    return RatchetState(scopes if isinstance(scopes, dict) else {})


def save_ratchet(state: RatchetState, path: Path | str = DEFAULT_RATCHET_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"scopes": dict(state), "policy": {
            "cluster_ratchet_factor": CLUSTER_RATCHET_FACTOR,
            "roi_ratchet_step": ROI_RATCHET_STEP,
            "max_attempts": MAX_ATTEMPTS,
        }}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(target)


def demotion_count(state: RatchetState, scope: str) -> int:
    entry = state.get(scope) or {}
    try:
        return max(0, int(entry.get("demotions", 0)))
    except (TypeError, ValueError):
        return 0


def record_demotion(
    state: RatchetState,
    scope: str,
    *,
    reason: str = "",
    roi: float | None = None,
    at: str | None = None,
) -> RatchetState:
    """Remember a demotion. Monotonic: the count never decreases."""
    entry = dict(state.get(scope) or {})
    count = demotion_count(state, scope) + 1
    stamp = at or datetime.now(timezone.utc).isoformat()
    history = list(entry.get("history") or [])
    history.append({"at": stamp, "reason": reason, "roi": roi, "attempt": count})
    entry.update({
        "demotions": count,
        "last_demoted_at": stamp,
        "history": history[-20:],          # bounded; the count is the authority
    })
    state[scope] = entry
    return state


def requirements_for(
    state: RatchetState,
    scope: str,
    *,
    base_clusters: int,
    base_roi_floor: float = 0.0,
) -> dict[str, Any]:
    """The bar this scope must clear on its NEXT promotion attempt.

    Attempt 1 (never demoted) is the operator's minimal bar: the base cluster
    count and a strictly positive ROI lower bound. Each recorded demotion
    multiplies the cluster requirement and adds to the ROI floor.
    """
    count = demotion_count(state, scope)
    banned = count >= MAX_ATTEMPTS
    required_clusters = int(
        math.ceil(base_clusters * (CLUSTER_RATCHET_FACTOR ** count))
    )
    required_roi = float(base_roi_floor) + (ROI_RATCHET_STEP * count)
    return {
        "scope": scope,
        "prior_demotions": count,
        "attempt": count + 1,
        "required_forward_clusters": required_clusters,
        "required_roi_ci95_lower": required_roi,
        "eligible_for_retry": not banned,
        "max_attempts": MAX_ATTEMPTS,
        "reason": ("retired_after_max_demotions" if banned else "ratchet_active"),
    }


def clears_ratchet(
    state: RatchetState,
    scope: str,
    *,
    forward_clusters: int,
    roi_ci95_lower: float | None,
    base_clusters: int,
    base_roi_floor: float = 0.0,
) -> dict[str, Any]:
    """Whether a candidate clears its own escalated bar. Fails closed."""
    need = requirements_for(
        state, scope, base_clusters=base_clusters, base_roi_floor=base_roi_floor,
    )
    checks = {
        "eligible_for_retry": bool(need["eligible_for_retry"]),
        "forward_clusters": int(forward_clusters) >= need["required_forward_clusters"],
        # Strictly greater than the floor: a ROI whose CI lower bound sits on
        # zero is not evidence of an edge, it is evidence of a coin flip.
        "roi_ci95_lower": (
            roi_ci95_lower is not None
            and float(roi_ci95_lower) > need["required_roi_ci95_lower"]
        ),
    }
    return {
        **need,
        "measured_forward_clusters": int(forward_clusters),
        "measured_roi_ci95_lower": roi_ci95_lower,
        "checks": checks,
        "pass": all(checks.values()),
        "failures": sorted(name for name, ok in checks.items() if not ok),
    }
