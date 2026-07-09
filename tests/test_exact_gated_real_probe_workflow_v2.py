from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_exact_gated_real_probe_workflow_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["exact_gated_real_probe_workflow_v2_status"] == "PASS_DISABLED"
    assert report["gate_check"]["mode_required"] == "1"
    assert report["gate_check"]["ack_required"] == "READ_ONLY_PUBLIC_PROBES_ONLY"
    assert report["real_probe_run_allowed"] is False
    assert report["missing_ack_probe_run"] is False
    assert report["fuzzy_ack_probe_run"] is False
