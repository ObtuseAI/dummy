from __future__ import annotations
import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import httpx

from core.evidence_dir import EvidencePath
from core.ontology import Contract, Forecast, ForecastOpinion, Market, OrderBook, OrderBookLevel
from core.logger import logger
from forecasting.hybrid_engine import HYBRID_REVIEW_CALL_CAP, HybridForecastEngine
from forecasting.engine import kalshi_fee_cents, signed_edge_after_fees
from forecasting.model_probability_authority import (
    MODEL_PANEL_SOURCE,
    ModelProbabilityAuthorityDecision,
    ModelProbabilityAuthorityRegistry,
    is_sports_model_market,
    model_probability_scope,
)
from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing
from kalshi.normalizer import KalshiNormalizer
from calibration.storage import CalibrationStorage
from calibration.schema import ForecastRecordV2
from calibration.recalibrator import ProbabilityRecalibrator
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.tasks import ModelTask
from autonomy.target_policy import is_prediction_quarantined_target

FORECAST_LOOP_V2_TIMEOUT_SECONDS = 60
# Fusion defaults are deliberately quant-only.  A caller must pass the exact
# earned model weight returned by ModelProbabilityAuthorityRegistry.
DEFAULT_STATISTICAL_WEIGHT = Decimal("1")
DEFAULT_MODEL_WEIGHT = Decimal("0")
MAX_MODEL_DEVIATION_FROM_MARKET = Decimal("0.15")
MODEL_MODE_LIVE_HYBRID = "LIVE_HYBRID"
MODEL_MODE_MOCK_ONLY = "MOCK_ONLY"
MODEL_MODE_DEGRADED_QUANT_ONLY = "DEGRADED_QUANT_ONLY"
EXPECTED_OPENROUTER_API_BASE = "https://openrouter.ai/api"
EXPECTED_OPENROUTER_METADATA_PROVIDER = "openrouter_generic"
LIVE_MARKET_STATUSES = frozenset({"live", "in_play", "in-play"})
PREGAME_MARKET_STATUSES = frozenset(
    {"pre", "pregame", "pre_game", "pre-game", "pre game", "scheduled"}
)

# Static role contracts prevent runtime self-routing or silent model
# substitution. Every envelope is validated against the configured route and
# the provider/model identity actually returned before any synthesis occurs.
REVIEW_ROUTE_CONTRACTS: dict[str, tuple[ModelTask, str, str]] = {
    "primary_forecast": (
        ModelTask.FORECAST_OPINION,
        "gemini_3_6_flash",
        "google/gemini-3.6-flash",
    ),
    "rapid_forecast": (
        ModelTask.RAPID_FORECAST,
        "gpt_5_6_luna",
        "openai/gpt-5.6-luna",
    ),
    "no_trade": (
        ModelTask.NO_TRADE_REASON,
        "glm_5_2",
        "z-ai/glm-5.2",
    ),
    "critique": (
        ModelTask.STRATEGY_CRITIQUE,
        "claude_sonnet_5",
        "anthropic/claude-sonnet-5",
    ),
    "risk": (
        ModelTask.RISK_CRITIQUE,
        "glm_5_2",
        "z-ai/glm-5.2",
    ),
    "thesis": (
        ModelTask.MARKET_THESIS,
        "claude_sonnet_5",
        "anthropic/claude-sonnet-5",
    ),
    "calibration": (
        ModelTask.CALIBRATION_NOTE,
        "glm_5_2",
        "z-ai/glm-5.2",
    ),
}

REVIEW_ROLE_LABELS: dict[str, str] = {
    "primary_forecast": "high_volume_event_data_extraction_and_rapid_probability",
    "rapid_forecast": "low_latency_structured_forecast_and_trade_draft",
    "no_trade": "adversarial_no_trade_and_missing_evidence_gate",
    "critique": "deep_strategy_critique",
    "risk": "adversarial_risk_and_hypothesis_falsification",
    "thesis": "deep_market_thesis_and_strategy_synthesis",
    "calibration": "adversarial_calibration_and_hypothesis_critique",
}

EXPECTED_HYBRID_PROVIDER_MODELS: dict[str, str] = {
    "gemini_3_6_flash": "google/gemini-3.6-flash",
    "gpt_5_6_luna": "openai/gpt-5.6-luna",
    "claude_sonnet_5": "anthropic/claude-sonnet-5",
    "glm_5_2": "z-ai/glm-5.2",
}

REQUIRED_DEFAULT_ROUTES: dict[str, str] = {
    task.value: provider
    for task, provider, _model in REVIEW_ROUTE_CONTRACTS.values()
}
REQUIRED_DEFAULT_ROUTES.update(
    {
        ModelTask.TRADE_DRAFT.value: "gpt_5_6_luna",
        ModelTask.HYBRID_REVIEW.value: "hybrid",
    }
)

REVIEW_CONTENT_REQUIRED_KEYS: dict[str, set[str]] = {
    "primary_forecast": {
        "dummy_probability",
        "confidence_score",
        "uncertainty_band",
        "reasoning",
        "evidence_used",
    },
    "rapid_forecast": {
        "dummy_probability",
        "confidence_score",
        "uncertainty_band",
        "reasoning",
        "action",
        "entry_condition",
    },
    "no_trade": {"reason", "contributing_factors"},
    "critique": {"verdict", "reasoning"},
    "risk": {"risk_level", "reasoning"},
    "thesis": {"thesis", "confidence"},
    "calibration": {"note"},
}


class RealMarketForecastLoop:
    def __init__(
        self,
        hybrid_engine: HybridForecastEngine | None = None,
        storage: CalibrationStorage | None = None,
    ):
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.storage = storage or CalibrationStorage()
        self.credentials_present = False

    async def run(self, contract_tickers: list[str] | None = None) -> dict[str, Any]:
        reader: KalshiRealReadOnly | None = None
        try:
            reader = KalshiRealReadOnly()
            self.credentials_present = True
        except KalshiCredentialsMissing:
            return {"source": "mock", "opinions": [], "reason": "kalshi_credentials_missing"}
        normalizer = KalshiNormalizer()
        tickers = contract_tickers or ["KXELONMARS-99"]
        opinions: list[ForecastOpinion] = []
        try:
            for ticker in tickers:
                if is_prediction_quarantined_target(ticker):
                    continue
                snapshot = await reader.get_full_snapshot(ticker)
                normalized = normalizer.normalize_full_snapshot(snapshot, ticker)
                market = normalized["markets"][0] if normalized["markets"] else None
                if market and is_prediction_quarantined_target(
                    market.ticker, category=market.category,
                ):
                    continue
                orderbook = normalized["orderbook"]
                opinion = await self.hybrid_engine.forecast_opinion(
                    market_ticker=orderbook.market_ticker,
                    contract_ticker=ticker,
                    event_title=market.title if market else ticker,
                    contract_title=ticker,
                    orderbook=orderbook,
                )
                opinions.append(opinion)
                self.storage.append_forecast(opinion)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                return {"source": "mock", "opinions": [], "reason": "kalshi_credentials_unauthorized"}
            raise
        finally:
            if reader is not None:
                await reader.close()

        return {"source": "live", "opinions": [o.model_dump() for o in opinions], "count": len(opinions)}


class RealMarketForecastLoopV2:
    """Real-market forecast loop using fresh Kalshi snapshots and hybrid model reviews.

    Produces native :class:`core.ontology.ForecastOpinion` objects only.  Never
    submits orders.  Falls back to explicit mock data when Kalshi credentials are
    missing and marks the run ``model_mode: MOCK_ONLY`` when live model credentials
    are absent or disabled by routing config.
    """

    def __init__(
        self,
        hybrid_engine: HybridForecastEngine | None = None,
        storage: CalibrationStorage | None = None,
        artifact_dir: str | Path | None = None,
        model_authority_path: str | Path | None = None,
        model_authority_approved_roots: Iterable[str | Path] | None = None,
    ):
        self.hybrid_engine = hybrid_engine or HybridForecastEngine()
        self.storage = storage or CalibrationStorage()
        self.recalibrator = ProbabilityRecalibrator(self.storage.data_dir / "recalibrator.json")
        # EvidencePath (not a bare Path + eager mkdir): constructing the loop
        # must not materialise the gitignored artifacts/dummy tree.  Only the
        # three report writes at the end of a run create the directory, and in
        # a fresh checkout that directory's existence is what the test suite's
        # workstation-evidence probe keys off.
        self.artifact_dir = EvidencePath(artifact_dir or "artifacts/dummy")
        self.credentials_present = False
        self.model_mode = "UNKNOWN"
        self.model_degradation_reasons: list[str] = []
        self.model_authority = ModelProbabilityAuthorityRegistry(
            model_authority_path,
            approved_evidence_roots=model_authority_approved_roots,
        )
        self.model_authority_decisions: dict[str, ModelProbabilityAuthorityDecision] = {}
        self.normalizer = KalshiNormalizer()

    def _determine_model_mode(self) -> str:
        router = self.hybrid_engine.router
        config = router.config
        live_enabled = getattr(config, "live_model_calls_enabled", False)
        self.model_degradation_reasons = []
        if not live_enabled:
            return MODEL_MODE_MOCK_ONLY

        failures: list[str] = []
        expected_voices = set(EXPECTED_HYBRID_PROVIDER_MODELS)
        configured_voices = list(getattr(config, "hybrid_providers", []))
        if (
            len(configured_voices) != len(expected_voices)
            or set(configured_voices) != expected_voices
        ):
            failures.append("hybrid_provider_set_mismatch")

        if len(REVIEW_ROUTE_CONTRACTS) > HYBRID_REVIEW_CALL_CAP:
            failures.append("hybrid_review_call_cap_exceeded")

        for task_name, provider_name in REQUIRED_DEFAULT_ROUTES.items():
            if config.default_provider.get(task_name) != provider_name:
                failures.append(f"route_mismatch:{task_name}")

        for provider_name, expected_model in EXPECTED_HYBRID_PROVIDER_MODELS.items():
            provider_config = config.provider_configs.get(provider_name)
            if provider_config is None:
                failures.append(f"provider_config_missing:{provider_name}")
                continue
            if provider_config.model_name != expected_model:
                failures.append(f"configured_model_mismatch:{provider_name}")
            if provider_config.route_mode != "openrouter":
                failures.append(f"route_mode_mismatch:{provider_name}")
            if provider_config.api_key_env != "OPENROUTER_API_KEY":
                failures.append(f"credential_source_mismatch:{provider_name}")
            if provider_config.api_base.rstrip("/") != EXPECTED_OPENROUTER_API_BASE:
                failures.append(f"api_base_mismatch:{provider_name}")
            provider = getattr(router, "providers", {}).get(provider_name)
            if provider is None or not getattr(provider, "available", False):
                failures.append(f"provider_unavailable:{provider_name}")

        if failures:
            self.model_degradation_reasons = sorted(set(failures))
            return MODEL_MODE_DEGRADED_QUANT_ONLY
        return MODEL_MODE_LIVE_HYBRID

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _explicit_sports_phase(
        market: Market,
        raw_market: dict[str, Any] | None = None,
        contract: Contract | None = None,
    ) -> str:
        """Return ``pre``, ``live``, or ``unknown`` from explicit venue state.

        Generic states such as ``active`` do not establish whether a sports
        event has started. Malformed or conflicting phase fields are also
        unknown, so they can never inherit the pregame authority bucket.
        """
        signals: set[str] = set()
        for value in (market.status, getattr(contract, "status", None)):
            status = str(value or "").strip().lower()
            if status in LIVE_MARKET_STATUSES:
                signals.add("live")
            elif status in PREGAME_MARKET_STATUSES:
                signals.add("pre")

        raw = raw_market if isinstance(raw_market, dict) else {}
        malformed = False
        for field in ("live", "is_live"):
            if field not in raw:
                continue
            value = raw[field]
            if value is True:
                signals.add("live")
            elif value is False:
                signals.add("pre")
            else:
                malformed = True

        for field in ("phase", "market_phase"):
            if field not in raw:
                continue
            phase = str(raw[field] or "").strip().lower()
            if phase in LIVE_MARKET_STATUSES:
                signals.add("live")
            elif phase in PREGAME_MARKET_STATUSES:
                signals.add("pre")
            else:
                malformed = True

        if malformed or len(signals) != 1:
            return "unknown"
        return next(iter(signals))

    @classmethod
    def _is_live_phase(
        cls,
        market: Market,
        raw_market: dict[str, Any] | None = None,
        contract: Contract | None = None,
    ) -> bool | None:
        """Return an explicit live flag; unknown/ambiguous state stays ``None``."""
        phase = cls._explicit_sports_phase(market, raw_market, contract)
        if phase == "live":
            return True
        if phase == "pre":
            return False
        return None

    @staticmethod
    def _freshness_score(ts: datetime, expiration: datetime | None = None) -> Decimal:
        age = max(0.0, (RealMarketForecastLoopV2._now() - ts).total_seconds())
        if expiration is None:
            decay_seconds = 300.0
        else:
            horizon_seconds = max(0.0, (expiration - RealMarketForecastLoopV2._now()).total_seconds())
            decay_seconds = max(60.0, min(3600.0, horizon_seconds * 0.05))
        return Decimal(str(round(max(0.0, 1.0 - age / decay_seconds), 4)))

    def _settlement_risk_score(self, market: Market) -> Decimal:
        text = f"{market.category} {market.title}".lower()
        if "weather" in text:
            return Decimal("0.15")
        if any(k in text for k in ("crypto", "btc", "bitcoin")):
            return Decimal("0.25")
        if any(k in text for k in ("macro", "index", "economic", "spx", "sp500", "nasdaq", "gdp", "inflation")):
            return Decimal("0.20")
        if "politic" in text:
            return Decimal("0.35")
        return Decimal("0.30")

    def _score_market(
        self,
        market: Market,
        contract: Contract,
        orderbook: OrderBook,
    ) -> dict[str, Any] | None:
        if not orderbook.bids or not orderbook.asks:
            return None
        best_bid_level = orderbook.bids[-1]
        best_ask_level = orderbook.asks[0]
        best_bid = best_bid_level.price
        best_ask = best_ask_level.price
        if best_bid >= best_ask:
            return None
        spread = best_ask - best_bid
        mid = (Decimal(best_bid) + Decimal(best_ask)) / Decimal("200")

        total_bid_size = sum(level.size for level in orderbook.bids)
        total_ask_size = sum(level.size for level in orderbook.asks)
        total_size = total_bid_size + total_ask_size

        depth_score = min(Decimal("1"), Decimal(total_size) / Decimal("1000")).quantize(Decimal("0.0001"))
        spread_score = max(Decimal("0"), Decimal("1") - Decimal(spread) / Decimal("10")).quantize(
            Decimal("0.0001")
        )
        liquidity_score = (depth_score * spread_score).quantize(Decimal("0.0001"))
        freshness = (
            orderbook.freshness_score
            if orderbook.freshness_score is not None
            else self._freshness_score(orderbook.source_ts or orderbook.timestamp, contract.expiration)
        )
        settlement = self._settlement_risk_score(market)

        top_size = Decimal(best_bid_level.size + best_ask_level.size)
        imbalance = (
            Decimal(best_bid_level.size - best_ask_level.size) / top_size
            if top_size
            else Decimal("0")
        )
        adjustment = imbalance * Decimal("0.05") * liquidity_score
        dummy_stat = max(Decimal("0"), min(Decimal("1"), mid + adjustment)).quantize(Decimal("0.0001"))

        return {
            "best_bid_cents": best_bid,
            "best_ask_cents": best_ask,
            "spread_cents": spread,
            "market_implied_probability": mid.quantize(Decimal("0.0001")),
            "dummy_statistical_probability": dummy_stat,
            "depth_score": depth_score,
            "spread_score": spread_score,
            "liquidity_score": liquidity_score,
            "freshness_score": freshness,
            "settlement_risk_score": settlement,
            "total_size": total_size,
            "bid_levels": len(orderbook.bids),
            "ask_levels": len(orderbook.asks),
            "expiration_known": contract.expiration is not None,
            "category": market.category,
            "live_phase": self._is_live_phase(market, contract=contract),
            "market_phase": self._explicit_sports_phase(market, contract=contract),
        }

    def _build_base_forecast(
        self,
        market: Market,
        contract: Contract,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> Forecast:
        now = self._now()
        expires = contract.expiration or now
        market_implied = scores["market_implied_probability"]
        dummy_stat = scores["dummy_statistical_probability"]
        delta = (dummy_stat - market_implied).quantize(Decimal("0.0001"))
        confidence = (
            scores["liquidity_score"] * scores["freshness_score"] * (Decimal("1") - scores["settlement_risk_score"])
        ).quantize(Decimal("0.0001"))
        fee = Decimal(kalshi_fee_cents(market_implied)) / Decimal("100")
        edge_after_fees = signed_edge_after_fees(delta, fee)
        return Forecast(
            market_ticker=market.ticker,
            contract_ticker=contract.ticker,
            event_title=market.title,
            contract_title=contract.title,
            market_implied_probability=market_implied,
            dummy_probability=dummy_stat,
            probability_delta=delta,
            confidence_score=confidence,
            uncertainty_band=(
                max(Decimal("0"), dummy_stat - Decimal("0.05")),
                min(Decimal("1"), dummy_stat + Decimal("0.05")),
            ),
            expected_edge=delta,
            edge_after_fees=edge_after_fees.quantize(Decimal("0.0001")),
            freshness_score=scores["freshness_score"],
            liquidity_score=scores["liquidity_score"],
            spread_score=scores["spread_score"],
            orderbook_depth_score=scores["depth_score"],
            settlement_risk_score=scores["settlement_risk_score"],
            source_summary="kalshi_snapshot_v2",
            model_summary="statistical_midpoint",
            calibration_notes=(
                "Deterministic orderbook baseline; no exogenous signal; "
                f"fee_estimate_cents={kalshi_fee_cents(market_implied)}; "
                f"expiration_known={scores['expiration_known']}"
            ),
            timestamp=now,
            expiration=expires,
            strategy_references=["probability_disagreement_v2"],
            proof_reference=f"forecast_v2_{market.ticker}_{contract.ticker}_{now.isoformat()}",
        )

    @staticmethod
    def _safe_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except Exception:
            return {}

    @staticmethod
    def _strict_probability(value: Any) -> Decimal | None:
        if isinstance(value, bool):
            return None
        try:
            parsed = Decimal(str(value))
        except Exception:
            return None
        if not parsed.is_finite() or not Decimal("0") <= parsed <= Decimal("1"):
            return None
        return parsed

    @classmethod
    def _payload_semantic_failures(
        cls,
        review_key: str,
        payload: Any,
    ) -> list[str]:
        if not isinstance(payload, dict):
            return [f"response_schema_invalid:{review_key}"]

        failures: list[str] = []
        if review_key in {"primary_forecast", "rapid_forecast"}:
            probability = cls._strict_probability(payload.get("dummy_probability"))
            confidence = cls._strict_probability(payload.get("confidence_score"))
            if probability is None:
                failures.append(f"response_probability_invalid:{review_key}")
            if confidence is None:
                failures.append(f"response_confidence_invalid:{review_key}")
            band = payload.get("uncertainty_band")
            band_valid = isinstance(band, (list, tuple)) and len(band) == 2
            if band_valid:
                low = cls._strict_probability(band[0])
                high = cls._strict_probability(band[1])
                band_valid = (
                    low is not None
                    and high is not None
                    and probability is not None
                    and low <= probability <= high
                )
            if not band_valid:
                failures.append(f"response_uncertainty_band_invalid:{review_key}")
            if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
                failures.append(f"response_reasoning_invalid:{review_key}")
            if review_key == "primary_forecast":
                evidence = payload.get("evidence_used")
                if not isinstance(evidence, list) or any(
                    not isinstance(item, str) or not item.strip() for item in evidence
                ):
                    failures.append("response_evidence_used_invalid:primary_forecast")
            else:
                if str(payload.get("action", "")).lower() not in {
                    "hold",
                    "consider_yes",
                    "consider_no",
                }:
                    failures.append("response_action_invalid:rapid_forecast")
                if not isinstance(payload.get("entry_condition"), str) or not payload[
                    "entry_condition"
                ].strip():
                    failures.append("response_entry_condition_invalid:rapid_forecast")
        elif review_key == "no_trade":
            reason = payload.get("reason")
            factors = payload.get("contributing_factors")
            if reason is not None and not isinstance(reason, str):
                failures.append("response_reason_invalid:no_trade")
            if not isinstance(factors, list) or any(
                not isinstance(item, str) or not item.strip() for item in factors
            ):
                failures.append("response_factors_invalid:no_trade")
        elif review_key == "critique":
            if str(payload.get("verdict", "")).lower() not in {
                "block",
                "warn",
                "proceed",
            }:
                failures.append("response_verdict_invalid:critique")
            if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
                failures.append("response_reasoning_invalid:critique")
        elif review_key == "risk":
            if str(payload.get("risk_level", "")).lower() not in {
                "low",
                "medium",
                "high",
                "critical",
            }:
                failures.append("response_risk_level_invalid:risk")
            if not isinstance(payload.get("reasoning"), str) or not payload["reasoning"].strip():
                failures.append("response_reasoning_invalid:risk")
        elif review_key == "thesis":
            if not isinstance(payload.get("thesis"), str) or not payload["thesis"].strip():
                failures.append("response_thesis_invalid:thesis")
            if cls._strict_probability(payload.get("confidence")) is None:
                failures.append("response_confidence_invalid:thesis")
        elif review_key == "calibration":
            if not isinstance(payload.get("note"), str) or not payload["note"].strip():
                failures.append("response_note_invalid:calibration")
        return failures

    @staticmethod
    def _quant_only_review_content(review_key: str, base: Forecast) -> dict[str, Any]:
        if review_key in {"primary_forecast", "rapid_forecast"}:
            content = {
                "dummy_probability": str(base.dummy_probability),
                "confidence_score": str(base.confidence_score),
                "uncertainty_band": [
                    str(base.uncertainty_band[0]),
                    str(base.uncertainty_band[1]),
                ],
                "reasoning": "model contribution disabled; quantitative baseline retained",
            }
            if review_key == "primary_forecast":
                content["evidence_used"] = []
            else:
                content.update(
                    {
                        "action": "hold",
                        "entry_condition": "model route unavailable; never submit",
                    }
                )
            return content
        if review_key == "no_trade":
            return {
                "reason": "model route unavailable; trading disabled",
                "contributing_factors": ["model_route_unavailable"],
            }
        if review_key == "critique":
            return {
                "verdict": "block",
                "reasoning": "model route unavailable",
            }
        if review_key == "risk":
            return {
                "risk_level": "high",
                "reasoning": "model route unavailable",
            }
        if review_key == "thesis":
            return {
                "thesis": "model contribution disabled; quantitative baseline retained",
                "confidence": 0,
            }
        return {
            "note": "model contribution disabled; quantitative baseline retained",
        }

    def _quant_only_review_envelope(
        self,
        review_key: str,
        base: Forecast,
        reason: str,
    ) -> ModelResponseEnvelope:
        task, _provider_name, _model_name = REVIEW_ROUTE_CONTRACTS[review_key]
        return ModelResponseEnvelope(
            task=task,
            decision=ModelRouteDecision(
                task=task,
                provider_name="none",
                model_name="none",
                reason=reason,
            ),
            prompt="",
            content=json.dumps(self._quant_only_review_content(review_key, base)),
            raw_metadata={
                "provider": "none",
                "model": "none",
                "error_class": reason,
                "model_mode": self.model_mode,
            },
            latency_ms=0.0,
        )

    def _complete_review_set(
        self,
        review: dict[str, Any] | None,
        base: Forecast,
        reason: str,
    ) -> dict[str, Any]:
        source = review if isinstance(review, dict) else {}
        completed: dict[str, Any] = {"model_mode": self.model_mode}
        for review_key in REVIEW_ROUTE_CONTRACTS:
            envelope = source.get(review_key)
            completed[review_key] = (
                envelope
                if envelope is not None
                else self._quant_only_review_envelope(review_key, base, reason)
            )
        return completed

    def _review_contract_failures(self, review: Any) -> list[str]:
        if not isinstance(review, dict):
            return ["review_not_mapping"]

        failures: list[str] = []
        unexpected_keys = set(review) - (set(REVIEW_ROUTE_CONTRACTS) | {"model_mode"})
        failures.extend(f"unexpected_review:{key}" for key in sorted(unexpected_keys))
        for review_key, (expected_task, expected_provider, expected_model) in REVIEW_ROUTE_CONTRACTS.items():
            envelope = review.get(review_key)
            if envelope is None:
                failures.append(f"missing_review:{review_key}")
                continue
            decision = getattr(envelope, "decision", None)
            if decision is None:
                failures.append(f"missing_decision:{review_key}")
                continue
            if getattr(envelope, "task", None) != expected_task:
                failures.append(f"envelope_task_mismatch:{review_key}")
            if getattr(decision, "task", None) != expected_task:
                failures.append(f"decision_task_mismatch:{review_key}")
            if getattr(decision, "provider_name", None) != expected_provider:
                failures.append(f"provider_mismatch:{review_key}")
            if getattr(decision, "model_name", None) != expected_model:
                failures.append(f"decision_model_mismatch:{review_key}")
            if getattr(decision, "fallback_reason", None):
                failures.append(f"provider_fallback:{review_key}")
            if getattr(envelope, "blocked_by", None):
                failures.append(f"prompt_blocked:{review_key}")

            metadata = getattr(envelope, "raw_metadata", None)
            if not isinstance(metadata, dict):
                failures.append(f"metadata_missing:{review_key}")
            else:
                if metadata.get("provider") != EXPECTED_OPENROUTER_METADATA_PROVIDER:
                    failures.append(f"metadata_provider_mismatch:{review_key}")
                if metadata.get("model") != expected_model:
                    failures.append(f"metadata_model_mismatch:{review_key}")
                if "error_class" not in metadata or metadata.get("error_class") is not None:
                    failures.append(f"provider_error:{review_key}")

            payload = self._safe_json(str(getattr(envelope, "content", "")))
            required_keys = REVIEW_CONTENT_REQUIRED_KEYS[review_key]
            if not isinstance(payload, dict) or not required_keys.issubset(payload):
                failures.append(f"response_schema_invalid:{review_key}")
            else:
                failures.extend(self._payload_semantic_failures(review_key, payload))

        return sorted(set(failures))

    @staticmethod
    def _safe_probability(value: Any, fallback: Decimal) -> Decimal:
        parsed = RealMarketForecastLoopV2._strict_probability(value)
        return parsed if parsed is not None else fallback

    @classmethod
    def _safe_uncertainty_band(
        cls,
        value: Any,
        probability: Decimal,
        fallback_width: Decimal,
    ) -> tuple[Decimal, Decimal]:
        fallback = (
            max(Decimal("0"), probability - fallback_width).quantize(Decimal("0.0001")),
            min(Decimal("1"), probability + fallback_width).quantize(Decimal("0.0001")),
        )
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return fallback
        low = cls._safe_probability(value[0], Decimal("-1"))
        high = cls._safe_probability(value[1], Decimal("-1"))
        if low < 0 or high < 0 or not (low <= probability <= high):
            return fallback
        return low.quantize(Decimal("0.0001")), high.quantize(Decimal("0.0001"))

    @staticmethod
    def _fuse_probabilities(
        market_probability: Decimal,
        statistical_probability: Decimal,
        model_probability: Decimal,
        statistical_weight: Decimal = DEFAULT_STATISTICAL_WEIGHT,
        model_weight: Decimal = DEFAULT_MODEL_WEIGHT,
    ) -> tuple[Decimal, Decimal, Decimal]:
        lower = max(Decimal("0"), market_probability - MAX_MODEL_DEVIATION_FROM_MARKET)
        upper = min(Decimal("1"), market_probability + MAX_MODEL_DEVIATION_FROM_MARKET)
        clamped_model = max(lower, min(upper, model_probability))
        weight_total = statistical_weight + model_weight
        if weight_total <= 0:
            statistical_weight = Decimal("1")
            model_weight = Decimal("0")
            weight_total = Decimal("1")
        fused = (
            statistical_probability * statistical_weight + clamped_model * model_weight
        ) / weight_total
        disagreement = abs(clamped_model - statistical_probability)
        return (
            max(Decimal("0"), min(Decimal("1"), fused)).quantize(Decimal("0.0001")),
            clamped_model.quantize(Decimal("0.0001")),
            disagreement.quantize(Decimal("0.0001")),
        )

    @staticmethod
    def _disagreement_confidence_adjustment(disagreement: Decimal) -> Decimal:
        return -(max(Decimal("0"), disagreement) * Decimal("0.50")).quantize(Decimal("0.0001"))

    def _model_probability_authority_for(
        self,
        base: Forecast,
        scores: dict[str, Any],
    ) -> ModelProbabilityAuthorityDecision:
        scope = model_probability_scope(
            ticker=base.contract_ticker,
            title=f"{base.event_title} {base.contract_title}",
            category=str(scores.get("category") or ""),
            decision_at=base.timestamp,
            expiration=base.expiration,
            live_phase=scores.get("live_phase"),
        )
        sports_phase_unknown = (
            is_sports_model_market(
                ticker=base.contract_ticker,
                category=str(scores.get("category") or ""),
            )
            and scores.get("live_phase") is not True
            and scores.get("live_phase") is not False
        )
        authority_blockers: list[str] = []
        if sports_phase_unknown:
            authority_blockers.append("sports_phase_unknown_or_ambiguous")
        if self.model_mode != MODEL_MODE_LIVE_HYBRID:
            authority_blockers.append("model_mode_not_live_hybrid")
        if authority_blockers:
            decision = ModelProbabilityAuthorityDecision(
                scope=scope,
                weight=Decimal("0"),
                authorized=False,
                blockers=tuple(sorted(authority_blockers)),
            )
        else:
            decision = self.model_authority.evaluate(scope, now=self._now())
        self.model_authority_decisions[scope] = decision
        return decision

    def _model_authority_summary(self) -> dict[str, Any]:
        by_scope = {
            scope: decision.as_dict()
            for scope, decision in sorted(self.model_authority_decisions.items())
        }
        maximum = max(
            (decision.weight for decision in self.model_authority_decisions.values()),
            default=Decimal("0"),
        )
        return {
            "model_probability_authority": float(maximum),
            "model_probability_authority_by_scope": by_scope,
            "authorized_scope_count": sum(
                1 for decision in self.model_authority_decisions.values()
                if decision.authorized
            ),
        }

    def _synthesize_opinion(
        self,
        base: Forecast,
        scores: dict[str, Any],
        reviews: dict[str, Any],
    ) -> ForecastOpinion:
        primary = self._safe_json(reviews["primary_forecast"].content)
        rapid = self._safe_json(reviews["rapid_forecast"].content)
        no_trade = self._safe_json(reviews["no_trade"].content)
        critique = self._safe_json(reviews["critique"].content)
        risk = self._safe_json(reviews["risk"].content)
        thesis = self._safe_json(reviews["thesis"].content)
        calibration = self._safe_json(reviews["calibration"].content)

        live_hybrid = self.model_mode == MODEL_MODE_LIVE_HYBRID
        authority = self._model_probability_authority_for(base, scores)
        model_weight = authority.weight if live_hybrid else Decimal("0")
        statistical_weight = Decimal("1") - model_weight
        if not live_hybrid:
            model_prob = scores["dummy_statistical_probability"]
            model_conf = base.confidence_score
            model_disagreement = Decimal("0")
            voice_disagreement = Decimal("0")
        else:
            primary_probability = self._safe_probability(
                primary.get("dummy_probability"), scores["dummy_statistical_probability"]
            )
            rapid_probability = self._safe_probability(
                rapid.get("dummy_probability"), scores["dummy_statistical_probability"]
            )
            raw_model_prob = (
                (primary_probability + rapid_probability) / Decimal("2")
            ).quantize(Decimal("0.0001"))
            model_prob, _clamped_model_prob, fusion_disagreement = self._fuse_probabilities(
                scores["market_implied_probability"],
                scores["dummy_statistical_probability"],
                raw_model_prob,
                statistical_weight=statistical_weight,
                model_weight=model_weight,
            )
            voice_disagreement = abs(primary_probability - rapid_probability).quantize(
                Decimal("0.0001")
            )
            model_disagreement = max(fusion_disagreement, voice_disagreement)
            if authority.authorized:
                model_conf = (
                    self._safe_probability(
                        primary.get("confidence_score"), base.confidence_score
                    )
                    + self._safe_probability(
                        rapid.get("confidence_score"), base.confidence_score
                    )
                ) / Decimal("2")
            else:
                model_conf = base.confidence_score

        model_prob = self.recalibrator.apply(model_prob, str(scores.get("category") or ""))

        adjustment = Decimal("0")
        verdict = str(critique.get("verdict", "")).lower()
        if verdict == "block":
            adjustment -= Decimal("0.30")
        elif verdict == "warn":
            adjustment -= Decimal("0.10")
        elif verdict == "proceed" and authority.authorized:
            adjustment += Decimal("0.05")

        risk_level = str(risk.get("risk_level", "")).lower()
        if risk_level in ("high", "critical"):
            adjustment -= Decimal("0.15")
        elif risk_level == "medium":
            adjustment -= Decimal("0.05")

        if not live_hybrid:
            adjustment = Decimal("0")
        elif authority.authorized:
            adjustment += self._disagreement_confidence_adjustment(model_disagreement)
        else:
            # Research-only model output is persisted for later grading, but it
            # cannot raise/lower confidence or exercise a trade veto.
            adjustment = Decimal("0")
        final_conf = (model_conf + adjustment).quantize(Decimal("0.0001"))
        final_conf = max(Decimal("0"), min(Decimal("1"), final_conf))

        band_width = ((Decimal("1") - final_conf) * Decimal("0.2")).quantize(Decimal("0.0001"))
        if live_hybrid and authority.authorized:
            primary_low, primary_high = self._safe_uncertainty_band(
                primary.get("uncertainty_band"), model_prob, band_width
            )
            rapid_low, rapid_high = self._safe_uncertainty_band(
                rapid.get("uncertainty_band"), model_prob, band_width
            )
            low, high = min(primary_low, rapid_low), max(primary_high, rapid_high)
        else:
            low, high = self._safe_uncertainty_band(None, model_prob, Decimal("0.05"))

        no_trade_reason: str | None = None
        if self.model_mode == MODEL_MODE_MOCK_ONLY:
            no_trade_reason = "mock mode - simulated opinions; trading disabled"
        elif self.model_mode == MODEL_MODE_DEGRADED_QUANT_ONLY:
            no_trade_reason = "degraded quant-only - hybrid model validation failed; trading disabled"
        elif not scores["expiration_known"]:
            no_trade_reason = "market expiration unavailable"
        elif final_conf < Decimal("0.30"):
            no_trade_reason = (
                no_trade.get("reason") if authority.authorized else None
            ) or "confidence below threshold"
        elif scores["liquidity_score"] < Decimal("0.05"):
            no_trade_reason = (
                no_trade.get("reason") if authority.authorized else None
            ) or "insufficient liquidity"
        elif scores["freshness_score"] < Decimal("0.20"):
            no_trade_reason = (
                no_trade.get("reason") if authority.authorized else None
            ) or "stale market data"
        elif authority.authorized and verdict == "block":
            no_trade_reason = no_trade.get("reason") or f"strategy critique blocked: {critique.get('reasoning', 'n/a')}"
        elif not authority.authorized:
            no_trade_reason = None
        else:
            no_trade_reason = no_trade.get("reason")

        if live_hybrid:
            reasoning = " | ".join(
                [
                    f"Gemini 3.6 evidence/probability: {primary.get('reasoning', 'n/a')}",
                    f"GPT-5.6 Luna rapid forecast: {rapid.get('reasoning', 'n/a')}",
                    f"Claude strategy critique ({verdict or 'none'}): {critique.get('reasoning', 'n/a')}",
                    f"GLM risk ({risk_level or 'none'}): {risk.get('reasoning', 'n/a')}",
                    f"Claude thesis: {thesis.get('thesis', 'n/a')}",
                    f"GLM calibration: {calibration.get('note', 'n/a')}",
                ]
            )
        else:
            reasons = ",".join(self.model_degradation_reasons) or self.model_mode.lower()
            reasoning = f"Quantitative baseline retained with zero model probability authority: {reasons}"

        calibration_notes = [
            f"spread_score={scores['spread_score']}",
            f"depth_score={scores['depth_score']}",
            f"liquidity_score={scores['liquidity_score']}",
            f"freshness_score={scores['freshness_score']}",
            f"settlement_risk_score={scores['settlement_risk_score']}",
            (
                f"fusion_weights=stat:{statistical_weight},model:{model_weight}"
                if live_hybrid
                else "fusion_weights=stat:1,model:0"
            ),
            f"model_probability_authority={model_weight}",
            f"model_probability_scope={authority.scope}",
            f"model_probability_authorized={str(authority.authorized).lower()}",
            f"model_disagreement={model_disagreement}",
            f"independent_forecast_disagreement={voice_disagreement}",
            f"primary_forecast_provider={reviews['primary_forecast'].decision.provider_name}",
            f"rapid_forecast_provider={reviews['rapid_forecast'].decision.provider_name}",
            f"strategy_provider={reviews['critique'].decision.provider_name}",
            f"risk_provider={reviews['risk'].decision.provider_name}",
            f"calibration_provider={reviews['calibration'].decision.provider_name}",
        ]
        calibration_notes.extend(
            f"model_authority_blocker={reason}" for reason in authority.blockers
        )
        calibration_notes.extend(
            f"model_degradation={reason}" for reason in self.model_degradation_reasons
        )

        providers = sorted(
            {
                envelope.decision.provider_name
                for envelope in reviews.values()
                if getattr(envelope, "decision", None) is not None
            }
        )
        if self.model_mode == MODEL_MODE_MOCK_ONLY:
            model_summary = f"MOCK_ONLY({'+'.join(providers) or 'mock'})+deterministic_orderbook_baseline"
        elif self.model_mode == MODEL_MODE_DEGRADED_QUANT_ONLY:
            model_summary = "DEGRADED_QUANT_ONLY+deterministic_orderbook_baseline"
        else:
            mode = "PROBABILITY_AUTHORIZED" if authority.authorized else "RESEARCH_ONLY"
            model_summary = (
                ("+".join(providers) or "provider_metadata_unavailable")
                + f"({mode})"
            )

        return ForecastOpinion(
            market_ticker=base.market_ticker,
            contract_ticker=base.contract_ticker,
            forecast_reference=base.proof_reference,
            market_implied_probability=scores["market_implied_probability"],
            dummy_probability=model_prob,
            probability_delta=(model_prob - scores["market_implied_probability"]).quantize(Decimal("0.0001")),
            model_disagreement=model_disagreement,
            confidence_score=final_conf,
            uncertainty_band=(low, high),
            model_summary=model_summary,
            reasoning=reasoning,
            no_trade_reason=no_trade_reason,
            calibration_notes=calibration_notes,
            timestamp=base.timestamp,
            expiration=base.expiration,
            proof_reference=f"hybrid_forecast_v2_{base.market_ticker}_{base.contract_ticker}_{self._now().isoformat()}",
        )

    def _mock_market_data(self) -> list[tuple[Market, Contract, OrderBook]]:
        now = self._now()
        entries: list[tuple[Market, Contract, OrderBook]] = []

        sports_market = Market(
            ticker="KXMLBGAME-26JUL21NYYBOS-NYY",
            title="Will the Yankees beat the Red Sox?",
            status="active",
            category="Sports",
            event_ticker="KXMLBGAME-26JUL21NYYBOS",
            contracts=[
                Contract(
                    ticker="KXMLBGAME-26JUL21NYYBOS-NYY-YES",
                    title="Yes",
                    status="active",
                    yes_bid=49,
                    yes_ask=51,
                    expiration=now + timedelta(days=1),
                )
            ],
        )
        sports_book = OrderBook(
            market_ticker="KXMLBGAME-26JUL21NYYBOS-NYY",
            contract_ticker="KXMLBGAME-26JUL21NYYBOS-NYY-YES",
            bids=[OrderBookLevel(price=49, size=600)],
            asks=[OrderBookLevel(price=51, size=500)],
            timestamp=now,
        )
        entries.append((sports_market, sports_market.contracts[0], sports_book))

        crypto_market = Market(
            ticker="BTC-ABOVE-100K",
            title="Will Bitcoin trade above $100k at year-end?",
            status="active",
            category="Crypto",
            event_ticker="BTC-ABOVE-100K",
            contracts=[
                Contract(
                    ticker="BTC-ABOVE-100K-YES",
                    title="Yes",
                    status="active",
                    yes_bid=57,
                    yes_ask=63,
                    expiration=now + timedelta(days=30),
                )
            ],
        )
        crypto_book = OrderBook(
            market_ticker="BTC-ABOVE-100K",
            contract_ticker="BTC-ABOVE-100K-YES",
            bids=[OrderBookLevel(price=57, size=300)],
            asks=[OrderBookLevel(price=63, size=300)],
            timestamp=now,
        )
        entries.append((crypto_market, crypto_market.contracts[0], crypto_book))

        macro_market = Market(
            ticker="SPX-ABOVE-5000",
            title="Will S&P 500 close above 5000?",
            status="active",
            category="Macro",
            event_ticker="SPX-ABOVE-5000",
            contracts=[
                Contract(
                    ticker="SPX-ABOVE-5000-YES",
                    title="Yes",
                    status="active",
                    yes_bid=48,
                    yes_ask=52,
                    expiration=now + timedelta(days=7),
                )
            ],
        )
        macro_book = OrderBook(
            market_ticker="SPX-ABOVE-5000",
            contract_ticker="SPX-ABOVE-5000-YES",
            bids=[OrderBookLevel(price=48, size=800)],
            asks=[OrderBookLevel(price=52, size=800)],
            timestamp=now,
        )
        entries.append((macro_market, macro_market.contracts[0], macro_book))

        politics_market = Market(
            ticker="POLITICS-WHO-WINS",
            title="Who will win the upcoming election?",
            status="active",
            category="Politics",
            event_ticker="POLITICS-WHO-WINS",
            contracts=[
                Contract(
                    ticker="POLITICS-WHO-WINS-YES",
                    title="Incumbent",
                    status="active",
                    yes_bid=30,
                    yes_ask=70,
                    expiration=now + timedelta(days=90),
                )
            ],
        )
        politics_book = OrderBook(
            market_ticker="POLITICS-WHO-WINS",
            contract_ticker="POLITICS-WHO-WINS-YES",
            bids=[OrderBookLevel(price=30, size=50)],
            asks=[OrderBookLevel(price=70, size=50)],
            timestamp=now,
        )
        entries.append((politics_market, politics_market.contracts[0], politics_book))

        stale_market = Market(
            ticker="MEME-STALE",
            title="Will a meme coin trend today?",
            status="active",
            category="Entertainment",
            event_ticker="MEME-STALE",
            contracts=[
                Contract(
                    ticker="MEME-STALE-YES",
                    title="Yes",
                    status="active",
                    yes_bid=49,
                    yes_ask=51,
                    expiration=now + timedelta(hours=6),
                )
            ],
        )
        stale_book = OrderBook(
            market_ticker="MEME-STALE",
            contract_ticker="MEME-STALE-YES",
            bids=[OrderBookLevel(price=49, size=1)],
            asks=[OrderBookLevel(price=51, size=1)],
            timestamp=now,
            freshness_score=Decimal("0.10"),
        )
        entries.append((stale_market, stale_market.contracts[0], stale_book))

        return entries

    def _select_from_scored(
        self,
        scored: list[tuple[Market, Contract, OrderBook, dict[str, Any]]],
        max_markets: int,
    ) -> list[tuple[Market, Contract, OrderBook, dict[str, Any]]]:
        scored = [
            item for item in scored
            if not is_prediction_quarantined_target(
                item[0].ticker,
                category=item[0].category,
            )
        ]
        selected: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
        used: set[str] = set()

        def add(predicate):
            for item in scored:
                if item[1].ticker in used:
                    continue
                if predicate(item):
                    selected.append(item)
                    used.add(item[1].ticker)
                    return True
            return False

        add(lambda item: "sport" in f"{item[0].category}".lower())
        add(lambda item: any(k in f"{item[0].category} {item[0].title}".lower() for k in ("crypto", "btc", "bitcoin")))
        add(lambda item: any(k in f"{item[0].category} {item[0].title}".lower() for k in ("macro", "index", "economic", "spx", "sp500", "nasdaq", "gdp", "inflation")))
        for item in sorted(scored, key=lambda x: float(x[3]["liquidity_score"]), reverse=True):
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
                break
        for item in sorted(scored, key=lambda x: (x[3]["spread_cents"] or 0), reverse=True):
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
                break
        for item in sorted(scored, key=lambda x: float(x[3]["freshness_score"]) * float(x[3]["depth_score"])):
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
                break
        for item in sorted(scored, key=lambda x: float(x[3]["liquidity_score"]), reverse=True):
            if len(selected) >= max_markets:
                break
            if item[1].ticker not in used:
                selected.append(item)
                used.add(item[1].ticker)
        return selected[:max_markets]

    async def _fetch_live_market_data(
        self,
        reader: KalshiRealReadOnly,
        max_markets: int,
    ) -> list[tuple[Market, Contract, OrderBook, dict[str, Any]]]:
        markets_raw = await reader.get_markets()
        markets = self.normalizer.normalize_markets(markets_raw)
        raw_rows = (
            markets_raw.get("markets", [])
            if isinstance(markets_raw, dict)
            else markets_raw
        )
        raw_by_ticker = {
            str(row.get("ticker") or ""): row
            for row in raw_rows
            if isinstance(row, dict) and row.get("ticker")
        }
        candidates: list[tuple[Market, Contract]] = []
        for market in markets:
            if market.status.lower() not in ({"active"} | LIVE_MARKET_STATUSES):
                continue
            if is_prediction_quarantined_target(
                market.ticker,
                category=market.category,
            ):
                continue
            for contract in market.contracts:
                if contract.status.lower() not in ({"active"} | LIVE_MARKET_STATUSES):
                    continue
                candidates.append((market, contract))

        # Bound orderbook fetches while avoiding API-order bias. The fixed seed
        # makes audits and tests reproducible.
        random.Random(20260720).shuffle(candidates)
        sample = candidates[: max(max_markets * 4, 20)]
        scored: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
        for market, contract in sample:
            try:
                raw_book = await reader.get_orderbook(contract.ticker)
                orderbook = self.normalizer.normalize_orderbook(contract.ticker, raw_book)
                orderbook.market_ticker = market.ticker
                orderbook.contract_ticker = contract.ticker
                scores = self._score_market(market, contract, orderbook)
                if scores is not None:
                    raw_market = raw_by_ticker.get(market.ticker)
                    scores["live_phase"] = self._is_live_phase(
                        market,
                        raw_market,
                        contract,
                    )
                    scores["market_phase"] = self._explicit_sports_phase(
                        market,
                        raw_market,
                        contract,
                    )
                    scored.append((market, contract, orderbook, scores))
            except Exception:
                continue
        return self._select_from_scored(scored, max_markets)

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _write_artifacts(
        self,
        snapshot_source: str,
        reader: KalshiRealReadOnly | None,
        entries: list[tuple[Market, Contract, OrderBook, dict[str, Any]]],
        reviews: list[dict[str, Any]],
        opinions: list[ForecastOpinion],
        max_markets: int,
    ) -> dict[str, Path]:
        now = self._now()
        authority_summary = self._model_authority_summary()
        endpoints_called: set[str] = set()
        order_creating: set[str] = set()
        if reader is not None and self.credentials_present:
            endpoints_called = reader.endpoints_called()
            order_creating = reader.order_creating_endpoints_called()

        report_path = self.artifact_dir / "real_market_forecast_loop_report_v2.json"
        manifest_path = self.artifact_dir / "forecast_opinion_manifest_v2.json"
        proof_path = self.artifact_dir / "live_hybrid_forecast_proof_report_v1.json"
        role_contracts = {
            review_key: {
                "role": REVIEW_ROLE_LABELS[review_key],
                "task": task.value,
                "provider": provider,
                "model": model,
            }
            for review_key, (task, provider, model) in REVIEW_ROUTE_CONTRACTS.items()
        }

        report = {
            "report_type": "real_market_forecast_loop_v2",
            "generated_at": now.isoformat(),
            "source": snapshot_source,
            "model_mode": self.model_mode,
            "model_panel_source": MODEL_PANEL_SOURCE,
            "hybrid_review_call_cap": HYBRID_REVIEW_CALL_CAP,
            "hybrid_role_contracts": role_contracts,
            **authority_summary,
            "model_degradation_reasons": self.model_degradation_reasons,
            "kalshi_credentials_present": self.credentials_present,
            "max_markets": max_markets,
            "market_count": len(entries),
            "opinion_count": len(opinions),
            "endpoints_called": sorted(endpoints_called),
            "order_creating_endpoints_called": sorted(order_creating),
            "markets": [
                {
                    "market_ticker": market.ticker,
                    "contract_ticker": contract.ticker,
                    "title": market.title,
                    "category": market.category,
                    "best_bid_cents": scores["best_bid_cents"],
                    "best_ask_cents": scores["best_ask_cents"],
                    "spread_cents": scores["spread_cents"],
                    "market_implied_probability": str(scores["market_implied_probability"]),
                    "dummy_statistical_probability": str(scores["dummy_statistical_probability"]),
                    "depth_score": str(scores["depth_score"]),
                    "spread_score": str(scores["spread_score"]),
                    "liquidity_score": str(scores["liquidity_score"]),
                    "freshness_score": str(scores["freshness_score"]),
                    "settlement_risk_score": str(scores["settlement_risk_score"]),
                }
                for market, contract, _orderbook, scores in entries
            ],
            "model_decisions": [
                {
                    "market_ticker": op.market_ticker,
                    "contract_ticker": op.contract_ticker,
                    "primary_forecast_decision": review["primary_forecast"].decision.model_dump(mode="json"),
                    "rapid_forecast_decision": review["rapid_forecast"].decision.model_dump(mode="json"),
                    "no_trade_decision": review["no_trade"].decision.model_dump(mode="json"),
                    "critique_decision": review["critique"].decision.model_dump(mode="json"),
                    "risk_decision": review["risk"].decision.model_dump(mode="json"),
                    "thesis_decision": review["thesis"].decision.model_dump(mode="json"),
                    "calibration_decision": review["calibration"].decision.model_dump(mode="json"),
                }
                for op, review in zip(opinions, reviews)
            ],
            "opinions": [op.model_dump(mode="json") for op in opinions],
        }
        report_path.write_text(json.dumps(report, indent=2, default=self._json_default))

        manifest = {
            "manifest_type": "forecast_opinion_manifest_v2",
            "generated_at": now.isoformat(),
            "model_mode": self.model_mode,
            "model_panel_source": MODEL_PANEL_SOURCE,
            "hybrid_role_contracts": role_contracts,
            **authority_summary,
            "model_degradation_reasons": self.model_degradation_reasons,
            "source": snapshot_source,
            "opinion_count": len(opinions),
            "opinions": [op.model_dump(mode="json") for op in opinions],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, default=self._json_default))

        proof = {
            "report_type": "live_hybrid_forecast_proof_v1",
            "generated_at": now.isoformat(),
            "model_mode": self.model_mode,
            "model_panel_source": MODEL_PANEL_SOURCE,
            "hybrid_review_call_cap": HYBRID_REVIEW_CALL_CAP,
            "hybrid_role_contracts": role_contracts,
            **authority_summary,
            "model_degradation_reasons": self.model_degradation_reasons,
            "kalshi_credentials_present": self.credentials_present,
            "no_order_submitted": True,
            "endpoints_called": sorted(endpoints_called),
            "order_creating_endpoints_called": sorted(order_creating),
            "model_provider_decisions": report["model_decisions"],
            "opinion_count": len(opinions),
            "opinion_proof_references": [op.proof_reference for op in opinions],
        }
        proof_path.write_text(json.dumps(proof, indent=2, default=self._json_default))

        return {
            "report": report_path,
            "manifest": manifest_path,
            "proof": proof_path,
        }

    async def _run_inner(self, max_markets: int = 5) -> dict[str, Any]:
        self.model_authority_decisions = {}
        self.model_mode = self._determine_model_mode()
        self.recalibrator.fit(
            self.storage.load_all_forecasts_v2(),
            self.storage.load_settlements(),
        )
        reader: KalshiRealReadOnly | None = None
        try:
            reader = KalshiRealReadOnly()
            self.credentials_present = True
        except KalshiCredentialsMissing:
            self.credentials_present = False

        entries: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
        snapshot_source = "live"
        try:
            if reader is None:
                snapshot_source = "mock"
                mock_entries = self._mock_market_data()
                scored_mock: list[tuple[Market, Contract, OrderBook, dict[str, Any]]] = []
                for market, contract, orderbook in mock_entries:
                    scores = self._score_market(market, contract, orderbook)
                    if scores is not None:
                        scored_mock.append((market, contract, orderbook, scores))
                entries = self._select_from_scored(
                    scored_mock,
                    max_markets,
                )
            else:
                entries = await self._fetch_live_market_data(reader, max_markets)
        finally:
            if reader is not None:
                await reader.close()

        # A paid model review of deterministic fallback fixtures is not live
        # research evidence.  Degrade before constructing any panel coroutine
        # so missing Kalshi credentials/data can never spend OpenRouter budget.
        if snapshot_source != "live" and self.model_mode == MODEL_MODE_LIVE_HYBRID:
            self.model_mode = MODEL_MODE_DEGRADED_QUANT_ONLY
            self.model_degradation_reasons = sorted(
                set(self.model_degradation_reasons + ["non_live_market_data"])
            )

        prepared: list[tuple[Market, Contract, OrderBook, dict[str, Any], Forecast]] = []
        for market, contract, orderbook, scores in entries:
            base = self._build_base_forecast(market, contract, orderbook, scores)
            prepared.append((market, contract, orderbook, scores, base))

        raw_reviews: list[dict[str, Any] | None] = []
        review_failures: list[str] = []
        if self.model_mode == MODEL_MODE_LIVE_HYBRID:
            for index, (market, contract, orderbook, scores, base) in enumerate(prepared):
                try:
                    raw_review = await self.hybrid_engine.hybrid_review(
                        base=base,
                        orderbook=orderbook,
                        market=market,
                        contract=contract,
                        scores=scores,
                        model_mode=self.model_mode,
                    )
                except Exception as exc:
                    raw_review = None
                    review_failures.append(
                        f"review_exception:{contract.ticker}:{type(exc).__name__}"
                    )
                current_failures = self._review_contract_failures(raw_review)
                for failure in current_failures:
                    review_failures.append(f"{contract.ticker}:{failure}")
                raw_reviews.append(raw_review)
                if current_failures:
                    # The panel is atomic across the run. Stop before paying
                    # for any later market once the first contract fails its
                    # route/identity/schema contract.
                    raw_reviews.extend(
                        None for _remaining in prepared[index + 1 :]
                    )
                    break

            if review_failures:
                self.model_mode = MODEL_MODE_DEGRADED_QUANT_ONLY
                self.model_degradation_reasons = sorted(
                    set(self.model_degradation_reasons + review_failures)
                )
        else:
            # Deliberate MOCK_ONLY and failed preflight never invoke a provider.
            raw_reviews = [None for _item in prepared]

        placeholder_reason = (
            "live_model_calls_disabled"
            if self.model_mode == MODEL_MODE_MOCK_ONLY
            else "hybrid_model_validation_failed"
        )
        reviews = [
            self._complete_review_set(raw_review, base, placeholder_reason)
            for raw_review, (_market, _contract, _orderbook, _scores, base)
            in zip(raw_reviews, prepared)
        ]

        opinions: list[ForecastOpinion] = []
        for (market, contract, _orderbook, scores, base), review in zip(prepared, reviews):
            opinion = self._synthesize_opinion(base, scores, review)
            opinions.append(opinion)
            self.storage.append_forecast(opinion)
            primary = self._safe_json(review["primary_forecast"].content)
            rapid = self._safe_json(review["rapid_forecast"].content)
            confidence = opinion.confidence_score
            confidence_bucket = "high" if confidence >= Decimal("0.7") else (
                "medium" if confidence >= Decimal("0.4") else "low"
            )
            self.storage.append_forecast_v2(
                ForecastRecordV2(
                    forecast_id=opinion.proof_reference,
                    market_ticker=opinion.market_ticker,
                    contract_ticker=opinion.contract_ticker,
                    category=market.category,
                    model_route=opinion.model_summary,
                    market_implied_probability=opinion.market_implied_probability,
                    dummy_probability=base.dummy_probability,
                    # Historical storage-column name retained for migrations;
                    # the value is the exact four-panel's two independent
                    # forecast voices, averaged before any authority weighting.
                    deepseekv4flash_probability=(
                        (
                            self._safe_probability(
                                primary.get("dummy_probability"), base.dummy_probability
                            )
                            + self._safe_probability(
                                rapid.get("dummy_probability"), base.dummy_probability
                            )
                        )
                        / Decimal("2")
                        if self.model_mode == MODEL_MODE_LIVE_HYBRID
                        else None
                    ),
                    final_probability=opinion.dummy_probability,
                    confidence_bucket=confidence_bucket,
                    timestamp=opinion.timestamp,
                    no_trade_reason=opinion.no_trade_reason,
                )
            )

        artifact_paths = self._write_artifacts(snapshot_source, reader, entries, reviews, opinions, max_markets)

        return {
            "source": snapshot_source,
            "model_mode": self.model_mode,
            **self._model_authority_summary(),
            "model_degradation_reasons": self.model_degradation_reasons,
            "kalshi_credentials_present": self.credentials_present,
            "opinions": [op.model_dump(mode="json") for op in opinions],
            "count": len(opinions),
            "artifact_paths": {k: str(v) for k, v in artifact_paths.items()},
        }

    async def run(self, max_markets: int = 5) -> dict[str, Any]:
        """Run the V2 forecast loop with a hard outer timeout."""
        try:
            return await asyncio.wait_for(
                self._run_inner(max_markets=max_markets),
                timeout=FORECAST_LOOP_V2_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "RealMarketForecastLoopV2.run timed out",
                extra={"component": "real_market_forecast_loop_v2", "max_markets": max_markets},
            )
            return {
                "source": "timeout",
                "model_mode": "MOCK_ONLY",
                "model_probability_authority": 0,
                "model_probability_authority_by_scope": {},
                "authorized_scope_count": 0,
                "kalshi_credentials_present": False,
                "opinions": [],
                "count": 0,
                "reason": "forecast_loop_v2_timeout",
            }
