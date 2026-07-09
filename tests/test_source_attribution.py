from __future__ import annotations


def test_source_attribution_feeds_bloodline_without_promoting_fixture_as_real() -> None:
    from predator_mesh.v17.attribution import OutcomeAttributionEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    report = OutcomeAttributionEngine().source_attribution_report(forecasts, outcomes)

    assert report["source_attributions"]
    assert report["fixture_sources_promoted_as_real"] is False
