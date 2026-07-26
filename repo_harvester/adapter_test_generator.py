"""Compatibility helpers for the canonical pending-adapter contract tests.

The old generator embedded hundreds of lines of duplicated tests for dozens of
generated no-op modules.  Pending candidates now share one inert adapter, so
the checked-in canonical test is the only source of test truth.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DUMMY_ARTIFACTS = ROOT / "artifacts" / "dummy"
TEST_PATH = ROOT / "tests" / "test_adapter_promotion.py"


def generate_tests(records: list[dict[str, Any]] | None = None) -> str:
    """Return the canonical metadata-only adapter contract tests."""

    del records
    return TEST_PATH.read_text(encoding="utf-8")


def write_tests(path: Path | None = None) -> Path:
    """Copy the canonical tests only when an explicit alternate path is given."""

    target = path or TEST_PATH
    if target.resolve() == TEST_PATH.resolve():
        return target
    target.write_text(generate_tests(), encoding="utf-8")
    return target


def write_adapter_test_report(
    passed: int,
    failed: int,
    errors: int,
    path: Path | None = None,
) -> Path:
    report_path = path or DUMMY_ARTIFACTS / "adapter_test_report_v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_file": str(TEST_PATH),
        "required_test_types": [
            "metadata_only",
            "shared_abstention",
            "no_secret_leak",
            "no_direct_order_path",
            "firewall_rejected",
        ],
        "result": {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "overall": (
                "STRUCTURAL_PASS_CAPABILITY_UNVERIFIED"
                if failed == 0 and errors == 0
                else "STRUCTURAL_FAIL"
            ),
        },
        "adapter_specific_upstream_tests_passed": False,
        "production_capability": False,
        "prediction_authority": False,
        "execution_authority": False,
        "incorporation_authority": False,
        "notes": (
            "Pending repositories are metadata only. The shared adapter proves "
            "fail-closed abstention, not upstream capability."
        ),
    }
    report_path.write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return report_path


if __name__ == "__main__":
    print(write_tests())
