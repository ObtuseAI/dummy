"""Fail-closed starvation state for missing resource measurements."""

from __future__ import annotations

from .models import ResourceUsage


def starvation_state(usage: ResourceUsage) -> dict[str, object]:
    return {
        "starved": bool(usage.unmeasured),
        "unmeasured_resources": list(usage.unmeasured),
        "reason": (
            "resource_measurements_incomplete"
            if usage.unmeasured
            else "resource_measurements_complete"
        ),
        "may_expand_resources": False,
    }
