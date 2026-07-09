from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_terrain_work_item_manifest_contains_terrain_work() -> None:
    report = assert_v20_report("edge_terrain_work_item_manifest_v1.json", "items")
    assert report["item_count"] >= 1

