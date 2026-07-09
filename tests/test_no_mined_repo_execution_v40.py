from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_no_mined_repo_execution_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_imported"] is False
    assert report["mined_repo_executed"] is False
    assert report["blind_mined_code_copied"] is False
