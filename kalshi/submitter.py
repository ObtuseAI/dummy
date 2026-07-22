from __future__ import annotations

from typing import Any

from core.logger import logger
from kalshi.client import KalshiClient


DIRECT_SUBMIT_RETIRED = "DIRECT_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL"


class KalshiSubmitter:
    """Retired compatibility wrapper with no broker-write capability.

    Historical adapters imported this class directly and thereby created a
    second real-order sink. It remains importable so old reports fail closed,
    but only ``LiveBrokerFirewall.submit`` may reach ``KalshiClient.create_order``.
    """

    name: str = "kalshi_submitter"

    def __init__(self, client: KalshiClient | None = None):
        self.client = client or KalshiClient()

    async def submit_limit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        logger.error(
            "Retired direct Kalshi submitter blocked",
            extra={"component": self.name},
        )
        raise PermissionError(DIRECT_SUBMIT_RETIRED)

    async def close(self):
        await self.client.close()
