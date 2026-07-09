from __future__ import annotations

from predator_mesh.v10.source_adapters import SourceAdapterPromotionEngine


def test_source_adapter_timeout_report_is_bounded() -> None:
    report = SourceAdapterPromotionEngine().timeout_report()
    assert report["verdict"] == "PASS"
    assert report["max_timeout_s"] <= 10
    assert all(entry["timeout_status"] == "BOUNDED" for entry in report["adapters"])
