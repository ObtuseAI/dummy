from __future__ import annotations

from predator_mesh.v10.source_adapters import (
    SourceAdapterMode,
    SourceAdapterPromotionDecision,
    SourceAdapterPromotionEngine,
)


def test_source_adapter_promotion_engine_creates_safe_candidates() -> None:
    engine = SourceAdapterPromotionEngine()
    candidates = engine.discover_candidates()
    modes = {candidate.mode for candidate in candidates}

    assert candidates
    assert SourceAdapterMode.LIVE_PUBLIC_BOUNDED in modes
    assert SourceAdapterMode.SAMPLE_STATIC in modes
    assert SourceAdapterMode.MOCK_ONLY_EXPLICIT in modes
    assert all(candidate.legality_status == "PUBLIC_ALLOWED" for candidate in candidates)
    assert all(candidate.timeout_s <= 10 for candidate in candidates)


def test_source_adapter_promotion_decisions_are_explicit() -> None:
    decisions = SourceAdapterPromotionEngine().promotion_decisions()
    assert decisions
    assert all(isinstance(d, SourceAdapterPromotionDecision) for d in decisions)
    assert all(d.decision in {"PROMOTE", "KEEP_SAMPLE", "KEEP_MOCK_EXPLICIT"} for d in decisions)
