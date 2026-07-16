from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_sec_edgar_adapter_has_rate_policy_blocker_for_real_fetch() -> None:
    report = assert_v20_report("sec_edgar_adapter_report_v1.json", "blocker")
    assert "rate" in report["blocker"].lower() or "user-agent" in report["blocker"].lower()
