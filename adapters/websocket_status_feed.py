"""Dashboard adapter: re-export Kalshi WebSocket feed and backend status socket."""

from kalshi.websocket import KalshiWebSocketFeed
from dashboard.backend.main import ws_status

__all__ = ["KalshiWebSocketFeed", "ws_status"]
