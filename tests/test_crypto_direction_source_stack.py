from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_crypto_direction_source_stack_is_readonly_and_blocks_terms_risk() -> None:
    report = assert_v20_report("crypto_direction_source_stack_report_v1.json", "sources")
    ids = {source["source_id"] for source in report["sources"]}
    assert {"CCXT_PUBLIC_PLAN", "COINGECKO_CONTEXT_ONLY", "DERIBIT_PUBLIC_OPTIONS_VOL"} <= ids

