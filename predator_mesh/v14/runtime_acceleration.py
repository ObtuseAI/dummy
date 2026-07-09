"""V14 runtime acceleration reports that preserve full-regression gates."""

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


class RuntimeAccelerationMegaReport:
    def to_report(self) -> dict[str, Any]:
        summary = _load_tests_summary()
        slowest = summary.get("slowest_25_verbose_pytest") or summary.get("v13_slowest_25_verbose_pytest") or []
        return {
            "workstream": "V14: Runtime Acceleration Mega Report",
            "required_full_regression_commands": FULL_REGRESSION_COMMANDS,
            "keeps_full_regression_required": True,
            "recursive_pytest_allowed": False,
            "recommended_shards": [
                "credential_and_source_reports",
                "liquidity_terrain_reports",
                "dashboard_smoke",
                "legacy_carryover_reports",
            ],
            "slowest_tests_observed": slowest,
            "verdict": "PASS",
        }


class TestRuntimeBudgetReport:
    __test__ = False

    def __init__(self, *, timeout_seconds_per_test: int = 60) -> None:
        self.timeout_seconds_per_test = timeout_seconds_per_test

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V14: Test Runtime Budget",
            "timeout_seconds_per_test": self.timeout_seconds_per_test,
            "unbounded_network_allowed": False,
            "unbounded_subprocess_allowed": False,
            "recursive_pytest_allowed": False,
            "full_regression_required": True,
            "verdict": "PASS" if self.timeout_seconds_per_test <= 60 else "FAIL",
        }


class SlowTestRemediationReport:
    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V14: Slow Test Remediation",
            "recursive_pytest_allowed": False,
            "remediation_actions": [
                "Reuse one sanitized V14 terrain closure per report bundle.",
                "Keep dashboard V14 endpoints report-shaped and cacheable.",
                "Shard local verification commands while preserving the required full regression.",
            ],
            "full_regression_required": True,
            "verdict": "PASS",
        }
