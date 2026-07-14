"""Real Kalshi READ_ONLY orderbook snapshot adapter for V12."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.secret_guard import redact
from kalshi.live_data import KalshiRealReadOnly
from predator_mesh.v11.orderbook import OrderbookLiquidityModel


class OrderbookSnapshotMode(str, Enum):
    REAL_READ_ONLY = "REAL_READ_ONLY"
    REAL_READ_ONLY_DEGRADED = "REAL_READ_ONLY_DEGRADED"
    SAMPLE_STATIC_FALLBACK = "SAMPLE_STATIC_FALLBACK"
    MOCK_ONLY_EXPLICIT = "MOCK_ONLY_EXPLICIT"


@dataclass(frozen=True)
class OrderbookSnapshotRequest:
    contract_ticker: str
    market_ticker: str = ""
    depth: int = 10
    timeout_s: float = 10.0
    adapter_timeout_s: float = 45.0
    allow_fallback: bool = True
    requested_size: int = 5
    expected_edge_cents: float = 8.0

    def __post_init__(self) -> None:
        if self.timeout_s > 10:
            raise ValueError("Orderbook snapshot request timeout must be <= 10s")
        if self.adapter_timeout_s > 45:
            raise ValueError("Orderbook snapshot adapter timeout must be <= 45s")


@dataclass(frozen=True)
class OrderbookSnapshotError:
    message: str
    category: str

    def to_dict(self) -> dict[str, Any]:
        return {"message": self.message, "category": self.category}


@dataclass(frozen=True)
class OrderbookSnapshotProof:
    proof_ref: str
    read_only: bool
    endpoint_family: str
    request_timeout_s: float
    adapter_timeout_s: float
    real_read_only_succeeded: bool
    fallback_reason: str = ""
    order_endpoints_called: list[str] = field(default_factory=list)
    cancel_endpoints_called: list[str] = field(default_factory=list)
    write_methods_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_ref": self.proof_ref,
            "read_only": self.read_only,
            "endpoint_family": self.endpoint_family,
            "request_timeout_s": self.request_timeout_s,
            "adapter_timeout_s": self.adapter_timeout_s,
            "real_read_only_succeeded": self.real_read_only_succeeded,
            "fallback_reason": self.fallback_reason,
            "order_endpoints_called": self.order_endpoints_called,
            "cancel_endpoints_called": self.cancel_endpoints_called,
            "write_methods_used": self.write_methods_used,
        }


@dataclass(frozen=True)
class OrderbookSnapshotResult:
    mode: OrderbookSnapshotMode
    snapshot: dict[str, Any]
    proof: OrderbookSnapshotProof
    error: OrderbookSnapshotError | None = None

    @property
    def is_real(self) -> bool:
        return self.mode is OrderbookSnapshotMode.REAL_READ_ONLY

    @classmethod
    def from_snapshot(
        cls,
        *,
        mode: OrderbookSnapshotMode,
        snapshot: dict[str, Any],
        proof_ref: str,
        fallback_reason: str = "",
    ) -> "OrderbookSnapshotResult":
        return cls(
            mode=mode,
            snapshot=redact(snapshot),
            proof=OrderbookSnapshotProof(
                proof_ref=proof_ref,
                read_only=True,
                endpoint_family="GET /markets/{ticker}/orderbook",
                request_timeout_s=10.0,
                adapter_timeout_s=45.0,
                real_read_only_succeeded=mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                fallback_reason=fallback_reason,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "snapshot": redact(self.snapshot),
            "proof": self.proof.to_dict(),
            "error": self.error.to_dict() if self.error else None,
            "is_real": self.is_real,
        }


class RealKalshiOrderbookSnapshotAdapter:
    """Bounded read-only orderbook capture with explicit fallback modes."""

    def __init__(self, read_only_client: Any | None = None, *, fallback_enabled: bool = True) -> None:
        self.read_only_client = read_only_client
        self.fallback_enabled = fallback_enabled

    async def capture(self, request: OrderbookSnapshotRequest) -> OrderbookSnapshotResult:
        try:
            return await asyncio.wait_for(
                self._capture_real(request),
                timeout=min(request.adapter_timeout_s, 45.0),
            )
        except Exception as exc:
            if not request.allow_fallback or not self.fallback_enabled:
                return self._degraded(request, str(exc), mode=OrderbookSnapshotMode.REAL_READ_ONLY_DEGRADED)
            return self._fallback(request, str(exc))

    def capture_sync(self, request: OrderbookSnapshotRequest) -> OrderbookSnapshotResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.capture(request))
        raise RuntimeError(f"capture_sync cannot run inside active event loop {id(loop)}")

    async def _capture_real(self, request: OrderbookSnapshotRequest) -> OrderbookSnapshotResult:
        client = self.read_only_client
        owns_client = False
        if client is None:
            client = KalshiRealReadOnly()
            owns_client = True
        try:
            raw = await asyncio.wait_for(client.get_orderbook(request.contract_ticker), timeout=request.timeout_s)
        finally:
            if owns_client and hasattr(client, "close"):
                await client.close()

        snapshot = self._normalize(raw, request)
        degraded_reason = self._degraded_reason(snapshot)
        endpoints = self._endpoints_called(client)
        write_methods = self._write_methods(client)
        order_endpoints = self._order_endpoints(endpoints, write_methods)
        cancel_endpoints = self._cancel_endpoints(endpoints)
        mode = OrderbookSnapshotMode.REAL_READ_ONLY if not degraded_reason else OrderbookSnapshotMode.REAL_READ_ONLY_DEGRADED
        return OrderbookSnapshotResult(
            mode=mode,
            snapshot=redact(snapshot),
            proof=OrderbookSnapshotProof(
                proof_ref="real-kalshi-orderbook-snapshot-v12",
                read_only=True,
                endpoint_family="GET /markets/{ticker}/orderbook",
                request_timeout_s=request.timeout_s,
                adapter_timeout_s=request.adapter_timeout_s,
                real_read_only_succeeded=mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                fallback_reason=degraded_reason,
                order_endpoints_called=order_endpoints,
                cancel_endpoints_called=cancel_endpoints,
                write_methods_used=write_methods,
            ),
            error=OrderbookSnapshotError(degraded_reason, "DEGRADED_REAL_READ") if degraded_reason else None,
        )

    def _fallback(self, request: OrderbookSnapshotRequest, reason: str) -> OrderbookSnapshotResult:
        snapshot = OrderbookLiquidityModel.sample_orderbook()
        snapshot.update(
            {
                "market_ticker": request.market_ticker or request.contract_ticker,
                "contract_ticker": request.contract_ticker,
                "requested_size": request.requested_size,
                "expected_edge_cents": request.expected_edge_cents,
                "sample_orderbook_used": True,
            }
        )
        return OrderbookSnapshotResult(
            mode=OrderbookSnapshotMode.SAMPLE_STATIC_FALLBACK,
            snapshot=snapshot,
            proof=OrderbookSnapshotProof(
                proof_ref="sample-static-orderbook-fallback-v12",
                read_only=True,
                endpoint_family="GET /markets/{ticker}/orderbook",
                request_timeout_s=request.timeout_s,
                adapter_timeout_s=request.adapter_timeout_s,
                real_read_only_succeeded=False,
                fallback_reason=reason,
            ),
            error=OrderbookSnapshotError(reason, "REAL_READ_ONLY_UNAVAILABLE"),
        )

    def _degraded(
        self,
        request: OrderbookSnapshotRequest,
        reason: str,
        *,
        mode: OrderbookSnapshotMode,
    ) -> OrderbookSnapshotResult:
        return OrderbookSnapshotResult(
            mode=mode,
            snapshot={
                "market_ticker": request.market_ticker or request.contract_ticker,
                "contract_ticker": request.contract_ticker,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "bids": [],
                "asks": [],
                "requested_size": request.requested_size,
                "expected_edge_cents": request.expected_edge_cents,
                "sample_orderbook_used": False,
            },
            proof=OrderbookSnapshotProof(
                proof_ref="real-kalshi-orderbook-degraded-v12",
                read_only=True,
                endpoint_family="GET /markets/{ticker}/orderbook",
                request_timeout_s=request.timeout_s,
                adapter_timeout_s=request.adapter_timeout_s,
                real_read_only_succeeded=False,
                fallback_reason=reason,
            ),
            error=OrderbookSnapshotError(reason, "DEGRADED_REAL_READ"),
        )

    def _normalize(self, raw: Any, request: OrderbookSnapshotRequest) -> dict[str, Any]:
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            raw = {}
        bids = self._levels(raw.get("bids"))
        asks = self._levels(raw.get("asks"))
        return {
            "market_ticker": raw.get("market_ticker") or request.market_ticker or request.contract_ticker,
            "contract_ticker": raw.get("contract_ticker") or raw.get("ticker") or request.contract_ticker,
            "timestamp": raw.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "bids": bids,
            "asks": asks,
            "requested_size": request.requested_size,
            "expected_edge_cents": request.expected_edge_cents,
            "sample_orderbook_used": False,
        }

    def _levels(self, levels: Any) -> list[dict[str, int]]:
        out: list[dict[str, int]] = []
        if not isinstance(levels, list):
            return out
        for level in levels:
            if hasattr(level, "model_dump"):
                level = level.model_dump()
            if not isinstance(level, dict):
                continue
            try:
                price = int(level["price"])
                size = int(level.get("size", level.get("count", 0)))
            except (KeyError, TypeError, ValueError):
                continue
            if price >= 0 and size > 0:
                out.append({"price": price, "size": size})
        return out

    def _degraded_reason(self, snapshot: dict[str, Any]) -> str:
        if not snapshot["bids"] and not snapshot["asks"]:
            return "empty_orderbook"
        if not snapshot["bids"] or not snapshot["asks"]:
            return "one_sided_orderbook"
        return ""

    def _endpoints_called(self, client: Any) -> list[str]:
        if hasattr(client, "endpoints_called"):
            try:
                return sorted(client.endpoints_called())
            except TypeError:
                return sorted(client.endpoints_called)
        if hasattr(client, "called"):
            return sorted(client.called)
        return []

    def _write_methods(self, client: Any) -> list[str]:
        audit_log = list(getattr(client, "request_audit_log", []))
        return sorted({entry.get("method") for entry in audit_log if entry.get("method") and entry.get("method") != "GET"})

    def _order_endpoints(self, endpoints: list[str], write_methods: list[str]) -> list[str]:
        if not write_methods:
            return []
        return [endpoint for endpoint in endpoints if "/orders" in endpoint.lower()]

    def _cancel_endpoints(self, endpoints: list[str]) -> list[str]:
        return [endpoint for endpoint in endpoints if "cancel_order" in endpoint.lower() or "DELETE /portfolio/orders" in endpoint]


def default_snapshot_request() -> OrderbookSnapshotRequest:
    return OrderbookSnapshotRequest(contract_ticker="KXDEMO-LIQUIDITY-YES", market_ticker="KXDEMO-LIQUIDITY")
