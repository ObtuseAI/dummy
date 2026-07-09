"""Config-bound real Kalshi market discovery for V16."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from core.secret_guard import redact
from predator_mesh.v16.runtime_config import KalshiReadOnlyClientFactory, KalshiReadOnlyRuntimeConfig


@dataclass(frozen=True)
class EligibleMarketCandidateV3:
    market_ticker: str
    contract_ticker: str
    status: str
    orderbook_nonempty: bool
    source_mode: str = "REAL_READ_ONLY_DISCOVERY"
    proof_ref: str = "eligible-market-candidate-v3"

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_ticker": self.market_ticker,
            "contract_ticker": self.contract_ticker,
            "status": self.status,
            "orderbook_nonempty": self.orderbook_nonempty,
            "source_mode": self.source_mode,
            "proof_ref": self.proof_ref,
        }


@dataclass(frozen=True)
class RealMarketDiscoveryProofV2:
    mode: str
    eligible_candidate_count: int
    endpoints_called: list[str]
    degradation_reason: str = ""
    max_request_timeout_s: float = 10.0
    total_timeout_s: float = 45.0
    max_candidates: int = 5

    @property
    def read_only_endpoints_only(self) -> bool:
        return all(endpoint.startswith("GET ") for endpoint in self.endpoints_called)

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Real Market Discovery Proof V2",
            "mode": self.mode,
            "eligible_candidate_count": self.eligible_candidate_count,
            "endpoints_called": self.endpoints_called,
            "read_only_endpoints_only": self.read_only_endpoints_only,
            "degradation_reason": self.degradation_reason,
            "max_request_timeout_s": self.max_request_timeout_s,
            "total_timeout_s": self.total_timeout_s,
            "max_candidates": self.max_candidates,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.mode == "REAL_READ_ONLY_DISCOVERY" and self.read_only_endpoints_only else "PARTIAL",
        }


@dataclass(frozen=True)
class RealMarketDiscoveryResultV2:
    mode: str
    eligible_candidates: list[EligibleMarketCandidateV3] = field(default_factory=list)
    degradation_reason: str = ""
    endpoints_called: list[str] = field(default_factory=list)
    max_request_timeout_s: float = 10.0
    total_timeout_s: float = 45.0
    max_candidates: int = 5

    @property
    def eligible_candidate_count(self) -> int:
        return len(self.eligible_candidates)

    @property
    def selected_candidate(self) -> EligibleMarketCandidateV3 | None:
        return self.eligible_candidates[0] if self.eligible_candidates else None

    @property
    def proof(self) -> RealMarketDiscoveryProofV2:
        return RealMarketDiscoveryProofV2(
            mode=self.mode,
            eligible_candidate_count=self.eligible_candidate_count,
            endpoints_called=self.endpoints_called,
            degradation_reason=self.degradation_reason,
            max_request_timeout_s=self.max_request_timeout_s,
            total_timeout_s=self.total_timeout_s,
            max_candidates=self.max_candidates,
        )

    def to_report(self) -> dict[str, Any]:
        return redact(
            {
                "workstream": "V16: Config-Bound Real Market Discovery",
                "mode": self.mode,
                "eligible_candidate_count": self.eligible_candidate_count,
                "eligible_candidates": [candidate.to_dict() for candidate in self.eligible_candidates],
                "degradation_reason": self.degradation_reason,
                "endpoints_called": self.endpoints_called,
                "read_only_endpoints_only": self.proof.read_only_endpoints_only,
                "max_request_timeout_s": self.max_request_timeout_s,
                "total_timeout_s": self.total_timeout_s,
                "verdict": "PASS" if self.mode == "REAL_READ_ONLY_DISCOVERY" else "PARTIAL",
            }
        )

    def candidate_manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Eligible Market Candidate Manifest V3",
            "version": "v3",
            "candidate_count": self.eligible_candidate_count,
            "max_candidates": self.max_candidates,
            "candidates": [candidate.to_dict() for candidate in self.eligible_candidates],
            "account_sensitive_fields_excluded": True,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.eligible_candidates else "PARTIAL",
        }


class ConfigBoundRealKalshiMarketDiscovery:
    def __init__(
        self,
        *,
        runtime_config: KalshiReadOnlyRuntimeConfig,
        read_only_client_factory: Callable[..., Any] | None = None,
        max_candidates: int = 5,
        request_timeout_s: float = 10.0,
        total_timeout_s: float = 45.0,
    ) -> None:
        self.runtime_config = runtime_config
        self.read_only_client_factory = read_only_client_factory
        self.max_candidates = min(max_candidates, 10)
        self.request_timeout_s = min(request_timeout_s, 10.0)
        self.total_timeout_s = min(total_timeout_s, 45.0)

    async def discover(self) -> RealMarketDiscoveryResultV2:
        try:
            return await asyncio.wait_for(self._discover_inner(), timeout=self.total_timeout_s)
        except asyncio.TimeoutError:
            return self._partial("PARTIAL_ENDPOINT_UNAVAILABLE", "DISCOVERY_TIMEOUT")
        except Exception as exc:
            return self._partial("PARTIAL_ENDPOINT_UNAVAILABLE", self._classify_exception(exc))

    def discover_sync(self) -> RealMarketDiscoveryResultV2:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.discover())
        raise RuntimeError(f"discover_sync cannot run inside active event loop {id(loop)}")

    async def _discover_inner(self) -> RealMarketDiscoveryResultV2:
        if not self.runtime_config.ready:
            return self._partial("PARTIAL_CONFIG_BINDING_ERROR", self.runtime_config.invalid_reason)
        with self.runtime_config.credential_environment_overlay():
            client = KalshiReadOnlyClientFactory(
                self.runtime_config,
                client_factory=self.read_only_client_factory,
            ).build()
            try:
                markets = await asyncio.wait_for(client.get_markets(), timeout=self.request_timeout_s)
                if isinstance(markets, dict):
                    markets = markets.get("markets", [])
                candidates: list[EligibleMarketCandidateV3] = []
                inspected = 0
                for market in markets if isinstance(markets, list) else []:
                    if inspected >= self.max_candidates:
                        break
                    if not isinstance(market, dict):
                        continue
                    inspected += 1
                    candidate = await self._candidate(client, market)
                    if candidate is not None and candidate.orderbook_nonempty:
                        candidates.append(candidate)
                endpoints = self._endpoints_called(client)
                if candidates:
                    return RealMarketDiscoveryResultV2(
                        mode="REAL_READ_ONLY_DISCOVERY",
                        eligible_candidates=candidates,
                        endpoints_called=endpoints,
                        max_request_timeout_s=self.request_timeout_s,
                        total_timeout_s=self.total_timeout_s,
                        max_candidates=self.max_candidates,
                    )
                return RealMarketDiscoveryResultV2(
                    mode="PARTIAL_NO_ELIGIBLE_MARKET",
                    eligible_candidates=[],
                    degradation_reason="NO_ELIGIBLE_MARKET",
                    endpoints_called=endpoints,
                    max_request_timeout_s=self.request_timeout_s,
                    total_timeout_s=self.total_timeout_s,
                    max_candidates=self.max_candidates,
                )
            finally:
                if self.read_only_client_factory is None and hasattr(client, "close"):
                    await client.close()

    async def _candidate(self, client: Any, market: dict[str, Any]) -> EligibleMarketCandidateV3 | None:
        contract_ticker = str(market.get("ticker") or market.get("contract_ticker") or market.get("yes_contract_ticker") or "").strip()
        if not contract_ticker:
            return None
        market_ticker = str(market.get("market_ticker") or market.get("event_ticker") or contract_ticker).strip()
        status = str(market.get("status") or market.get("market_status") or "unknown").lower()
        if status not in {"active", "open", "initialized", "trading"}:
            return None
        if not self._not_expired(market):
            return None
        try:
            book = await asyncio.wait_for(client.get_orderbook(contract_ticker), timeout=self.request_timeout_s)
        except Exception:
            return None
        if hasattr(book, "model_dump"):
            book = book.model_dump()
        bids = book.get("bids") if isinstance(book, dict) else []
        asks = book.get("asks") if isinstance(book, dict) else []
        return EligibleMarketCandidateV3(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            status=status,
            orderbook_nonempty=bool(bids or asks),
        )

    def _not_expired(self, market: dict[str, Any]) -> bool:
        raw = market.get("close_time") or market.get("expiration_time") or market.get("expiration_ts")
        if not raw:
            return True
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed > datetime.now(timezone.utc)
        except Exception:
            return True

    def _endpoints_called(self, client: Any) -> list[str]:
        if hasattr(client, "endpoints_called"):
            try:
                return sorted(client.endpoints_called())
            except TypeError:
                return sorted(client.endpoints_called)
        return sorted(getattr(client, "called", []))

    def _partial(self, mode: str, reason: str) -> RealMarketDiscoveryResultV2:
        return RealMarketDiscoveryResultV2(
            mode=mode,
            eligible_candidates=[],
            degradation_reason=reason,
            endpoints_called=[],
            max_request_timeout_s=self.request_timeout_s,
            total_timeout_s=self.total_timeout_s,
            max_candidates=self.max_candidates,
        )

    def _classify_exception(self, exc: Exception) -> str:
        text = str(exc).lower()
        if "timeout" in text:
            return "DISCOVERY_TIMEOUT"
        if any(marker in text for marker in ("401", "403", "unauthorized", "forbidden", "credential", "invalid", "private key", "pem")):
            return "CREDENTIALS_INVALID"
        return "ENDPOINT_UNAVAILABLE"
