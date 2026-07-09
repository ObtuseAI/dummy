from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_licensed_adapter_plan_pack_never_activates_paid_sources() -> None:
    report = assert_v20_report("licensed_adapter_plan_pack_report_v1.json", "plans")
    assert report["actual_activation_count"] == 0
    assert report["plan_count"] > 0

