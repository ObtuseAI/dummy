from __future__ import annotations

from predator_mesh.v34.run import KalshiReadonlyRuleReconciliationV2, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_kalshi_readonly_rule_reconciliation_default_disabled() -> None:
    state = build_default_v34_state(enable_network=False)
    result = KalshiReadonlyRuleReconciliationV2().run(state["minimal_live_public_probe_execution"])

    assert result.status == "PASS_DISABLED_BY_DEFAULT"
    assert result.blocker == "PROBE_DISABLED"
    assert result.execution_bridge_present is False


def test_kalshi_readonly_rule_reconciliation_report_contract() -> None:
    report = assert_v34_report_named("kalshi_readonly_rule_reconciliation_v2_report.json", "kalshi_readonly_enabled_probe_status")

    assert report["kalshi_readonly_enabled_probe_status"] == "PASS_DISABLED_BY_DEFAULT"
