from __future__ import annotations


def test_outcome_backed_source_bloodline_has_low_sample_pressure() -> None:
    from predator_mesh.v17.bloodlines import OutcomeBackedSourceBloodline

    report = OutcomeBackedSourceBloodline().to_report()

    assert report["sample_quality"] == "LOW_SAMPLE"
    assert report["mock_sources_promoted_as_real"] is False
