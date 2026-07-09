from __future__ import annotations

from predator_mesh.v14.runtime_acceleration import RuntimeAccelerationMegaReport


def test_runtime_acceleration_mega_report_keeps_full_regression_required() -> None:
    report = RuntimeAccelerationMegaReport().to_report()

    assert report["verdict"] == "PASS"
    assert report["recursive_pytest_allowed"] is False
    assert any("--durations=25" in command for command in report["required_full_regression_commands"])
    assert report["keeps_full_regression_required"] is True
