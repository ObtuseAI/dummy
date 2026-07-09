"""Config-bound real orderbook snapshot fetch for V16."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from core.secret_guard import redact
from predator_mesh.v12.orderbook_snapshot import (
    OrderbookSnapshotError,
    OrderbookSnapshotMode,
    OrderbookSnapshotProof,
    OrderbookSnapshotResult,
)
from predator_mesh.v16.market_discovery import RealMarketDiscoveryResultV2
from predator_mesh.v16.runtime_config import KalshiReadOnlyClientFactory, KalshiReadOnlyRuntimeConfig


@dataclass(frozen=True)
class NonemptyOrderbookProof:
    bid_depth: int
    ask_depth: int
    bid_level_count: int
    ask_level_count: int

    @property
    def nonempty(self) -> bool:
        return self.bid_depth > 0 or self.ask_depth > 0

    @property
    def two_sided(self) -> bool:
        return self.bid_depth > 0 and self.ask_depth > 0

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Nonempty Orderbook Proof",
            "nonempty": self.nonempty,
            "two_sided": self.two_sided,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "bid_level_count": self.bid_level_count,
            "ask_level_count": self.ask_level_count,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.nonempty else "PARTIAL",
        }


@dataclass(frozen=True)
class ReadOnlyOrderbookEndpointProofV2:
    endpoints_called: list[str] = field(default_factory=list)
    order_endpoints_called: list[str] = field(default_factory=list)
    cancel_endpoints_called: list[str] = field(default_factory=list)
    write_methods_used: list[str] = field(default_factory=list)

    @property
    def read_only_endpoints_only(self) -> bool:
        return (
            all(endpoint.startswith("GET ") for endpoint in self.endpoints_called)
            and not self.order_endpoints_called
            and not self.cancel_endpoints_called
            and not self.write_methods_used
        )

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: ReadOnly Orderbook Endpoint Proof V2",
            "endpoints_called": self.endpoints_called,
            "read_only_endpoints_only": self.read_only_endpoints_only,
            "order_endpoints_called": self.order_endpoints_called,
            "cancel_endpoints_called": self.cancel_endpoints_called,
            "write_methods_used": self.write_methods_used,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.read_only_endpoints_only else "FAIL",
        }


class RealOrderbookSnapshotSanitizer:
    def sanitize(self, raw: Any, *, market_ticker: str, contract_ticker: str) -> dict[str, Any]:
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        raw = raw if isinstance(raw, dict) else {}
        return redact(
            {
                "market_ticker": raw.get("market_ticker") or market_ticker or contract_ticker,
                "contract_ticker": raw.get("contract_ticker") or raw.get("ticker") or contract_ticker,
                "timestamp": raw.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                "bids": self._levels(raw.get("bids")),
                "asks": self._levels(raw.get("asks")),
                "requested_size": int(raw.get("requested_size") or 5),
                "expected_edge_cents": float(raw.get("expected_edge_cents") or 8.0),
                "sample_orderbook_used": False,
            }
        )

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


@dataclass(frozen=True)
class RealOrderbookSnapshotResultV2:
    mode: OrderbookSnapshotMode
    snapshot: dict[str, Any]
    proof: OrderbookSnapshotProof
    nonempty_proof: NonemptyOrderbookProof
    endpoint_proof: ReadOnlyOrderbookEndpointProofV2
    error: OrderbookSnapshotError | None = None
    discovery_mode: str = ""

    @property
    def is_real(self) -> bool:
        return self.mode is OrderbookSnapshotMode.REAL_READ_ONLY

    def to_orderbook_snapshot_result(self) -> OrderbookSnapshotResult:
        return OrderbookSnapshotResult(mode=self.mode, snapshot=self.snapshot, proof=self.proof, error=self.error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "snapshot": redact(self.snapshot),
            "proof": self.proof.to_dict(),
            "nonempty_proof": self.nonempty_proof.to_report(),
            "endpoint_proof": self.endpoint_proof.to_report(),
            "error": self.error.to_dict() if self.error else None,
            "is_real": self.is_real,
        }

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Config-Bound Real Orderbook Snapshot",
            "mode": self.mode.value,
            "snapshot": redact(self.snapshot),
            "nonempty_orderbook": self.nonempty_proof.nonempty,
            "read_only_endpoints_only": self.endpoint_proof.read_only_endpoints_only,
            "discovery_mode": self.discovery_mode,
            "proof": self.proof.to_dict(),
            "fallback_reason": self.proof.fallback_reason,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.mode is OrderbookSnapshotMode.REAL_READ_ONLY else "PARTIAL",
        }

    def manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Real Orderbook Snapshot Manifest V4",
            "version": "v4",
            "snapshot_count": 1,
            "snapshots": [
                {
                    "snapshot_mode": self.mode.value,
                    "real_read_only": self.mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                    "market_ticker": self.snapshot.get("market_ticker"),
                    "contract_ticker": self.snapshot.get("contract_ticker"),
                    "proof_ref": self.proof.proof_ref,
                }
            ],
            "sanitized": True,
            "account_sensitive_fields_excluded": True,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.mode is OrderbookSnapshotMode.REAL_READ_ONLY else "PARTIAL",
        }


class ConfigBoundRealOrderbookSnapshotAdapter:
    def __init__(
        self,
        *,
        runtime_config: KalshiReadOnlyRuntimeConfig,
        discovery_result: RealMarketDiscoveryResultV2,
        read_only_client_factory: Callable[..., Any] | None = None,
        request_timeout_s: float = 10.0,
        total_timeout_s: float = 45.0,
    ) -> None:
        self.runtime_config = runtime_config
        self.discovery_result = discovery_result
        self.read_only_client_factory = read_only_client_factory
        self.request_timeout_s = min(request_timeout_s, 10.0)
        self.total_timeout_s = min(total_timeout_s, 45.0)
        self.sanitizer = RealOrderbookSnapshotSanitizer()

    async def capture(self) -> RealOrderbookSnapshotResultV2:
        try:
            return await asyncio.wait_for(self._capture_inner(), timeout=self.total_timeout_s)
        except asyncio.TimeoutError:
            return self._degraded("ENDPOINT_TIMEOUT")
        except Exception as exc:
            return self._degraded(self._classify_exception(exc))

    def capture_sync(self) -> RealOrderbookSnapshotResultV2:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.capture())
        raise RuntimeError(f"capture_sync cannot run inside active event loop {id(loop)}")

    async def _capture_inner(self) -> RealOrderbookSnapshotResultV2:
        candidate = self.discovery_result.selected_candidate
        if not self.runtime_config.ready:
            return self._degraded(self.runtime_config.invalid_reason or "CONFIG_NOT_READY")
        if candidate is None:
            return self._degraded(self.discovery_result.degradation_reason or "NO_ELIGIBLE_MARKET")
        with self.runtime_config.credential_environment_overlay():
            client = KalshiReadOnlyClientFactory(
                self.runtime_config,
                client_factory=self.read_only_client_factory,
            ).build()
            try:
                raw = await asyncio.wait_for(client.get_orderbook(candidate.contract_ticker), timeout=self.request_timeout_s)
                snapshot = self.sanitizer.sanitize(
                    raw,
                    market_ticker=candidate.market_ticker,
                    contract_ticker=candidate.contract_ticker,
                )
                endpoints = self._endpoints_called(client)
                endpoint_proof = self._endpoint_proof(client, endpoints)
                nonempty = self._nonempty(snapshot)
                reason = self._degraded_reason(snapshot, nonempty, endpoint_proof)
                mode = OrderbookSnapshotMode.REAL_READ_ONLY if not reason else OrderbookSnapshotMode.REAL_READ_ONLY_DEGRADED
                proof = OrderbookSnapshotProof(
                    proof_ref="config-bound-real-orderbook-snapshot-v16",
                    read_only=True,
                    endpoint_family="GET /markets/{ticker}/orderbook",
                    request_timeout_s=self.request_timeout_s,
                    adapter_timeout_s=self.total_timeout_s,
                    real_read_only_succeeded=mode is OrderbookSnapshotMode.REAL_READ_ONLY,
                    fallback_reason=reason,
                    order_endpoints_called=endpoint_proof.order_endpoints_called,
                    cancel_endpoints_called=endpoint_proof.cancel_endpoints_called,
                    write_methods_used=endpoint_proof.write_methods_used,
                )
                return RealOrderbookSnapshotResultV2(
                    mode=mode,
                    snapshot=snapshot,
                    proof=proof,
                    nonempty_proof=nonempty,
                    endpoint_proof=endpoint_proof,
                    error=OrderbookSnapshotError(reason, "DEGRADED_REAL_READ") if reason else None,
                    discovery_mode=self.discovery_result.mode,
                )
            finally:
                if self.read_only_client_factory is None and hasattr(client, "close"):
                    await client.close()

    def _degraded(self, reason: str) -> RealOrderbookSnapshotResultV2:
        snapshot = {
            "market_ticker": "",
            "contract_ticker": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bids": [],
            "asks": [],
            "requested_size": 5,
            "expected_edge_cents": 8.0,
            "sample_orderbook_used": reason in {"CONFIG_NOT_READY", "CREDENTIALS_MISSING", "NO_ELIGIBLE_MARKET"},
        }
        mode = OrderbookSnapshotMode.SAMPLE_STATIC_FALLBACK if snapshot["sample_orderbook_used"] else OrderbookSnapshotMode.REAL_READ_ONLY_DEGRADED
        nonempty = self._nonempty(snapshot)
        endpoint_proof = ReadOnlyOrderbookEndpointProofV2()
        proof = OrderbookSnapshotProof(
            proof_ref="config-bound-orderbook-degraded-v16",
            read_only=True,
            endpoint_family="GET /markets/{ticker}/orderbook",
            request_timeout_s=self.request_timeout_s,
            adapter_timeout_s=self.total_timeout_s,
            real_read_only_succeeded=False,
            fallback_reason=reason,
        )
        return RealOrderbookSnapshotResultV2(
            mode=mode,
            snapshot=snapshot,
            proof=proof,
            nonempty_proof=nonempty,
            endpoint_proof=endpoint_proof,
            error=OrderbookSnapshotError(reason, "REAL_READ_ONLY_UNAVAILABLE"),
            discovery_mode=self.discovery_result.mode,
        )

    def _nonempty(self, snapshot: dict[str, Any]) -> NonemptyOrderbookProof:
        bids = snapshot.get("bids") if isinstance(snapshot.get("bids"), list) else []
        asks = snapshot.get("asks") if isinstance(snapshot.get("asks"), list) else []
        bid_depth = sum(int(level.get("size", 0)) for level in bids if isinstance(level, dict))
        ask_depth = sum(int(level.get("size", 0)) for level in asks if isinstance(level, dict))
        return NonemptyOrderbookProof(
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            bid_level_count=len(bids),
            ask_level_count=len(asks),
        )

    def _degraded_reason(
        self,
        snapshot: dict[str, Any],
        nonempty: NonemptyOrderbookProof,
        endpoint_proof: ReadOnlyOrderbookEndpointProofV2,
    ) -> str:
        if not endpoint_proof.read_only_endpoints_only:
            return "WRITE_OR_ORDER_ENDPOINT_DETECTED"
        if not nonempty.nonempty:
            return "empty_orderbook"
        if not nonempty.two_sided:
            return "one_sided_orderbook"
        bids = snapshot.get("bids") or []
        asks = snapshot.get("asks") or []
        best_bid = max(level["price"] for level in bids)
        best_ask = min(level["price"] for level in asks)
        if best_bid >= best_ask:
            return "crossed_orderbook"
        return ""

    def _endpoints_called(self, client: Any) -> list[str]:
        if hasattr(client, "endpoints_called"):
            try:
                return sorted(client.endpoints_called())
            except TypeError:
                return sorted(client.endpoints_called)
        return sorted(getattr(client, "called", []))

    def _endpoint_proof(self, client: Any, endpoints: list[str]) -> ReadOnlyOrderbookEndpointProofV2:
        audit_log = list(getattr(client, "request_audit_log", []))
        write_methods = sorted({entry.get("method") for entry in audit_log if entry.get("method") and entry.get("method") != "GET"})
        order_endpoints = [endpoint for endpoint in endpoints if "/orders" in endpoint.lower() and not endpoint.startswith("GET ")]
        cancel_endpoints = [endpoint for endpoint in endpoints if "cancel" in endpoint.lower() or endpoint.startswith("DELETE ")]
        return ReadOnlyOrderbookEndpointProofV2(
            endpoints_called=endpoints,
            order_endpoints_called=order_endpoints,
            cancel_endpoints_called=cancel_endpoints,
            write_methods_used=write_methods,
        )

    def _classify_exception(self, exc: Exception) -> str:
        text = str(exc).lower()
        if "timeout" in text:
            return "ENDPOINT_TIMEOUT"
        if any(marker in text for marker in ("401", "403", "unauthorized", "forbidden", "credential", "private key", "pem")):
            return "CREDENTIALS_INVALID"
        return "ENDPOINT_UNAVAILABLE"
