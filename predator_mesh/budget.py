"""Mesh budget helpers."""

from __future__ import annotations

from predator_mesh.models import MeshBudget


def build_default_budget(
    max_provider_calls: int = 20,
    max_kalshi_calls: int = 10,
) -> MeshBudget:
    """Return a fresh default budget for a scheduler cycle."""
    return MeshBudget(
        max_provider_calls=max_provider_calls,
        max_kalshi_calls=max_kalshi_calls,
    )
