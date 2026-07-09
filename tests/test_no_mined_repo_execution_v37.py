from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_mined_repo_execution_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_imported"] is False
    assert report["mined_repo_executed"] is False
