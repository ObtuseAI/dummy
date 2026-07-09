from __future__ import annotations


def test_outcome_attribution_engine_marks_low_evidence_without_fake_causality() -> None:
    from predator_mesh.v17.attribution import OutcomeAttributionEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    report = OutcomeAttributionEngine().to_report(forecasts, outcomes)

    assert report["evidence_backed"] is True
    assert report["causality_claim"] == "LOW_CONFIDENCE_ATTRIBUTION"
