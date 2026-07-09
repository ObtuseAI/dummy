import pytest

from model_router.tasks import ModelTask
from strategies.disagreement import HybridDisagreementEngine


@pytest.mark.asyncio
async def test_mock_disagreement_review():
    engine = HybridDisagreementEngine()
    result = await engine.review(ModelTask.FORECAST_OPINION, "What is the probability?")
    assert "agreement_score" in result
    assert "confidence_adjustment" in result
    assert "verdict" in result
    assert "primary" in result
    assert "secondary" in result
    assert "proof_reference" in result
