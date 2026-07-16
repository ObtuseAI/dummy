from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_universe_work_item_manifest_contains_public_promotion_work() -> None:
    report = assert_v20_report("source_universe_work_item_manifest_v1.json", "items")
    assert report["item_count"] >= 1
