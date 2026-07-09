from __future__ import annotations

from v18_test_helpers import DOMAINS, assert_pass_report


def test_domain_feature_schema_marks_required_features_by_domain() -> None:
    from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine

    report = DomainIntelligenceSpine().feature_schema_report()

    assert_pass_report(report)
    assert set(report["schemas"]) == DOMAINS
    for schema in report["feature_schemas"].values():
        assert schema["required_features"]
        assert schema["settlement_ambiguity_flag_required"] is True
