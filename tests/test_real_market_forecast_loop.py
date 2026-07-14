
import pytest
from forecasting.real_market_loop import RealMarketForecastLoop
from kalshi.live_data import KalshiCredentialsMissing


@pytest.fixture(autouse=True)
def _clear_kalshi_creds(monkeypatch):
    """The V1 loop test asserts mock fallback; ensure no real creds leak in.

    This deletes every documented Kalshi credential env var so that a ``.env``
    load order cannot change the test's semantics.
    """
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_API_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_loop_mock_fallback_without_kalshi_creds(monkeypatch):
    """Guaranteed mock-only path regardless of any .env-loaded credentials."""
    # Belt-and-suspenders: replace KalshiRealReadOnly so the loop can never
    # instantiate a real Kalshi reader in this test.
    class _AlwaysMissing:
        def __init__(self, *args, **kwargs):
            raise KalshiCredentialsMissing("mock-only test")

    monkeypatch.setattr(
        "forecasting.real_market_loop.KalshiRealReadOnly", _AlwaysMissing
    )

    loop = RealMarketForecastLoop()
    result = await loop.run(["MOCK-YES"])
    assert result["source"] == "mock"
    assert result["opinions"] == []
