from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_defillama_crypto_context_adapter_is_context_only() -> None:
    report = assert_v20_report("defillama_crypto_context_adapter_report_v1.json", "blocker")
    assert "Context only" in report["blocker"]
