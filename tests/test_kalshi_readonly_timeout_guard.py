from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest

from kalshi.client import KalshiClient
from kalshi.live_data import KALSHI_READ_ONLY_TIMEOUT_SECONDS


def test_kalshi_request_timeouts_are_at_most_10s():
    """Each Kalshi HTTP request must have a per-call timeout <= 10s."""
    import kalshi.client as kalshi_client_module

    assert kalshi_client_module._REQUEST_TIMEOUT_SECONDS <= 10.0
    assert kalshi_client_module._REQUEST_OUTER_TIMEOUT_SECONDS <= 10.0


def test_kalshi_read_only_total_timeout_is_at_most_45s():
    """KalshiRealReadOnly.get_full_snapshot must be bounded by 45s total."""
    assert KALSHI_READ_ONLY_TIMEOUT_SECONDS <= 45.0


@pytest.mark.asyncio
async def test_kalshi_client_request_times_out_within_bound(monkeypatch):
    """A stalled Kalshi server must not block a single request beyond the bound."""
    import kalshi.client as kalshi_client_module

    # Use a short timeout in the test so we prove the path without waiting 10s.
    monkeypatch.setattr(kalshi_client_module, "_REQUEST_OUTER_TIMEOUT_SECONDS", 1)
    client = KalshiClient()

    async def _never_respond(*args, **kwargs):
        await asyncio.sleep(120)
        return httpx.Response(200, json={})

    start = asyncio.get_event_loop().time()
    with patch("kalshi.client.sign_request", return_value={
        "KALSHI-ACCESS-KEY": "test",
        "KALSHI-ACCESS-SIGNATURE": "sig",
        "KALSHI-ACCESS-TIMESTAMP": "ts",
    }):
        with patch.object(client.client, "request", new=_never_respond):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_markets()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 10, f"Kalshi client blocked for {elapsed:.1f}s"
    await client.close()
