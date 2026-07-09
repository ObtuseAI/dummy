from __future__ import annotations

from predator_mesh.v13.runtime_profile import TestRuntimeProfileReport


def test_test_runtime_profile_report_lists_slowest_tests_without_running_nested_pytest() -> None:
    report = TestRuntimeProfileReport().to_report()

    assert "slowest_tests" in report
    assert report["generated_from"] in {"latest_pytest_duration_artifact", "static_profile"}
    assert report["verdict"] == "PASS"
