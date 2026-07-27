from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.interprocess_lock import InterprocessFileLock
from core.ontology import Position
from autonomy.fees import kalshi_taker_fee_cents
from live_firewall.operational_journal import canonical_json, sha256_json


DEFAULT_EXPOSURE_STATE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "live_exposure_state.json"
EXPOSURE_STATE_ANCHOR_SCHEMA = "dummy.live-exposure-state.v1"
_FAIL_CLOSED_EXPOSURE_CENTS = 2**63 - 1
_OPEN_ORDER_STATES = frozenset(
    {"open", "submitting", "submit_outcome_unknown", "partially_filled"}
)


class ExposureTracker:
    """Live exposure/open-order state with optional atomic persistence."""

    def __init__(self, *, persist: bool = False, state_path: Path | None = None):
        configured_path = os.environ.get("DUMMY_EXPOSURE_STATE_PATH")
        self.state_path = state_path or (Path(configured_path) if configured_path else DEFAULT_EXPOSURE_STATE_PATH)
        self._state_lock = InterprocessFileLock(
            self.state_path.with_name(f"{self.state_path.name}.lock")
        )
        self.persist_enabled = persist
        self._has_persisted_state = False
        self._state_revision = 0
        self.positions: dict[tuple[str, str], Position] = {}
        self.order_history: list[dict[str, Any]] = []
        self.reconciliation_history: list[dict[str, Any]] = []
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
    def _validate_position(position: Position) -> None:
        if (
            not isinstance(position.market_ticker, str)
            or not position.market_ticker.strip()
            or not isinstance(position.contract_ticker, str)
            or not position.contract_ticker.strip()
            or position.side not in {"yes", "no"}
            or isinstance(position.quantity, bool)
            or not isinstance(position.quantity, int)
            or position.quantity < 1
            or isinstance(position.avg_price_cents, bool)
            or not isinstance(position.avg_price_cents, int)
            or not 1 <= position.avg_price_cents <= 100
            or isinstance(position.unrealized_pnl_cents, bool)
            or not isinstance(position.unrealized_pnl_cents, int)
        ):
            raise ValueError("invalid exposure position")

    @staticmethod
    def _strict_persisted_position(raw: Any) -> Position:
        required = {
            "market_ticker",
            "contract_ticker",
            "side",
            "quantity",
            "avg_price_cents",
            "unrealized_pnl_cents",
        }
        allowed = required | {"source_ts", "freshness_score"}
        if (
            not isinstance(raw, dict)
            or not required <= set(raw) <= allowed
            or not all(
                isinstance(raw[field], str)
                for field in ("market_ticker", "contract_ticker", "side")
            )
            or any(
                isinstance(raw[field], bool)
                or not isinstance(raw[field], int)
                for field in (
                    "quantity",
                    "avg_price_cents",
                    "unrealized_pnl_cents",
                )
            )
        ):
            raise ValueError("persisted position fields or types are invalid")
        position = Position.model_validate(raw)
        ExposureTracker._validate_position(position)
        return position

    @staticmethod
    def _strict_int(value: Any, *, minimum: int, maximum: int | None = None) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            raise ValueError("persisted exposure integer is invalid")
        return value

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
        try:
            with self._state_lock.hold():
                self._load_locked()
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"

    def _load_locked(self, *, require_existing: bool = False) -> bool:
        if not self.state_path.exists():
            if require_existing or self._has_persisted_state:
                self.persistence_error = (
                    "FileNotFoundError: persisted exposure state is missing"
                )
                return False
            self.positions = {}
            self.order_history = []
            self.reconciliation_history = []
            self.open_orders = []
            self._state_revision = 0
            return True
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("exposure state must be a JSON object")
            legacy_fields = {
                "positions",
                "open_orders",
                "order_history",
                "updated_at",
            }
            reconciliation_fields = legacy_fields | {
                "reconciliation_history"
            }
            current_fields = reconciliation_fields | {"state_revision"}
            if frozenset(data) not in {
                frozenset(legacy_fields),
                frozenset(reconciliation_fields),
                frozenset(current_fields),
            }:
                raise ValueError("exposure state fields mismatch")
            self._parse_timestamp(data["updated_at"])
            state_revision = self._strict_int(
                data.get("state_revision", 0),
                minimum=0,
            )
            positions = data.get("positions", [])
            orders = data.get("open_orders", [])
            history = data.get("order_history", [])
            reconciliations = data.get("reconciliation_history", [])
            if (
                not isinstance(positions, list)
                or not isinstance(orders, list)
                or not isinstance(history, list)
                or not isinstance(reconciliations, list)
            ):
                raise ValueError("exposure state collections must be lists")
            loaded_positions: dict[tuple[str, str], Position] = {}
            for raw in positions:
                position = self._strict_persisted_position(raw)
                key = self._position_key(position)
                if key in loaded_positions:
                    raise ValueError("duplicate persisted position identity")
                loaded_positions[key] = position
            loaded_history = []
            for raw in history:
                if not isinstance(raw, dict):
                    raise ValueError("order history item must be an object")
                required_history = {"ts", "market", "size", "price_cents"}
                allowed_history = required_history | {"client_order_id"}
                if (
                    not required_history <= set(raw) <= allowed_history
                    or not isinstance(raw["market"], str)
                    or not raw["market"].strip()
                    or (
                        "client_order_id" in raw
                        and (
                            not isinstance(raw["client_order_id"], str)
                            or not raw["client_order_id"].strip()
                        )
                    )
                ):
                    raise ValueError("order history fields are invalid")
                self._strict_int(raw["size"], minimum=1)
                self._strict_int(
                    raw["price_cents"],
                    minimum=1,
                    maximum=99,
                )
                loaded_history.append(
                    {**raw, "ts": self._parse_timestamp(raw["ts"])}
                )
            loaded_orders: list[dict[str, Any]] = []
            seen_order_identities: set[str] = set()
            for raw in orders:
                if not isinstance(raw, dict):
                    raise ValueError("open order item must be an object")
                order = dict(raw)
                required_order = {
                    "order_id",
                    "market",
                    "contract",
                    "side",
                    "size",
                    "price_cents",
                    "filled_size",
                    "remaining_size",
                    "filled_cost_cents",
                    "state",
                }
                allowed_order = required_order | {
                    "client_order_id",
                    "reserved_at",
                    "accepted_at",
                    "last_reconciled_at",
                    "fee_reserve_cents",
                }
                if not required_order <= set(order) <= allowed_order:
                    raise ValueError("persisted open-order fields mismatch")
                for field in (
                    "order_id",
                    "market",
                    "contract",
                    "side",
                    "state",
                ):
                    if (
                        not isinstance(order[field], str)
                        or not order[field].strip()
                    ):
                        raise ValueError("persisted open-order identity is invalid")
                order_id = order["order_id"]
                market = order["market"]
                contract = order["contract"]
                side = order["side"]
                state = order["state"]
                size = self._strict_int(order["size"], minimum=1)
                price = self._strict_int(
                    order["price_cents"],
                    minimum=1,
                    maximum=99,
                )
                filled = self._strict_int(order["filled_size"], minimum=0)
                remaining = self._strict_int(
                    order["remaining_size"],
                    minimum=0,
                )
                filled_cost = self._strict_int(
                    order["filled_cost_cents"],
                    minimum=0,
                )
                fee_reserve = self._strict_int(
                    order.get(
                        "fee_reserve_cents",
                        kalshi_taker_fee_cents(
                            price,
                            size,
                            market,
                        ),
                    ),
                    minimum=0,
                )
                client_order_id = order.get("client_order_id")
                if (
                    side not in {"yes", "no"}
                    or state not in _OPEN_ORDER_STATES
                    or filled + remaining != size
                    or filled_cost > filled * 100
                    or (filled == 0 and filled_cost != 0)
                    or (
                        client_order_id is not None
                        and (
                            not isinstance(client_order_id, str)
                            or not client_order_id.strip()
                        )
                    )
                ):
                    raise ValueError("invalid persisted open-order reservation")
                identities = {order_id}
                if client_order_id is not None:
                    identities.add(client_order_id)
                if seen_order_identities & identities:
                    raise ValueError("duplicate persisted open-order identity")
                seen_order_identities.update(identities)
                order.update({
                    "order_id": order_id,
                    "market": market,
                    "contract": contract,
                    "side": side,
                    "size": size,
                    "price_cents": price,
                    "filled_size": filled,
                    "remaining_size": remaining,
                    "filled_cost_cents": filled_cost,
                    "fee_reserve_cents": fee_reserve,
                    "state": state,
                })
                loaded_orders.append(order)
            loaded_reconciliations: list[dict[str, Any]] = []
            seen_reconciliation_ids: set[str] = set()
            for raw in reconciliations:
                if not isinstance(raw, dict):
                    raise ValueError(
                        "reconciliation history item must be an object"
                    )
                kind = raw.get("kind")
                reconciliation_id = raw.get("reconciliation_id")
                if (
                    not isinstance(reconciliation_id, str)
                    or len(reconciliation_id) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in reconciliation_id
                    )
                    or reconciliation_id in seen_reconciliation_ids
                ):
                    raise ValueError(
                        "reconciliation history identity is invalid"
                    )
                seen_reconciliation_ids.add(reconciliation_id)
                if kind == "terminal_order":
                    required = {
                        "kind",
                        "reconciliation_id",
                        "order_id",
                        "client_order_id",
                        "contract",
                        "side",
                        "cumulative_size",
                        "avg_price_cents",
                        "terminal_state",
                    }
                    if set(raw) != required:
                        raise ValueError(
                            "terminal reconciliation fields mismatch"
                        )
                    if (
                        raw["side"] not in {"yes", "no"}
                        or raw["terminal_state"]
                        not in {"filled", "canceled", "expired", "rejected"}
                        or not isinstance(raw["order_id"], str)
                        or not raw["order_id"]
                        or not isinstance(raw["client_order_id"], str)
                        or not raw["client_order_id"]
                        or not isinstance(raw["contract"], str)
                        or not raw["contract"]
                    ):
                        raise ValueError(
                            "terminal reconciliation identity is invalid"
                        )
                    cumulative = self._strict_int(
                        raw["cumulative_size"],
                        minimum=0,
                    )
                    average = raw["avg_price_cents"]
                    if (
                        cumulative == 0
                        and average is not None
                    ) or (
                        cumulative > 0
                        and (
                            isinstance(average, bool)
                            or not isinstance(average, int)
                            or not 1 <= average <= 100
                        )
                    ):
                        raise ValueError(
                            "terminal reconciliation price is invalid"
                        )
                elif kind == "position_close":
                    if set(raw) != {
                        "kind",
                        "reconciliation_id",
                        "contract",
                        "side",
                    } or (
                        not isinstance(raw.get("contract"), str)
                        or not raw["contract"]
                        or raw.get("side") not in {"yes", "no"}
                    ):
                        raise ValueError(
                            "position-close reconciliation is invalid"
                        )
                else:
                    raise ValueError(
                        "reconciliation history kind is invalid"
                    )
                loaded_reconciliations.append(dict(raw))
            self.positions = loaded_positions
            self.open_orders = loaded_orders
            self.order_history = loaded_history
            self.reconciliation_history = loaded_reconciliations
            self._state_revision = state_revision
            self._has_persisted_state = True
            self.persistence_error = None
            return True
        except Exception as exc:
            # A corrupt prior state must block new live orders, not look empty.
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False

    def _payload(self) -> dict[str, Any]:
        return {
            "positions": [position.model_dump(mode="json") for position in self.positions.values()],
            "open_orders": self.open_orders,
            "order_history": [
                {**order, "ts": self._serialize_timestamp(order["ts"])}
                for order in self.order_history[-10000:]
            ],
            "reconciliation_history": self.reconciliation_history[-10000:],
            "state_revision": self._state_revision,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def anchor_head(self) -> tuple[int, str]:
        """Return a monotonic revision and canonical semantic-state digest."""
        if self.persist_enabled and not self.refresh_persisted_state():
            raise RuntimeError(
                "persisted exposure state is unavailable for anchoring"
            )
        payload = {
            "schema": EXPOSURE_STATE_ANCHOR_SCHEMA,
            "state_revision": self._state_revision,
            "positions": sorted(
                (
                    position.model_dump(mode="json")
                    for position in self.positions.values()
                ),
                key=lambda item: (
                    str(item["contract_ticker"]),
                    str(item["side"]),
                ),
            ),
            "open_orders": sorted(
                (
                    json.loads(canonical_json(order))
                    for order in self.open_orders
                ),
                key=lambda item: (
                    str(item.get("client_order_id") or ""),
                    str(item.get("order_id") or ""),
                ),
            ),
            "order_history": [
                {
                    **order,
                    "ts": self._serialize_timestamp(order["ts"]),
                }
                for order in self.order_history[-10000:]
            ],
            "reconciliation_history": (
                self.reconciliation_history[-10000:]
            ),
        }
        return self._state_revision, sha256_json(payload)

    def _persist_locked(self) -> bool:
        if not self.persist_enabled:
            return True
        tmp = self.state_path.with_name(
            f".{self.state_path.name}.{os.getpid()}.{uuid4().hex}.tmp"
        )
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(
                self._payload(),
                indent=2,
                sort_keys=True,
            )
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.state_path)
            # Flush the replaced file as well. On POSIX, also fsync the parent
            # directory so the rename itself is durable. Windows does not
            # expose directory handles through os.open, while os.fsync on the
            # final file still maps to FlushFileBuffers.
            # Windows requires a writable handle for FlushFileBuffers via
            # ``os.fsync``; opening read-only raises ``EBADF`` even though no
            # additional bytes are written here.
            with self.state_path.open("r+b") as handle:
                os.fsync(handle.fileno())
            if os.name != "nt":
                directory_fd = os.open(
                    self.state_path.parent,
                    os.O_RDONLY,
                )
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            self._has_persisted_state = True
            self.persistence_error = None
            return True
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _mutate_persisted_state(
        self,
        mutation: Callable[[], bool],
    ) -> bool:
        if self.persistence_error is not None:
            return False
        if not self.persist_enabled:
            if not mutation():
                return False
            self._state_revision += 1
            return True
        try:
            with self._state_lock.hold():
                if not self._load_locked():
                    return False
                if not mutation():
                    return False
                self._state_revision += 1
                return self._persist_locked()
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False

    def refresh_persisted_state(
        self,
        *,
        require_existing: bool = False,
    ) -> bool:
        if not self.persist_enabled:
            return self.persistence_error is None
        if self.persistence_error is not None:
            return False
        try:
            with self._state_lock.hold():
                return self._load_locked(
                    require_existing=require_existing
                )
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False

    def verify_persistence(self) -> bool:
        """Reload then replace only the exact newest cross-process state."""
        if self.persistence_error is not None:
            # Never overwrite a corrupt/unknown prior position book with an
            # empty optimistic one. Resolution requires an operator repair.
            return False
        if not self.persist_enabled:
            return True
        try:
            with self._state_lock.hold():
                if not self._load_locked():
                    return False
                return self._persist_locked()
        except Exception as exc:
            self.persistence_error = f"{type(exc).__name__}: {exc}"
            return False

    def record_order(
        self,
        market_ticker: str,
        size: int,
        price_cents: int,
    ) -> None:
        if (
            not isinstance(market_ticker, str)
            or not market_ticker.strip()
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 1
            or isinstance(price_cents, bool)
            or not isinstance(price_cents, int)
            or not 1 <= price_cents <= 99
        ):
            raise ValueError("invalid order history record")

        def mutation() -> bool:
            self.order_history.append({
                "ts": datetime.now(timezone.utc),
                "market": market_ticker,
                "size": size,
                "price_cents": price_cents,
            })
            return True

        self._mutate_persisted_state(mutation)

    def update_position(self, position: Position) -> None:
        self._validate_position(position)

        def mutation() -> bool:
            self.positions[self._position_key(position)] = position
            return True

        self._mutate_persisted_state(mutation)

    def remove_position(
        self,
        ticker: str,
        side: str | None = None,
    ) -> None:
        normalized_side = side.lower() if side else None

        def mutation() -> bool:
            self.positions = {
                key: position
                for key, position in self.positions.items()
                if not (
                    (
                        position.contract_ticker == ticker
                        or position.market_ticker == ticker
                    )
                    and (
                        normalized_side is None
                        or position.side.lower() == normalized_side
                    )
                )
            }
            return True

        self._mutate_persisted_state(mutation)

    def add_open_order(
        self,
        order_id: str,
        market_ticker: str,
        size: int,
        price_cents: int,
        *,
        contract_ticker: str | None = None,
        side: str | None = None,
    ) -> None:
        contract = contract_ticker or market_ticker
        if (
            not isinstance(order_id, str)
            or not order_id.strip()
            or not isinstance(market_ticker, str)
            or not market_ticker.strip()
            or not isinstance(contract, str)
            or not contract.strip()
            or side not in {"yes", "no"}
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 1
            or isinstance(price_cents, bool)
            or not isinstance(price_cents, int)
            or not 1 <= price_cents <= 99
        ):
            raise ValueError("invalid open-order reservation")

        def mutation() -> bool:
            self.open_orders = [
                order for order in self.open_orders
                if order.get("order_id") != order_id
            ]
            self.open_orders.append({
                "order_id": order_id,
                "market": market_ticker,
                "contract": contract,
                "side": side,
                "size": int(size),
                "remaining_size": int(size),
                "filled_size": 0,
                "filled_cost_cents": 0,
                "fee_reserve_cents": kalshi_taker_fee_cents(
                    int(price_cents),
                    int(size),
                    market_ticker,
                ),
                "price_cents": int(price_cents),
                "state": "open",
            })
            return True

        self._mutate_persisted_state(mutation)

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
        if (
            not isinstance(client_order_id, str)
            or not client_order_id.strip()
            or not isinstance(market_ticker, str)
            or not market_ticker.strip()
            or not isinstance(contract_ticker, str)
            or not contract_ticker.strip()
            or side not in {"yes", "no"}
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 1
            or isinstance(price_cents, bool)
            or not isinstance(price_cents, int)
            or not 1 <= price_cents <= 99
        ):
            self.persistence_error = "invalid order-submission reservation"
            return False

        def mutation() -> bool:
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
                "fee_reserve_cents": kalshi_taker_fee_cents(
                    int(price_cents),
                    int(size),
                    market_ticker,
                ),
                "price_cents": int(price_cents),
                "state": "submitting",
                "reserved_at": now.isoformat(),
            })
            return True

        return self._mutate_persisted_state(mutation)

    def submission_record(
        self,
        client_order_id: str,
    ) -> dict[str, Any] | None:
        """Return an existing durable/ambiguous submission without mutating it."""
        normalized = str(client_order_id).strip()
        if not normalized:
            return None
        if self.persist_enabled and not self.refresh_persisted_state():
            return None
        for order in self.open_orders:
            if (
                str(order.get("order_id") or "") == normalized
                or str(order.get("client_order_id") or "") == normalized
            ):
                return dict(order)
        return None

    def confirm_open_order(
        self,
        client_order_id: str,
        broker_order_id: str,
    ) -> bool:
        """Bind a pre-transport reservation to the broker order id."""
        if (
            not isinstance(client_order_id, str)
            or not client_order_id.strip()
            or not isinstance(broker_order_id, str)
            or not broker_order_id.strip()
        ):
            return False

        def mutation() -> bool:
            if any(
                broker_order_id
                in {
                    str(order.get("order_id") or ""),
                    str(order.get("client_order_id") or ""),
                }
                and client_order_id
                not in {
                    str(order.get("order_id") or ""),
                    str(order.get("client_order_id") or ""),
                }
                for order in self.open_orders
            ):
                self.persistence_error = "duplicate broker order id"
                return False
            for order in self.open_orders:
                if (
                    order.get("order_id") == client_order_id
                    or order.get("client_order_id") == client_order_id
                ):
                    order["client_order_id"] = client_order_id
                    order["order_id"] = broker_order_id
                    order["state"] = "open"
                    order["accepted_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    return True
            self.persistence_error = (
                "accepted order has no durable reservation"
            )
            return False

        return self._mutate_persisted_state(mutation)

    def mark_order_outcome_unknown(self, client_order_id: str) -> bool:
        """Keep an ambiguous submission reserved until reconciliation."""
        def mutation() -> bool:
            for order in self.open_orders:
                if (
                    order.get("order_id") == client_order_id
                    or order.get("client_order_id") == client_order_id
                ):
                    order["state"] = "submit_outcome_unknown"
                    return True
            self.persistence_error = (
                "unknown submit outcome has no reservation"
            )
            return False

        return self._mutate_persisted_state(mutation)

    def record_cumulative_fill(
        self,
        order_id: str,
        cumulative_size: int,
        avg_price_cents: int | None,
        *,
        terminal_state: str | None = None,
        reconciliation_id: str | None = None,
    ) -> bool:
        """Apply a broker-witnessed cumulative fill without double counting.

        Positions are created only here, never from order acceptance.  An
        active partial fill reserves its witnessed position plus the entire
        unfilled remainder at the submitted LIMIT.  Filled/canceled terminal
        states release only the remainder that the broker has resolved.
        """
        return self._mutate_persisted_state(
            lambda: self._record_cumulative_fill_in_memory(
                order_id,
                cumulative_size,
                avg_price_cents,
                terminal_state=terminal_state,
                reconciliation_id=reconciliation_id,
            )
        )

    def _record_cumulative_fill_in_memory(
        self,
        order_id: str,
        cumulative_size: int,
        avg_price_cents: int | None,
        *,
        terminal_state: str | None,
        reconciliation_id: str | None,
    ) -> bool:
        normalized_reconciliation_id: str | None = None
        if reconciliation_id is not None:
            normalized_reconciliation_id = str(reconciliation_id)
            if (
                len(normalized_reconciliation_id) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in normalized_reconciliation_id
                )
            ):
                self.persistence_error = (
                    "terminal reconciliation identity is invalid"
                )
                return False
            prior_reconciliation = next(
                (
                    item
                    for item in self.reconciliation_history
                    if item.get("reconciliation_id")
                    == normalized_reconciliation_id
                ),
                None,
            )
            expected_terminal = {
                "kind": "terminal_order",
                "reconciliation_id": normalized_reconciliation_id,
                "order_id": str(order_id),
                "client_order_id": "",
                "contract": "",
                "side": "",
                "cumulative_size": int(cumulative_size),
                "avg_price_cents": avg_price_cents,
                "terminal_state": str(terminal_state or "").lower(),
            }
            if prior_reconciliation is not None:
                comparable = {
                    **expected_terminal,
                    "client_order_id": prior_reconciliation.get(
                        "client_order_id"
                    ),
                    "contract": prior_reconciliation.get("contract"),
                    "side": prior_reconciliation.get("side"),
                }
                if prior_reconciliation == comparable:
                    return True
                self.persistence_error = (
                    "terminal reconciliation identity conflict"
                )
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
        if terminal not in {
            None,
            "filled",
            "canceled",
            "expired",
            "rejected",
        }:
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
            if normalized_reconciliation_id is not None:
                self.reconciliation_history.append(
                    {
                        "kind": "terminal_order",
                        "reconciliation_id": (
                            normalized_reconciliation_id
                        ),
                        # Preserve the caller's lookup identity, not the
                        # broker-rebound id.  A restart may replay the same
                        # witness by proposal/client id after the open order
                        # was removed, so this value must remain stable across
                        # the first application and every idempotent replay.
                        "order_id": str(order_id),
                        "client_order_id": str(
                            order.get("client_order_id") or order_id
                        ),
                        "contract": str(order.get("contract") or ""),
                        "side": str(order.get("side") or ""),
                        "cumulative_size": cumulative_size,
                        "avg_price_cents": avg_price_cents,
                        "terminal_state": terminal,
                    }
                )
            self.open_orders = [item for item in self.open_orders if item is not order]
        return True

    def record_position_close(
        self,
        ticker: str,
        side: str,
        *,
        reconciliation_id: str,
    ) -> bool:
        """Persist one idempotent settlement-backed position removal."""
        normalized_id = str(reconciliation_id)
        normalized_side = str(side).lower()
        if (
            len(normalized_id) != 64
            or any(
                character not in "0123456789abcdef"
                for character in normalized_id
            )
            or not isinstance(ticker, str)
            or not ticker
            or normalized_side not in {"yes", "no"}
        ):
            self.persistence_error = (
                "position-close reconciliation identity is invalid"
            )
            return False

        expected = {
            "kind": "position_close",
            "reconciliation_id": normalized_id,
            "contract": ticker,
            "side": normalized_side,
        }

        def mutation() -> bool:
            prior = next(
                (
                    item
                    for item in self.reconciliation_history
                    if item.get("reconciliation_id") == normalized_id
                ),
                None,
            )
            if prior is not None:
                if prior == expected:
                    return True
                self.persistence_error = (
                    "position-close reconciliation identity conflict"
                )
                return False
            self.positions.pop((ticker, normalized_side), None)
            self.reconciliation_history.append(expected)
            return True

        return self._mutate_persisted_state(mutation)

    def remove_open_order(self, order_id: str) -> None:
        def mutation() -> bool:
            self.open_orders = [
                order for order in self.open_orders
                if order.get("order_id") != order_id
                and order.get("client_order_id") != order_id
            ]
            return True

        self._mutate_persisted_state(mutation)

    def _refresh_for_risk_read(self) -> bool:
        return (
            self.persistence_error is None
            and (
                not self.persist_enabled
                or self.refresh_persisted_state(require_existing=True)
            )
        )

    def _bounded_exposure(
        self,
        positions: Any,
        orders: Any,
    ) -> int:
        """Calculate notional or return a cap-breaking fail-closed sentinel."""
        try:
            total = 0
            for position in positions:
                self._validate_position(position)
                total += position.quantity * position.avg_price_cents
            for order in orders:
                remaining = order.get("remaining_size")
                price = order.get("price_cents")
                if (
                    isinstance(remaining, bool)
                    or not isinstance(remaining, int)
                    or remaining < 0
                    or isinstance(price, bool)
                    or not isinstance(price, int)
                    or not 1 <= price <= 99
                ):
                    raise ValueError("invalid open-order risk fields")
                total += remaining * price
                fee_reserve = order.get("fee_reserve_cents", 0)
                if (
                    isinstance(fee_reserve, bool)
                    or not isinstance(fee_reserve, int)
                    or fee_reserve < 0
                ):
                    raise ValueError(
                        "invalid open-order fee reservation"
                    )
                total += fee_reserve
            if total < 0:
                raise ValueError("negative aggregate exposure")
            return total
        except (AttributeError, TypeError, ValueError) as exc:
            self.persistence_error = (
                f"{type(exc).__name__}: invalid exposure risk state"
            )
            return _FAIL_CLOSED_EXPOSURE_CENTS

    def total_exposure_cents(self) -> int:
        if not self._refresh_for_risk_read():
            return _FAIL_CLOSED_EXPOSURE_CENTS
        return self._bounded_exposure(
            self.positions.values(),
            self.open_orders,
        )

    def market_exposure_cents(self, ticker: str) -> int:
        if not self._refresh_for_risk_read():
            return _FAIL_CLOSED_EXPOSURE_CENTS
        return self._bounded_exposure(
            (
                position
                for position in self.positions.values()
                if position.market_ticker == ticker
            ),
            (
                order
                for order in self.open_orders
                if order.get("market") == ticker
            ),
        )

    def correlated_exposure_cents(self, ticker: str) -> int:
        if not self._refresh_for_risk_read():
            return _FAIL_CLOSED_EXPOSURE_CENTS
        # Event-family proxy: Kalshi event/series prefix before the first '-'.
        prefix = ticker.split("-")[0].upper()
        return self._bounded_exposure(
            (
                position
                for position in self.positions.values()
                if position.market_ticker.upper().split("-")[0] == prefix
            ),
            (
                order
                for order in self.open_orders
                if str(order.get("market", "")).upper().split("-")[0]
                == prefix
            ),
        )

    def orders_last_hour(self) -> int:
        if not self._refresh_for_risk_read():
            return _FAIL_CLOSED_EXPOSURE_CENTS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        try:
            return len(
                [
                    order
                    for order in self.order_history
                    if self._parse_timestamp(order["ts"]) > cutoff
                ]
            )
        except (KeyError, TypeError, ValueError) as exc:
            self.persistence_error = (
                f"{type(exc).__name__}: invalid order history state"
            )
            return _FAIL_CLOSED_EXPOSURE_CENTS

    def open_markets(self) -> int:
        if not self._refresh_for_risk_read():
            return _FAIL_CLOSED_EXPOSURE_CENTS
        markets = {position.market_ticker for position in self.positions.values()}
        markets.update(
            str(order["market"])
            for order in self.open_orders
            if order.get("market")
        )
        return len(markets)

    def open_order_count(self) -> int:
        if not self._refresh_for_risk_read():
            return _FAIL_CLOSED_EXPOSURE_CENTS
        return len(self.open_orders)

    def client_order_id_for(self, order_id: str) -> str | None:
        """Resolve the durable proposal identity before terminal removal."""
        normalized = str(order_id).strip()
        if not normalized:
            return None
        if self.persist_enabled and not self.refresh_persisted_state():
            return None
        for order in self.open_orders:
            if (
                str(order.get("order_id") or "") == normalized
                or str(order.get("client_order_id") or "") == normalized
            ):
                candidate = str(order.get("client_order_id") or "").strip()
                return candidate or None
        return None


_PERSISTENT_TRACKER: ExposureTracker | None = None


def get_persistent_exposure_tracker() -> ExposureTracker:
    global _PERSISTENT_TRACKER
    configured = os.environ.get("DUMMY_EXPOSURE_STATE_PATH")
    desired = Path(configured) if configured else DEFAULT_EXPOSURE_STATE_PATH
    if _PERSISTENT_TRACKER is None or _PERSISTENT_TRACKER.state_path != desired:
        _PERSISTENT_TRACKER = ExposureTracker(persist=True, state_path=desired)
    return _PERSISTENT_TRACKER
