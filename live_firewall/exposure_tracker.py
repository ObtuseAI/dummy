from datetime import datetime, timezone, timedelta
from collections import defaultdict
from core.ontology import Position


class ExposureTracker:
    def __init__(self):
        self.positions: dict[str, Position] = {}
        self.order_history: list[dict] = []
        self.open_orders: list[dict] = []

    def record_order(self, market_ticker: str, size: int, price_cents: int):
        self.order_history.append({"ts": datetime.now(timezone.utc), "market": market_ticker, "size": size, "price_cents": price_cents})

    def update_position(self, position: Position):
        self.positions[position.market_ticker] = position

    def remove_position(self, market_ticker: str):
        self.positions.pop(market_ticker, None)

    def add_open_order(self, order_id: str, market_ticker: str, size: int, price_cents: int):
        self.open_orders.append({"order_id": order_id, "market": market_ticker, "size": size, "price_cents": price_cents})

    def remove_open_order(self, order_id: str):
        self.open_orders = [o for o in self.open_orders if o["order_id"] != order_id]

    def total_exposure_cents(self) -> int:
        return sum(p.quantity * p.avg_price_cents for p in self.positions.values())

    def market_exposure_cents(self, ticker: str) -> int:
        p = self.positions.get(ticker)
        return p.quantity * p.avg_price_cents if p else 0

    def correlated_exposure_cents(self, ticker: str) -> int:
        # Simple: sum exposure in same event family (prefix before first '-')
        prefix = ticker.split("-")[0]
        return sum(
            p.quantity * p.avg_price_cents
            for p in self.positions.values()
            if p.market_ticker.startswith(prefix)
        )

    def orders_last_hour(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        return len([o for o in self.order_history if o["ts"] > cutoff])

    def open_markets(self) -> int:
        return len(self.positions)

    def open_order_count(self) -> int:
        return len(self.open_orders)
