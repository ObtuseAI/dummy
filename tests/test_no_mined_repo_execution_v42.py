from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_mined_repo_execution_v42() -> None:
    report = assert_current_test_report(__file__)
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_executed"] is False
