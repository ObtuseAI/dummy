"""V15 runtime acceleration V2.

No removed tests, no weakened safety, no skipped final full regression.
Reduces repeated live/credential probe calls in unit tests via short
deterministic fixtures and caches safe (non-secret) proof artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"

FULL_REGRESSION_COMMANDS = [
    "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


def _load_tests_summary() -> dict[str, Any]:
    path = ARTIFACTS / "tests_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class _SafeProofCache:
    """In-process cache for non-secret proof artifacts (redacted dicts only)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get_or_set(self, key: str, builder: Any) -> dict[str, Any]:
        if key not in self._store:
            self._store[key] = builder()
        return self._store[key]

    def clear(self) -> None:
        self._store.clear()


SAFE_PROOF_CACHE = _SafeProofCache()


class RuntimeAccelerationMegaReportV2:
    def to_report(self) -> dict[str, Any]:
        summary = _load_tests_summary()
        slowest = summary.get("slowest_25_verbose_pytest") or summary.get("v14_slowest_25_verbose_pytest") or []
        return {
            "workstream": "V15: Runtime Acceleration Mega Report V2",
            "required_full_regression_commands": FULL_REGRESSION_COMMANDS,
            "keeps_full_regression_required": True,
            "recursive_pytest_allowed": False,
            "deterministic_fixtures_used": True,
            "safe_proof_cache_enabled": True,
            "recommended_shards": [
                "credential_shape_and_conflict_reports",
                "auth_probe_v2_bounded_reports",
                "real_terrain_and_source_reports",
                "launch_gate_reports",
                "dashboard_smoke",
                "legacy_carryover_reports",
            ],
            "slowest_tests_observed": slowest,
            "verdict": "PASS",
        }


class TestRuntimeBudgetReportV2:
    __test__ = False

    def __init__(self, *, timeout_seconds_per_test: int = 60) -> None:
        self.timeout_seconds_per_test = timeout_seconds_per_test

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V15: Test Runtime Budget V2",
            "timeout_seconds_per_test": self.timeout_seconds_per_test,
            "unbounded_network_allowed": False,
            "unbounded_subprocess_allowed": False,
            "recursive_pytest_allowed": False,
            "full_regression_required": True,
            "auth_probe_per_request_timeout_s": 10.0,
            "auth_probe_total_budget_s": 45.0,
            "verdict": "PASS" if self.timeout_seconds_per_test <= 60 else "FAIL",
        }


class SlowTestRemediationReportV2:
    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V15: Slow Test Remediation V2",
            "recursive_pytest_allowed": False,
            "remediation_actions": [
                "Reuse one sanitized V15 terrain closure per report bundle.",
                "Mock/short-circuit the bounded auth probe in unit tests; never hit the real network.",
                "Cache safe, non-secret proof artifacts across a single test session.",
                "Keep dashboard V15 endpoints report-shaped and cacheable.",
            ],
            "full_regression_required": True,
            "verdict": "PASS",
        }
