from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_real_live_public_evidence_ledger_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["only_live_public_probe_results_accepted"] is True
    assert report["execution_bridge_present"] is False
