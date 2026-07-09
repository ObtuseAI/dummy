from __future__ import annotations

from predator_mesh.v10.validation import ValidationShardRunner


def test_full_regression_guard_requires_full_pytest_and_dashboard() -> None:
    report = ValidationShardRunner().full_regression_guard_report()
    assert report["verdict"] == "PASS"
    assert "python -m pytest tests/ -q --tb=short --timeout=60" in report["required_commands"]
    assert "npm run build" in " ".join(report["required_commands"])
    assert report["fast_feedback_is_not_proof"] is True
