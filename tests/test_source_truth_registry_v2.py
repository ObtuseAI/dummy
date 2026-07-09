from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_source_truth_registry_v2_requires_legality_freshness_and_fallbacks() -> None:
    from predator_mesh.v18.source_truth import SourceTruthRegistryV2

    report = SourceTruthRegistryV2().to_report()

    assert_pass_report(report)
    assert set(report["domain_coverage"]) == DOMAINS
    assert report["all_sources_have_legality"] is True
    assert report["all_sources_have_fallback_mode"] is True
    assert report["sample_static_sources_labeled_live"] is False
