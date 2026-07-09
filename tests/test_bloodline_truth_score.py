from __future__ import annotations


def test_bloodline_truth_score_is_bounded_and_low_sample() -> None:
    from predator_mesh.v17.bloodlines import BloodlineTruthScore

    score = BloodlineTruthScore(score=0.5, sample_count=2)

    assert 0 <= score.score <= 1
    assert score.sample_quality == "LOW_SAMPLE"
