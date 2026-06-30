import asyncio, httpx
from kalshi.error_classifier import classify, KalshiErrorCategory

class KalshiRateLimiter:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute(self, coro_factory):
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                return await coro_factory()
            except httpx.HTTPStatusError as e:
                last_exc = e
                cat = classify(e.response.status_code, e.response.text)
                if cat != KalshiErrorCategory.RATE_LIMIT and cat != KalshiErrorCategory.NETWORK:
                    raise
                await asyncio.sleep(self.base_delay * (2 ** attempt))
            except httpx.RequestError as e:
                last_exc = e
                await asyncio.sleep(self.base_delay * (2 ** attempt))
        raise last_exc
