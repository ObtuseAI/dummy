from __future__ import annotations

from predator_mesh.v34.run import CryptoPriceReconciliationV2, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_crypto_price_reconciliation_default_disabled() -> None:
    state = build_default_v34_state(enable_network=False)
    result = CryptoPriceReconciliationV2().run(state["minimal_live_public_probe_execution"])

    assert result.status == "PASS_DISABLED_BY_DEFAULT"
    assert result.blocker == "PROBE_DISABLED"
    assert result.execution_bridge_present is False


def test_crypto_price_reconciliation_report_contract() -> None:
    report = assert_v34_report_named("crypto_price_reconciliation_v2_report.json", "crypto_enabled_probe_status")

    assert report["crypto_enabled_probe_status"] == "PASS_DISABLED_BY_DEFAULT"
