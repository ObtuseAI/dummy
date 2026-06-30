import json, asyncio
import websockets
from core.state import STATE
from core.logger import logger

class KalshiWebSocketFeed:
    def __init__(self, url: str = "wss://trading-api.kalshi.com/v1/stream", on_message=None):
        self.url = url
        self.on_message = on_message or (lambda x: None)
        self.ws = None
        self._running = False

    async def connect(self):
        self._running = True
        try:
            self.ws = await websockets.connect(self.url)
            STATE.kalshi_connected = True
            logger.info("Kalshi WebSocket connected", extra={"component": "kalshi_ws"})
            async for msg in self.ws:
                if not self._running:
                    break
                try:
                    await self.on_message(json.loads(msg))
                except Exception as e:
                    logger.error(f"Kalshi WS message error: {e}", extra={"component": "kalshi_ws"})
        except Exception as e:
            STATE.kalshi_connected = False
            logger.error(f"Kalshi WebSocket error: {e}", extra={"component": "kalshi_ws"})

    async def disconnect(self):
        self._running = False
        if self.ws:
            await self.ws.close()
            STATE.kalshi_connected = False
