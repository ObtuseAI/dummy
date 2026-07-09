from __future__ import annotations

from predator_mesh.v13.runtime_profile import SlowTestAccelerationReport


def test_slow_test_acceleration_report_keeps_required_tests_and_avoids_recursive_pytest() -> None:
    report = SlowTestAccelerationReport().to_report()

    assert report["verdict"] == "PASS"
    assert report["recursive_pytest_inside_unit_tests"] is False
    assert report["required_tests_preserved"] is True
