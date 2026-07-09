"""Bounded real Kalshi market discovery for V13 orderbook terrain."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from core.secret_guard import redact
from kalshi.live_data import KalshiCredentialsMissing, KalshiRealReadOnly
from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge


class MarketDiscoveryMode(str, Enum):
    REAL_READ_ONLY_DISCOVERY = "REAL_READ_ONLY_DISCOVERY"
    REAL_READ_ONLY_DEGRADED = "REAL_READ_ONLY_DEGRADED"
    SAMPLE_STATIC_FALLBACK = "SAMPLE_STATIC_FALLBACK"
    MOCK_ONLY_EXPLICIT = "MOCK_ONLY_EXPLICIT"


@dataclass(frozen=True)
class MarketEligibilityScore:
    active_open: bool
    not_expired: bool
    orderbook_endpoint_available: bool
    orderbook_nonempty: bool
    bounded_request: bool
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_open": self.active_open,
            "not_expired": self.not_expired,
            "orderbook_endpoint_available": self.orderbook_endpoint_available,
            "orderbook_nonempty": self.orderbook_nonempty,
            "bounded_request": self.bounded_request,
            "score": self.score,
        }


@dataclass(frozen=True)
class EligibleMarketCandidate:
    market_ticker: str
    contract_ticker: str
    status: str
    orderbook_nonempty: bool
    score: MarketEligibilityScore
    source_mode: MarketDiscoveryMode
    proof_ref: str = "eligible-market-candidate-v13"

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_ticker": self.market_ticker,
            "contract_ticker": self.contract_ticker,
            "status": self.status,
            "orderbook_nonempty": self.orderbook_nonempty,
            "score": self.score.to_dict(),
            "source_mode": self.source_mode.value,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class MarketDiscoveryProof:
    mode: MarketDiscoveryMode
    eligible_candidates: list[EligibleMarketCandidate]
    degradation_reason: str = ""
    endpoints_called: list[str] = field(default_factory=list)
    max_request_timeout_s: float = 10.0
    total_timeout_s: float = 45.0
    max_candidates: int = 5
    real_read_only_used: bool = False

    @property
    def selected_candidate(self) -> EligibleMarketCandidate | None:
        return self.eligible_candidates[0] if self.eligible_candidates else None

    def to_dict(self) -> dict[str, Any]:
        return redact(
            {
                "mode": self.mode.value,
                "eligible_candidates": [candidate.to_dict() for candidate in self.eligible_candidates],
                "degradation_reason": self.degradation_reason,
                "endpoints_called": self.endpoints_called,
                "max_request_timeout_s": self.max_request_timeout_s,
                "total_timeout_s": self.total_timeout_s,
                "max_candidates": self.max_candidates,
                "real_read_only_used": self.real_read_only_used,
                "verdict": "PASS" if self.real_read_only_used else "PARTIAL",
            }
        )

    def candidate_manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V13: Eligible Market Candidate Manifest",
            "candidate_count": len(self.eligible_candidates),
            "max_candidates": self.max_candidates,
            "candidates": [candidate.to_dict() for candidate in self.eligible_candidates],
            "verdict": "PASS" if self.eligible_candidates else "PARTIAL",
        }

    def to_mode_report(self) -> dict[str, Any]:
        counts = {mode.value: 0 for mode in MarketDiscoveryMode}
        counts[self.mode.value] += 1
        return {
            "workstream": "V13: Market Discovery Modes",
            "mode": self.mode.value,
            "mode_counts": counts,
            "degradation_reason": self.degradation_reason,
            "real_read_only_used": self.real_read_only_used,
            "verdict": "PASS" if self.real_read_only_used else "PARTIAL",
        }


class RealKalshiMarketDiscovery:
    def __init__(
        self,
        *,
        credential_bridge: KalshiReadOnlyCredentialBridge | None = None,
        read_only_client_factory: Callable[[], Any] | None = None,
        max_candidates: int = 5,
        request_timeout_s: float = 10.0,
        total_timeout_s: float = 45.0,
    ) -> None:
        self.credential_bridge = credential_bridge or KalshiReadOnlyCredentialBridge()
        self.read_only_client_factory = read_only_client_factory
        self.max_candidates = min(max_candidates, 10)
        self.request_timeout_s = min(request_timeout_s, 10.0)
        self.total_timeout_s = min(total_timeout_s, 45.0)

    async def discover(self) -> MarketDiscoveryProof:
        try:
            return await asyncio.wait_for(self._discover_inner(), timeout=self.total_timeout_s)
        except asyncio.TimeoutError:
            return self._degraded("DISCOVERY_TIMEOUT")
        except KalshiCredentialsMissing:
            return self._fallback("CREDENTIALS_MISSING")
        except Exception as exc:
            return self._degraded(self._classify_exception(exc))

    def discover_sync(self) -> MarketDiscoveryProof:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.discover())
        raise RuntimeError(f"discover_sync cannot run inside active event loop {id(loop)}")

    async def _client(self):
        if self.read_only_client_factory is not None:
            return self.read_only_client_factory(), False
        return KalshiRealReadOnly(), True

    async def _discover_inner(self) -> MarketDiscoveryProof:
        readiness = self.credential_bridge.resolve()
        if not readiness.ready:
            return self._fallback("CREDENTIALS_MISSING")
        if self.read_only_client_factory is None:
            with self.credential_bridge.credential_environment_overlay():
                return await self._discover_with_client()
        return await self._discover_with_client()

    async def _discover_with_client(self) -> MarketDiscoveryProof:
        client, owns_client = await self._client()
        try:
            try:
                markets = await asyncio.wait_for(client.get_markets(), timeout=self.request_timeout_s)
            except Exception as exc:
                return MarketDiscoveryProof(
                    mode=MarketDiscoveryMode.REAL_READ_ONLY_DEGRADED,
                    eligible_candidates=[],
                    degradation_reason=self._classify_exception(exc),
                    endpoints_called=self._endpoints_called(client),
                    max_request_timeout_s=self.request_timeout_s,
                    total_timeout_s=self.total_timeout_s,
                    max_candidates=self.max_candidates,
                    real_read_only_used=False,
                )
            if isinstance(markets, dict):
                markets = markets.get("markets", [])
            candidates: list[EligibleMarketCandidate] = []
            inspected = 0
            for market in markets if isinstance(markets, list) else []:
                if inspected >= self.max_candidates:
                    break
                if not isinstance(market, dict):
                    continue
                inspected += 1
                candidate = await self._candidate(client, market)
                if candidate and candidate.score.score >= 1.0:
                    candidates.append(candidate)
            endpoints = self._endpoints_called(client)
            if candidates:
                return MarketDiscoveryProof(
                    mode=MarketDiscoveryMode.REAL_READ_ONLY_DISCOVERY,
                    eligible_candidates=candidates,
                    endpoints_called=endpoints,
                    max_request_timeout_s=self.request_timeout_s,
                    total_timeout_s=self.total_timeout_s,
                    max_candidates=self.max_candidates,
                    real_read_only_used=True,
                )
            return MarketDiscoveryProof(
                mode=MarketDiscoveryMode.REAL_READ_ONLY_DEGRADED,
                eligible_candidates=[],
                degradation_reason="NO_ELIGIBLE_MARKET_FOUND",
                endpoints_called=endpoints,
                max_request_timeout_s=self.request_timeout_s,
                total_timeout_s=self.total_timeout_s,
                max_candidates=self.max_candidates,
                real_read_only_used=False,
            )
        finally:
            if owns_client and hasattr(client, "close"):
                await client.close()

    async def _candidate(self, client: Any, market: dict[str, Any]) -> EligibleMarketCandidate | None:
        contract_ticker = str(
            market.get("ticker")
            or market.get("contract_ticker")
            or market.get("yes_contract_ticker")
            or ""
        )
        if not contract_ticker:
            return None
        market_ticker = str(market.get("market_ticker") or market.get("event_ticker") or contract_ticker)
        status = str(market.get("status") or market.get("market_status") or "unknown").lower()
        active_open = status in {"active", "open", "initialized", "trading"}
        not_expired = self._not_expired(market)
        orderbook_nonempty = False
        endpoint_available = False
        if active_open and not_expired:
            try:
                book = await asyncio.wait_for(client.get_orderbook(contract_ticker), timeout=self.request_timeout_s)
                endpoint_available = True
                if hasattr(book, "model_dump"):
                    book = book.model_dump()
                if isinstance(book, dict):
                    bids = book.get("bids") or []
                    asks = book.get("asks") or []
                    orderbook_nonempty = bool(bids or asks)
            except Exception:
                endpoint_available = False
        score_value = float(
            active_open
            and not_expired
            and endpoint_available
            and orderbook_nonempty
            and self.request_timeout_s <= 10
        )
        score = MarketEligibilityScore(
            active_open=active_open,
            not_expired=not_expired,
            orderbook_endpoint_available=endpoint_available,
            orderbook_nonempty=orderbook_nonempty,
            bounded_request=self.request_timeout_s <= 10 and self.total_timeout_s <= 45,
            score=score_value,
        )
        return EligibleMarketCandidate(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            status=status,
            orderbook_nonempty=orderbook_nonempty,
            score=score,
            source_mode=MarketDiscoveryMode.REAL_READ_ONLY_DISCOVERY,
        )

    def _not_expired(self, market: dict[str, Any]) -> bool:
        raw = market.get("close_time") or market.get("expiration_time") or market.get("expiration_ts")
        if not raw:
            return True
        try:
            value = str(raw).replace("Z", "+00:00")
            close_time = datetime.fromisoformat(value)
            if close_time.tzinfo is None:
                close_time = close_time.replace(tzinfo=timezone.utc)
            return close_time > datetime.now(timezone.utc)
        except Exception:
            return True

    def _endpoints_called(self, client: Any) -> list[str]:
        if hasattr(client, "endpoints_called"):
            try:
                return sorted(client.endpoints_called())
            except TypeError:
                return sorted(client.endpoints_called)
        return sorted(getattr(client, "called", []))

    def _classify_exception(self, exc: Exception) -> str:
        text = str(exc).lower()
        if any(
            marker in text
            for marker in (
                "401",
                "403",
                "unauthorized",
                "forbidden",
                "credential",
                "invalid",
                "private key",
                "deserialize",
                "pem",
                "sign",
            )
        ):
            return "CREDENTIALS_INVALID"
        if "timeout" in text:
            return "DISCOVERY_TIMEOUT"
        return "REAL_READ_ONLY_DEGRADED"

    def _fallback(self, reason: str) -> MarketDiscoveryProof:
        return MarketDiscoveryProof(
            mode=MarketDiscoveryMode.SAMPLE_STATIC_FALLBACK,
            eligible_candidates=[],
            degradation_reason=reason,
            max_request_timeout_s=self.request_timeout_s,
            total_timeout_s=self.total_timeout_s,
            max_candidates=self.max_candidates,
            real_read_only_used=False,
        )

    def _degraded(self, reason: str) -> MarketDiscoveryProof:
        return MarketDiscoveryProof(
            mode=MarketDiscoveryMode.REAL_READ_ONLY_DEGRADED,
            eligible_candidates=[],
            degradation_reason=reason,
            max_request_timeout_s=self.request_timeout_s,
            total_timeout_s=self.total_timeout_s,
            max_candidates=self.max_candidates,
            real_read_only_used=False,
        )
