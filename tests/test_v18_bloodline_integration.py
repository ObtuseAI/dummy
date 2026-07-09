from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_v18_source_truth_registry_connects_to_bloodline_attribution() -> None:
    from predator_mesh.v18.integration import V18BloodlineIntegration

    report = V18BloodlineIntegration().to_report()

    assert_pass_report(report)
    assert report["source_truth_registry_connected"] is True
    assert report["promotion_without_outcomes"] is False
