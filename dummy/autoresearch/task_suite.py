"""Sealed three-way task partitions for nested forecast research."""

from __future__ import annotations

from typing import Any

from dummy.world_model.models import digest_json

from .models import EvaluationPartition, ResearchTask, TaskSuite


def build_task_suite(tasks: tuple[ResearchTask, ...]) -> TaskSuite:
    """Build a content-addressed suite after group-level leakage checks."""

    return TaskSuite.create(tasks)


def task_suite_policy_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "partitions": [item.value for item in EvaluationPartition],
        "partition_law": {
            "event_clusters_disjoint": True,
            "selection_keys_disjoint": True,
            "evidence_ids_disjoint": True,
            "private_item_feedback_to_outer_loop": False,
            "private_aggregate_feedback_to_outer_loop": True,
            "external_used_for_selection": False,
            "external_used_for_claims_and_transfer_only": True,
        },
        "hidden_selection_dimensions": [
            "event_cluster",
            "date",
            "strike_family",
            "team_or_symbol",
        ],
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = ["build_task_suite", "task_suite_policy_manifest"]
