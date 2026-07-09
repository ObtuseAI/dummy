from __future__ import annotations

import os
from pathlib import Path

from tests.v36_test_helpers import assert_current_test_report


def test_v36_real_probe_run_controller_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_order_cancel_touched"] is True
    assert report["no_live_submit_touched"] is True
    assert report["no_execution_bridge"] is True
    assert report["execution_bridge_present"] is False
