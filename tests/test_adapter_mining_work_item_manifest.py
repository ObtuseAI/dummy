from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_adapter_mining_work_item_manifest_contains_github_adapter_work() -> None:
    report = assert_v20_report("adapter_mining_work_item_manifest_v1.json", "items")
    assert report["item_count"] >= 1

