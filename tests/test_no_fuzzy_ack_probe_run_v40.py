from __future__ import annotations

from predator_mesh.v40.reports import V40ReportFactory


def test_no_fuzzy_ack_probe_run_v40() -> None:
    reports = V40ReportFactory(env={"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY please"}, enable_real_probe=True).build()
    report = reports["no_fuzzy_ack_probe_run_report_v40.json"]
    assert report["ack_decision"] == "FAIL_FUZZY_ACK"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["v40_new_real_probe_count"] == 0
