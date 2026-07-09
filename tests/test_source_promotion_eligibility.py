from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_source_promotion_eligibility_blocks_unproven_or_fixture_sources() -> None:
    from predator_mesh.v18.source_truth import SourceTruthRegistryV2

    report = SourceTruthRegistryV2().promotion_eligibility_report()

    assert_pass_report(report)
    assert report["no_source_promoted_without_proof"] is True
    assert all(item["eligible"] is False for item in report["promotion_eligibility"])
