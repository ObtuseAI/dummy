from __future__ import annotations

from archive.report_scripts.generate_v10_reports import generate_timeout_guards_still_intact_report_v10


def test_timeout_guards_still_intact_v10() -> None:
    report = generate_timeout_guards_still_intact_report_v10()
    assert report["verdict"] == "PASS"
    assert report["max_source_adapter_timeout_s"] <= 10
    assert report["max_validation_shard_timeout_s"] <= 60
