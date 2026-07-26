"""Fail-closed lifecycle vocabulary for harvested repository adapters."""

from __future__ import annotations

from typing import Any

DORMANT = "DORMANT"
DORMANT_TEST_STATUS = "DORMANT_UNVERIFIED"
VERIFIED_CHALLENGER = "VERIFIED_CHALLENGER"
DORMANT_REASON = "upstream_integration_and_challenger_grade_not_verified"


def dormant_adapter_record(
    entry: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """Return an unverified adapter row with every authority bit removed."""

    return {
        **entry,
        "lifecycle_status": DORMANT,
        "integration_status": DORMANT,
        "integration_kind": (
            "metadata_only"
            if entry.get("integration_kind") != "upstream_adapter"
            else "upstream_adapter"
        ),
        "test_status": DORMANT_TEST_STATUS,
        "tests_passed": False,
        "upstream_integration_verified": False,
        "challenger_graded": False,
        "production_capability": False,
        "prediction_authority": False,
        "execution_authority": False,
        "dormant_reason": reason or DORMANT_REASON,
    }


__all__ = [
    "DORMANT",
    "DORMANT_REASON",
    "DORMANT_TEST_STATUS",
    "VERIFIED_CHALLENGER",
    "dormant_adapter_record",
]
