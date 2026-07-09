from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_source_domain_coverage_report_covers_all_v18_domains() -> None:
    from predator_mesh.v18.source_truth import SourceTruthRegistryV2

    report = SourceTruthRegistryV2().domain_coverage_report()

    assert_pass_report(report)
    assert set(report["domain_coverage"]) == DOMAINS
