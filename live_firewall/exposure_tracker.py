from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from core.ontology import Position


DEFAULT_EXPOSURE_STATE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "live_exposure_state.json"


class ExposureTracker:
    """Live exposure/open-order state with optional atomic persistence."""

    def __init__(self, *, persist: bool = False, state_path: Path | None = None):
        configured_path = os.environ.get("DUMMY_EXPOSURE_STATE_PATH")
        self.state_path = state_path or (Path(configured_path) if configured_path else DEFAULT_EXPOSURE_STATE_PATH)
        self.persist_enabled = persist
        self.positions: dict[tuple[str, str], Position] = {}
        self.order_history: list[dict[str, Any]] = []
        self.open_orders: list[dict[str, Any]] = []
        self.persistence_error: str | None = None
        if self.persist_enabled:
            self._load()

    @property
    def state_healthy(self) -> bool:
        return self.persistence_error is None

    @staticmethod
    def _position_key(position: Position) -> tuple[str, str]:
        return (position.contract_ticker, position.side.lower())

    @staticmethod
    def _serialize_timestamp(value: Any) -> str:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        return str(value)

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("exposure state must be a JSON object")
            positions = data.get("positions", [])
            orders = data.get("open_orders", [])
            history = data.get("order_history", [])
            if not isinstance(positions, list) or not isinstance(orders, list) or not isinstance(history, list):
                raise ValueError("exposure state collections must be lists")
            loaded_positions: dict[tuple[str, str], Position] = {}
            for raw in positions:
                position = Position.model_validate(raw)
                loaded_positions[self._position_key(position)] = position
            loaded_history = []
            for raw in history:
                if not isinstance(raw, dict):
                    raise ValueError("order history item must be an object")
                loaded_history.append({**raw, "ts": self._parse_timestamp(raw["ts"])})
            loaded_orders: list[dict[str, Any]] = []
            for raw in orders:
                if not isinstance(raw, dict):
                    raise ValueError("open order item must be an object")
                order = dict(raw)
                order_id = str(order.get("order_id") or "").strip()
                market = str(order.get("market") or "").strip()
                size = int(order.get("size"))
                price = int(order.get("price_cents"))
                filled = int(order.get("filled_size", 0))
                remaining = int(order.get("remaining_size", size - filled))
                if (
                    not order_id
                    or not market
                    or size < 1
                    or not (1 <= price <= 99)
                    or filled < 0
                    or remaining < 0
                    or filled + remaining != size
                ):
                    raise ValueError("invalid persisted open-order reservation")
                order.update({
                    "order_id": order_id,
                    "market": market,
                    "size": size,
                    "price_cents": price,
                    "filled_size": filled,
                    "remaining_size": remaining,
                    "filled_cost_cents": int(
                        order.get("filled_cost_cents", filled * price)
                    ),
                    "state": str(order.get("state") or "open"),
                })
                loaded_orders.append(order)
            self.positions = loaded_positions
            self.open_orders = loaded_orders
            self.order_history = loaded_history
        except Exception as exc:
            # A corrupt prior state must block new live orders, not look empty.
            self.persistence_error = f"{type(exc).__name__}: {exc}"

    def _payload(self) -> dict[str, Any]:
        return {
            "positions": [position.model_dump(mode="json") for position in self.positions.values()],
            "open_orders": self.open_orders,
            "order_history": [
                {**order, "ts": self._serialize_timestamp(order["ts"])}
                for order in self.order_history[-10000:]
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _persist(self) -> bool:
        if not self.persist_enabled:
            return True
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self._payload(), indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.state_path)
            self.persistence_error = None
            return True
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False

    def verify_persistence(self) -> bool:
        """Preflight the state sink before any broker submission."""
        if self.persistence_error is not None:
            # Never overwrite a corrupt/unknown prior position book with an
            # empty optimistic one. Resolution requires an operator repair.
            return False
        return self._persist()

    def record_order(self, market_ticker: str, size: int, price_cents: int):
        self.order_history.append({
            "ts": datetime.now(timezone.utc),
            "market": market_ticker,
            "size": size,
            "price_cents": price_cents,
        })
        self._persist()

    def update_position(self, position: Position):
        self.positions[self._position_key(position)] = position
        self._persist()

    def remove_position(self, ticker: str, side: str | None = None):
        normalized_side = side.lower() if side else None
        self.positions = {
            key: position
            for key, position in self.positions.items()
            if not (
                (position.contract_ticker == ticker or position.market_ticker == ticker)
                and (normalized_side is None or position.side.lower() == normalized_side)
            )
        }
        self._persist()

    def add_open_order(
        self,
        order_id: str,
        market_ticker: str,
        size: int,
        price_cents: int,
        *,
        contract_ticker: str | None = None,
        side: str | None = None,
    ):
        if not order_id or int(size) < 1 or not (1 <= int(price_cents) <= 99):
            raise ValueError("invalid open-order reservation")
        self.open_orders = [
            order for order in self.open_orders
            if order.get("order_id") != order_id
        ]
        self.open_orders.append({
            "order_id": order_id,
            "market": market_ticker,
            "contract": contract_ticker or market_ticker,
            "side": side,
            "size": int(size),
            "remaining_size": int(size),
            "filled_size": 0,
            "filled_cost_cents": 0,
            "price_cents": int(price_cents),
            "state": "open",
        })
        self._persist()

    def reserve_order_submission(
        self,
        client_order_id: str,
        market_ticker: str,
        size: int,
        price_cents: int,
        *,
        contract_ticker: str | None = None,
        side: str | None = None,
    ) -> bool:
        """Durably reserve worst-case notional before broker transport.

        A timeout can leave broker acceptance unknown.  Persisting the
        reservation first ensures that process failure or an ambiguous
        transport result cannot make the next order assume zero exposure.
        """
        if self.persistence_error is not None:
            return False
        if (
            not client_order_id
            or int(size) < 1
            or not (1 <= int(price_cents) <= 99)
        ):
            self.persistence_error = "invalid order-submission reservation"
            return False
        if any(
            order.get("order_id") == client_order_id
            or order.get("client_order_id") == client_order_id
            for order in self.open_orders
        ):
            self.persistence_error = "duplicate client order id"
            return False
        now = datetime.now(timezone.utc)
        self.order_history.append({
            "ts": now,
            "market": market_ticker,
            "size": int(size),
            "price_cents": int(price_cents),
            "client_order_id": client_order_id,
        })
        self.open_orders.append({
            "order_id": client_order_id,
            "client_order_id": client_order_id,
            "market": market_ticker,
            "contract": contract_ticker or market_ticker,
            "side": side,
            "size": int(size),
            "remaining_size": int(size),
            "filled_size": 0,
            "filled_cost_cents": 0,
            "price_cents": int(price_cents),
            "state": "submitting",
            "reserved_at": now.isoformat(),
        })
        return self._persist()

    def confirm_open_order(
        self,
        client_order_id: str,
        broker_order_id: str,
    ) -> bool:
        """Bind a pre-transport reservation to the broker order id."""
        if self.persistence_error is not None or not broker_order_id:
            return False
        for order in self.open_orders:
            if (
                order.get("order_id") == client_order_id
                or order.get("client_order_id") == client_order_id
            ):
                order["client_order_id"] = client_order_id
                order["order_id"] = broker_order_id
                order["state"] = "open"
                order["accepted_at"] = datetime.now(timezone.utc).isoformat()
                return self._persist()
        self.persistence_error = "accepted order has no durable reservation"
        return False

    def mark_order_outcome_unknown(self, client_order_id: str) -> bool:
        """Keep an ambiguous submission reserved until reconciliation."""
        for order in self.open_orders:
            if (
                order.get("order_id") == client_order_id
                or order.get("client_order_id") == client_order_id
            ):
                order["state"] = "submit_outcome_unknown"
                return self._persist()
        self.persistence_error = "unknown submit outcome has no reservation"
        return False

    def record_cumulative_fill(
        self,
        order_id: str,
        cumulative_size: int,
        avg_price_cents: int | None,
        *,
        terminal_state: str | None = None,
    ) -> bool:
        """Apply a broker-witnessed cumulative fill without double counting.

        Positions are created only here, never from order acceptance.  An
        active partial fill reserves its witnessed position plus the entire
        unfilled remainder at the submitted LIMIT.  Filled/canceled terminal
        states release only the remainder that the broker has resolved.
        """
        if self.persistence_error is not None:
            return False
        order = next(
            (
                item for item in self.open_orders
                if item.get("order_id") == order_id
                or item.get("client_order_id") == order_id
            ),
            None,
        )
        if order is None:
            self.persistence_error = "fill references unknown open order"
            return False
        try:
            original_size = int(order["size"])
            prior_size = int(order.get("filled_size", 0))
            prior_cost = int(order.get("filled_cost_cents", 0))
            cumulative_size = int(cumulative_size)
        except (KeyError, TypeError, ValueError):
            self.persistence_error = "malformed open order during fill reconcile"
            return False
        terminal = str(terminal_state or "").lower() or None
        if terminal not in {None, "filled", "canceled", "expired"}:
            self.persistence_error = "invalid terminal fill state"
            return False
        if not (prior_size <= cumulative_size <= original_size):
            self.persistence_error = "non-monotonic or oversized cumulative fill"
            return False
        if terminal == "filled" and cumulative_size != original_size:
            self.persistence_error = "filled status lacks complete fill witness"
            return False
        if cumulative_size > 0:
            if avg_price_cents is None:
                self.persistence_error = "positive fill lacks price witness"
                return False
            try:
                avg_price_cents = int(avg_price_cents)
            except (TypeError, ValueError):
                self.persistence_error = "positive fill price malformed"
                return False
            if not (1 <= avg_price_cents <= 99):
                self.persistence_error = "positive fill price out of range"
                return False
            cumulative_cost = cumulative_size * avg_price_cents
        else:
            cumulative_cost = 0

        delta_size = cumulative_size - prior_size
        delta_cost = cumulative_cost - prior_cost
        if delta_size > 0 and (delta_cost < delta_size or delta_cost > 100 * delta_size):
            self.persistence_error = "inconsistent cumulative fill cost"
            return False
        if delta_size == 0 and delta_cost != 0:
            self.persistence_error = "fill price revision without quantity witness"
            return False

        if delta_size > 0:
            market = str(order.get("market") or "")
            contract = str(order.get("contract") or market)
            side = str(order.get("side") or "").lower()
            if not market or not contract or side not in {"yes", "no"}:
                self.persistence_error = "fill reservation identity malformed"
                return False
            key = (contract, side)
            current = self.positions.get(key)
            current_size = int(current.quantity) if current is not None else 0
            current_cost = (
                int(current.quantity) * int(current.avg_price_cents)
                if current is not None else 0
            )
            new_size = current_size + delta_size
            new_cost = current_cost + delta_cost
            self.positions[key] = Position(
                market_ticker=market,
                contract_ticker=contract,
                side=side,
                quantity=new_size,
                avg_price_cents=math.ceil(new_cost / new_size),
                unrealized_pnl_cents=(
                    int(current.unrealized_pnl_cents) if current is not None else 0
                ),
                source_ts=datetime.now(timezone.utc),
            )

        order["filled_size"] = cumulative_size
        order["filled_cost_cents"] = cumulative_cost
        order["remaining_size"] = original_size - cumulative_size
        order["state"] = terminal or (
            "partially_filled" if cumulative_size else str(order.get("state") or "open")
        )
        order["last_reconciled_at"] = datetime.now(timezone.utc).isoformat()
        if terminal is not None:
            self.open_orders = [item for item in self.open_orders if item is not order]
        return self._persist()

    def remove_open_order(self, order_id: str):
        self.open_orders = [
            order for order in self.open_orders
            if order.get("order_id") != order_id
            and order.get("client_order_id") != order_id
        ]
        self._persist()

    def total_exposure_cents(self) -> int:
        positions = sum(
            p.quantity * p.avg_price_cents for p in self.positions.values()
        )
        reservations = sum(
            int(order.get("remaining_size", order.get("size", 0)))
            * int(order.get("price_cents", 0))
            for order in self.open_orders
        )
        return positions + reservations

    def market_exposure_cents(self, ticker: str) -> int:
        positions = sum(
            position.quantity * position.avg_price_cents
            for position in self.positions.values()
            if position.market_ticker == ticker
        )
        reservations = sum(
            int(order.get("remaining_size", order.get("size", 0)))
            * int(order.get("price_cents", 0))
            for order in self.open_orders
            if order.get("market") == ticker
        )
        return positions + reservations

    def correlated_exposure_cents(self, ticker: str) -> int:
        # Event-family proxy: Kalshi event/series prefix before the first '-'.
        prefix = ticker.split("-")[0].upper()
        positions = sum(
            p.quantity * p.avg_price_cents
            for p in self.positions.values()
            if p.market_ticker.upper().split("-")[0] == prefix
        )
        reservations = sum(
            int(order.get("remaining_size", order.get("size", 0)))
            * int(order.get("price_cents", 0))
            for order in self.open_orders
            if str(order.get("market", "")).upper().split("-")[0] == prefix
        )
        return positions + reservations

    def orders_last_hour(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        return len([o for o in self.order_history if self._parse_timestamp(o["ts"]) > cutoff])

    def open_markets(self) -> int:
        markets = {position.market_ticker for position in self.positions.values()}
        markets.update(
            str(order["market"])
            for order in self.open_orders
            if order.get("market")
        )
        return len(markets)

    def open_order_count(self) -> int:
        return len(self.open_orders)


_PERSISTENT_TRACKER: ExposureTracker | None = None


def get_persistent_exposure_tracker() -> ExposureTracker:
    global _PERSISTENT_TRACKER
    configured = os.environ.get("DUMMY_EXPOSURE_STATE_PATH")
    desired = Path(configured) if configured else DEFAULT_EXPOSURE_STATE_PATH
    if _PERSISTENT_TRACKER is None or _PERSISTENT_TRACKER.state_path != desired:
        _PERSISTENT_TRACKER = ExposureTracker(persist=True, state_path=desired)
    return _PERSISTENT_TRACKER
