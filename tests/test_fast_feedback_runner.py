from __future__ import annotations

from predator_mesh.v10.validation import ValidationProfile, ValidationShardRunner


def test_fast_feedback_runner_returns_safe_plan_not_subprocess() -> None:
    result = ValidationShardRunner().run_fast_feedback(ValidationProfile.SMOKE_FAST)
    assert result.profile == ValidationProfile.SMOKE_FAST
    assert result.status == "PLANNED"
    assert result.unbounded_subprocess is False
    assert result.recursive_pytest is False


def test_fast_feedback_report() -> None:
    report = ValidationShardRunner().fast_feedback_report()
    assert report["verdict"] == "PASS"
    assert report["profile"] == "smoke_fast"
    assert report["status"] == "PLANNED"
