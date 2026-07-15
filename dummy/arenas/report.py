"""Aggregate reproducibility report for the canonical arena catalog."""

from __future__ import annotations

from typing import Any

from dummy.arenas.catalog import arena_catalog
from dummy.arenas.models import ArenaInput
from dummy.arenas.runner import replay_arena
from dummy.world_model.models import digest_json


def arena_reproducibility_report() -> dict[str, Any]:
    inputs = ArenaInput(
        forecast_probability=0.61,
        market_prior=0.56,
        uncertainty=0.16,
        evidence_ids=("phase7-mechanical-fixture",),
    )
    results = [replay_arena(item, inputs) for item in arena_catalog()]
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 7,
        "status": "MECHANICS_VALIDATED_NO_EMPIRICAL_CLAIM",
        "scenario_count": len(results),
        "deterministic_count": sum(bool(item["deterministic"]) for item in results),
        "passing_count": sum(bool(item["passed"]) for item in results),
        "results": results,
        "runtime_episode_count": 0,
        "empirical_claim_supported": False,
        "execution_authority": False,
    }
    body["report_id"] = digest_json(body)
    return body


__all__ = ["arena_reproducibility_report"]
