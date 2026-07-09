from __future__ import annotations

from predator_mesh.v34.run import ProbeReconciliationSprintQueueV11, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_probe_reconciliation_sprint_queue_default_status() -> None:
    sprint = ProbeReconciliationSprintQueueV11().build(build_default_v34_state(enable_network=False))

    assert sprint.sprint_queue_v11_status == "PASS"
    assert sprint.execution_bridge_present is False
    assert sprint.risk_guard == "no live trading, no browser, no mined code"


def test_probe_reconciliation_sprint_queue_report_contract() -> None:
    report = assert_v34_report_named("probe_reconciliation_sprint_queue_v11_report.json", "probe_reconciliation_sprint_queue_v11")

    assert "reconciliation pass" in str(report["probe_reconciliation_sprint_queue_v11"])
