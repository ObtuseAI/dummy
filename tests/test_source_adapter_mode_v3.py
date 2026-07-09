from __future__ import annotations

from predator_mesh.v13.source_adapter_closure import SourceAdapterClosurePassV2
from tests.v13_test_helpers import real_snapshot_result


def test_source_adapter_mode_v3_counts_real_read_only_bounded_and_existing_partials() -> None:
    report = SourceAdapterClosurePassV2(real_snapshot_result()).mode_report_v3()

    assert report["mode_counts"]["REAL_READ_ONLY_BOUNDED"] == 1
    assert report["mode_counts"]["SAMPLE_STATIC"] >= 1
    assert report["mode_counts"]["MOCK_ONLY_EXPLICIT"] >= 1
    assert report["verdict"] == "PARTIAL"
