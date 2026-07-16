from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_crypto_source_blocker_has_deribit_and_ccxt_gates() -> None:
    report = assert_v20_report("crypto_source_blocker_report_v1.json", "blocked_sources")
    assert {"CCXT public adapter", "Deribit options/vol"} <= set(report["blocked_sources"])
