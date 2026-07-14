"""Tests for the data source scorer."""


from predator_mesh.data_inflow.models import DataSourceCandidate, SourceCategory
from predator_mesh.data_inflow.scoring import (
    DataSourceScore,
    PromotionPruningEngine,
    SourceScorer,
    SourceTier,
)


def test_source_scorer_computes_composite_score() -> None:
    scorer = SourceScorer()
    candidate = DataSourceCandidate(
        name="good_feed",
        category=SourceCategory.RSS,
        reliability=1.0,
        freshness_s=1.0,
        latency_ms=10.0,
        uniqueness=0.8,
        edge_contribution=0.8,
    )
    score = scorer.score(candidate)
    assert isinstance(score, DataSourceScore)
    assert score.source_id == candidate.source_id
    assert 0.0 <= score.composite_score <= 1.0
    assert score.reliability_score == 1.0
    assert score.tier == SourceTier.PROMOTE


def test_source_scorer_prunes_low_quality_source() -> None:
    scorer = SourceScorer(prune_threshold=0.25)
    candidate = DataSourceCandidate(
        name="bad_feed",
        category=SourceCategory.MOCK,
        reliability=0.1,
        freshness_s=1000.0,
        latency_ms=5000.0,
        uniqueness=0.1,
        edge_contribution=0.1,
    )
    score = scorer.score(candidate)
    assert score.tier == SourceTier.PRUNE
    assert score.composite_score <= scorer.prune_threshold


def test_source_scorer_latency_score_decays() -> None:
    scorer = SourceScorer(latency_target_ms=100.0)
    fast = scorer._latency_score(10.0)
    slow = scorer._latency_score(1000.0)
    assert fast > slow
    assert 0.0 <= fast <= 1.0
    assert 0.0 <= slow <= 1.0


def test_source_scorer_freshness_score_decays() -> None:
    scorer = SourceScorer(freshness_half_life_s=60.0)
    fresh = scorer._freshness_score(1.0)
    stale = scorer._freshness_score(300.0)
    assert fresh > stale
    assert 0.0 <= fresh <= 1.0
    assert 0.0 <= stale <= 1.0


def test_source_scorer_score_many() -> None:
    scorer = SourceScorer()
    candidates = [
        DataSourceCandidate(name="a", category=SourceCategory.MOCK),
        DataSourceCandidate(name="b", category=SourceCategory.RSS),
    ]
    scores = scorer.score_many(candidates)
    assert len(scores) == 2
    for score in scores:
        assert score.source_id in {c.source_id for c in candidates}


def test_promotion_pruning_engine_evaluates_candidates() -> None:
    engine = PromotionPruningEngine(scorer=SourceScorer())
    candidates = [
        DataSourceCandidate(
            name="promote_me",
            reliability=1.0,
            freshness_s=1.0,
            latency_ms=1.0,
            uniqueness=1.0,
            edge_contribution=1.0,
        ),
        DataSourceCandidate(
            name="prune_me",
            reliability=0.0,
            freshness_s=9999.0,
            latency_ms=9999.0,
            uniqueness=0.0,
            edge_contribution=0.0,
        ),
    ]
    evaluated = engine.evaluate(candidates)
    assert evaluated[0].status.value == "promoted"
    assert evaluated[1].status.value == "pruned"
    assert evaluated[0].score is not None
    assert evaluated[0].promotion_reason is not None
    assert evaluated[1].prune_reason is not None


def test_decide_returns_correct_status() -> None:
    scorer = SourceScorer(promote_threshold=0.8, prune_threshold=0.2)
    high = DataSourceCandidate(
        name="high",
        reliability=1.0,
        freshness_s=0.0,
        latency_ms=0.0,
        uniqueness=1.0,
        edge_contribution=1.0,
    )
    low = DataSourceCandidate(
        name="low",
        reliability=0.0,
        freshness_s=9999.0,
        latency_ms=9999.0,
        uniqueness=0.0,
        edge_contribution=0.0,
    )
    mid = DataSourceCandidate(
        name="mid",
        reliability=0.5,
        freshness_s=30.0,
        latency_ms=100.0,
        uniqueness=0.5,
        edge_contribution=0.5,
    )
    assert scorer.decide(high)[0].value == "promoted"
    assert scorer.decide(low)[0].value == "pruned"
    assert scorer.decide(mid)[0].value == "candidate"
