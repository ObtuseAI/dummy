from __future__ import annotations
import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from core.ontology import Contract, Forecast, ForecastOpinion, Market, MarketThesis, OrderBook
from forecasting.engine import ForecastEngine
from model_router.router import ModelRouter
from model_router.tasks import ModelTask


class HybridForecastEngine:
    def __init__(self, base_engine: ForecastEngine | None = None, router: ModelRouter | None = None):
        self.base_engine = base_engine or ForecastEngine()
        self.router = router or ModelRouter()

    async def forecast_opinion(
        self,
        market_ticker: str,
        contract_ticker: str,
        event_title: str,
        contract_title: str,
        orderbook: OrderBook,
    ) -> ForecastOpinion:
        base = self.base_engine.forecast(market_ticker, contract_ticker, event_title, contract_title, orderbook)
        prompt = self._build_forecast_prompt(base, orderbook)
        envelope = await self.router.call(
            ModelTask.FORECAST_OPINION,
            prompt,
            context={"market_ticker": market_ticker, "contract_ticker": contract_ticker},
        )
        return self._parse_opinion(envelope.content, base)

    def _build_forecast_prompt(self, base: Forecast, orderbook: OrderBook) -> str:
        return (
            f"Market: {base.market_ticker}\n"
            f"Contract: {base.contract_ticker}\n"
            f"Market-implied probability: {base.market_implied_probability}\n"
            f"Dummy base probability: {base.dummy_probability}\n"
            f"Edge after fees: {base.edge_after_fees}\n"
            f"Orderbook best bid/ask: {orderbook.bids[-1].price if orderbook.bids else None} / {orderbook.asks[0].price if orderbook.asks else None}\n"
            "Return a JSON object with keys: dummy_probability, confidence_score, uncertainty_band [low, high], reasoning, no_trade_reason (optional), calibration_notes (list)."
        )

    def _parse_opinion(self, content: str, base: Forecast) -> ForecastOpinion:
        try:
            data = json.loads(content)
        except Exception:
            data = {}
        dummy_prob = Decimal(str(data.get("dummy_probability", base.dummy_probability)))
        confidence = Decimal(str(data.get("confidence_score", base.confidence_score)))
        band = data.get("uncertainty_band") or [float(max(Decimal("0"), dummy_prob - Decimal("0.05"))), float(min(Decimal("1"), dummy_prob + Decimal("0.05")))]
        return ForecastOpinion(
            market_ticker=base.market_ticker,
            contract_ticker=base.contract_ticker,
            forecast_reference=base.proof_reference,
            market_implied_probability=base.market_implied_probability,
            dummy_probability=dummy_prob,
            probability_delta=(dummy_prob - base.market_implied_probability).quantize(Decimal("0.0001")),
            confidence_score=confidence,
            uncertainty_band=(Decimal(str(band[0])), Decimal(str(band[1]))),
            model_summary="hybrid_router",
            reasoning=str(data.get("reasoning", "no model reasoning")),
            no_trade_reason=data.get("no_trade_reason"),
            calibration_notes=data.get("calibration_notes", []),
            timestamp=datetime.now(timezone.utc),
            expiration=datetime.now(timezone.utc) + timedelta(hours=1),
            proof_reference=f"hybrid_forecast_{base.market_ticker}_{datetime.now(timezone.utc).isoformat()}",
        )

    async def market_thesis(self, market_ticker: str, contract_ticker: str, context: dict[str, Any]) -> MarketThesis:
        prompt = f"Write a concise market thesis for {market_ticker}/{contract_ticker}. Context: {context}"
        envelope = await self.router.call(ModelTask.MARKET_THESIS, prompt, context=context)
        try:
            data = json.loads(envelope.content)
        except Exception:
            data = {}
        return MarketThesis(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            thesis=data.get("thesis", "no thesis"),
            bullish_signals=data.get("bullish_signals", []),
            bearish_signals=data.get("bearish_signals", []),
            source=envelope.decision.provider_name,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _safe_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except Exception:
            return {}

    async def route_task(
        self,
        task: ModelTask,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Route a single model task through the underlying router."""
        return await self.router.call(task, prompt, context=context)

    def _build_deepseek_v2_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            f"Market: {base.market_ticker}\n"
            f"Contract: {base.contract_ticker}\n"
            f"Title: {base.event_title}\n"
            f"Market-implied probability: {base.market_implied_probability}\n"
            f"Dummy statistical estimate: {base.dummy_probability}\n"
            f"Edge after fees: {base.edge_after_fees}\n"
            f"Best bid/ask (cents): "
            f"{orderbook.bids[-1].price if orderbook.bids else None} / "
            f"{orderbook.asks[0].price if orderbook.asks else None}\n"
            f"Quality scores: spread={scores.get('spread_score')}, "
            f"depth={scores.get('depth_score')}, liquidity={scores.get('liquidity_score')}, "
            f"freshness={scores.get('freshness_score')}, settlement_risk={scores.get('settlement_risk_score')}\n"
            "Return a JSON object with keys: dummy_probability, confidence_score, "
            "uncertainty_band [low, high], reasoning, no_trade_reason (optional), calibration_notes (list)."
        )

    def _build_no_trade_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            f"Assess whether {base.market_ticker}/{base.contract_ticker} should be traded. "
            f"Dummy probability: {base.dummy_probability}, liquidity score: {scores.get('liquidity_score')}, "
            f"freshness score: {scores.get('freshness_score')}. "
            "Return JSON with keys: reason (string or null), contributing_factors (list)."
        )

    def _build_critique_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            f"Critique the strategy for {base.market_ticker}/{base.contract_ticker}. "
            f"Edge after fees: {base.edge_after_fees}, liquidity: {scores.get('liquidity_score')}, "
            f"settlement risk: {scores.get('settlement_risk_score')}. "
            "Return JSON with keys: verdict (proceed/warn/block), edge_assessment, "
            "risk_assessment, confidence_adjustment (number), reasoning."
        )

    def _build_risk_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            f"Assess market and settlement risk for {base.market_ticker}/{base.contract_ticker}. "
            f"Settlement risk score: {scores.get('settlement_risk_score')}, "
            f"freshness score: {scores.get('freshness_score')}. "
            "Return JSON with keys: risk_level (low/medium/high), reasoning."
        )

    def _build_thesis_prompt(
        self,
        base: Forecast,
        market: Market | None,
        contract: Contract | None,
        scores: dict[str, Any],
    ) -> str:
        category = getattr(market, "category", "unknown")
        title = getattr(market, "title", base.event_title)
        return (
            f"Write a concise market thesis for {base.market_ticker}/{base.contract_ticker}. "
            f"Title: {title}. Category: {category}. "
            f"Market-implied probability: {base.market_implied_probability}. "
            "Return JSON with keys: thesis, bullish_signals (list), bearish_signals (list), confidence (0-1)."
        )

    async def hybrid_review(
        self,
        base: Forecast,
        orderbook: OrderBook,
        market: Market | None = None,
        contract: Contract | None = None,
        scores: dict[str, Any] | None = None,
        model_mode: str = "MOCK_ONLY",
    ) -> dict[str, Any]:
        """Run DeepSeekV4Flash first-pass and MinimaxM3 critique tasks for a market.

        The underlying :class:`model_router.router.ModelRouter` maps each
        :class:`model_router.tasks.ModelTask` to its configured default provider
        (DeepSeekV4Flash or MinimaxM3).  If credentials are missing or live calls
        are disabled, the router falls back to MockProvider and this method
        still returns all required envelopes.
        """
        scores = scores or {}
        context = {"market_ticker": base.market_ticker, "contract_ticker": base.contract_ticker}
        deep_prompt = self._build_deepseek_v2_prompt(base, orderbook, scores)
        no_trade_prompt = self._build_no_trade_prompt(base, orderbook, scores)
        critique_prompt = self._build_critique_prompt(base, orderbook, scores)
        risk_prompt = self._build_risk_prompt(base, orderbook, scores)
        thesis_prompt = self._build_thesis_prompt(base, market, contract, scores)

        deep_env, no_trade_env, critique_env, risk_env, thesis_env = await asyncio.gather(
            self.router.call(ModelTask.FORECAST_OPINION, deep_prompt, context=context),
            self.router.call(ModelTask.NO_TRADE_REASON, no_trade_prompt, context=context),
            self.router.call(ModelTask.STRATEGY_CRITIQUE, critique_prompt, context=context),
            self.router.call(ModelTask.RISK_CRITIQUE, risk_prompt, context=context),
            self.router.call(ModelTask.MARKET_THESIS, thesis_prompt, context=context),
        )

        return {
            "model_mode": model_mode,
            "deepseek_forecast": deep_env,
            "no_trade": no_trade_env,
            "critique": critique_env,
            "risk": risk_env,
            "thesis": thesis_env,
        }
