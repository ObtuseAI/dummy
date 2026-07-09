import pytest
from core import state as state_module
from core.ontology import AccountMode
from execution.hybrid_path import HybridAutonomousExecutionPath


@pytest.mark.asyncio
async def test_hybrid_rehearsal_does_not_submit_live():
    original_mode = state_module.STATE.mode
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    try:
        path = HybridAutonomousExecutionPath()
        result = await path.rehearse_live_cap_with_model_review("MKT", "MKT-YES")
        assert result.get("live_submitted") is not True
        assert result.get("status") in ("rehearsal", "no_trade", "blocked")
    finally:
        state_module.STATE.set_mode(original_mode)
