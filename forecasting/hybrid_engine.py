from __future__ import annotations
import asyncio
import json
from typing import Any
from core.ontology import Contract, Forecast, Market, OrderBook
from model_router.router import ModelRouter
from model_router.tasks import ModelTask

HYBRID_REVIEW_CALL_CAP = 7


class HybridForecastEngine:
    """Model-review router for an already-built maintained V2 forecast.

    This class deliberately does not construct forecasts. The retired V1
    ``ForecastEngine`` was a parallel deterministic stack with fabricated
    constants. ``RealMarketForecastLoopV2`` owns current snapshot scoring and
    passes its evidence-bound base forecast into :meth:`hybrid_review`.
    """

    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

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

    def _build_primary_forecast_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            "Role: Gemini high-volume event/data extractor and rapid independent probability forecaster.\n"
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
            "First identify only the supplied evidence that materially changes the base rate; never invent "
            "news, injuries, prices, statistics, or unavailable context. Return a JSON object with keys: "
            "dummy_probability, confidence_score, uncertainty_band [low, high], reasoning, "
            "evidence_used (list of supplied facts), no_trade_reason (optional), calibration_notes (list)."
        )

    def _build_rapid_forecast_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            "Role: GPT-5.6 Luna low-latency independent structured forecast and trade-draft pass.\n"
            f"Market: {base.market_ticker}\nContract: {base.contract_ticker}\n"
            f"Title: {base.event_title}\n"
            f"Market-implied probability: {base.market_implied_probability}\n"
            f"Dummy statistical estimate: {base.dummy_probability}\n"
            f"Edge after fees: {base.edge_after_fees}\n"
            f"Best bid/ask (cents): "
            f"{orderbook.bids[-1].price if orderbook.bids else None} / "
            f"{orderbook.asks[0].price if orderbook.asks else None}\n"
            f"Quality scores: spread={scores.get('spread_score')}, "
            f"depth={scores.get('depth_score')}, liquidity={scores.get('liquidity_score')}, "
            f"freshness={scores.get('freshness_score')}.\n"
            "Make an independent estimate without seeing another model's response. Return JSON with keys: "
            "dummy_probability, confidence_score, uncertainty_band [low, high], reasoning, "
            "action (hold/consider_yes/consider_no), entry_condition (string). This is a research draft, "
            "never an order instruction."
        )

    def _build_no_trade_prompt(
        self,
        base: Forecast,
        orderbook: OrderBook,
        scores: dict[str, Any],
    ) -> str:
        return (
            "Role: GLM-5.2 adversarial no-trade and missing-evidence gate. "
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
            "Role: Claude Sonnet 5 deep strategy critic. Seek structural edge and failure modes. "
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
            "Role: GLM-5.2 adversarial risk and hypothesis falsification critic. "
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
            "Role: Claude Sonnet 5 deep market-thesis and strategy synthesis specialist. "
            f"Write a concise market thesis for {base.market_ticker}/{base.contract_ticker}. "
            f"Title: {title}. Category: {category}. "
            f"Market-implied probability: {base.market_implied_probability}. "
            "Return JSON with keys: thesis, bullish_signals (list), bearish_signals (list), confidence (0-1)."
        )

    def _build_calibration_prompt(
        self,
        base: Forecast,
        scores: dict[str, Any],
    ) -> str:
        return (
            "Role: GLM-5.2 adversarial calibration and hypothesis critic. "
            f"For {base.market_ticker}/{base.contract_ticker}, assess whether the supplied "
            f"statistical estimate {base.dummy_probability} is likely overconfident, underconfident, "
            f"or missing a falsifying condition. Data-quality scores: {scores}. "
            "Return JSON with key note (a concise calibration/falsification note)."
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
        """Run the bounded four-model OpenRouter research panel for a market.

        Seven statically routed, role-specific calls are made in parallel. The
        voices remain independent: no model sees another model's response.
        Callers must validate every envelope before synthesizing. Missing,
        malformed, substituted, or fallback responses invalidate the whole
        batch and retain the quantitative baseline.
        """
        scores = scores or {}
        context = {"market_ticker": base.market_ticker, "contract_ticker": base.contract_ticker}
        primary_prompt = self._build_primary_forecast_prompt(base, orderbook, scores)
        rapid_prompt = self._build_rapid_forecast_prompt(base, orderbook, scores)
        no_trade_prompt = self._build_no_trade_prompt(base, orderbook, scores)
        critique_prompt = self._build_critique_prompt(base, orderbook, scores)
        risk_prompt = self._build_risk_prompt(base, orderbook, scores)
        thesis_prompt = self._build_thesis_prompt(base, market, contract, scores)
        calibration_prompt = self._build_calibration_prompt(base, scores)

        call_specs = (
            (ModelTask.FORECAST_OPINION, primary_prompt),
            (ModelTask.RAPID_FORECAST, rapid_prompt),
            (ModelTask.NO_TRADE_REASON, no_trade_prompt),
            (ModelTask.STRATEGY_CRITIQUE, critique_prompt),
            (ModelTask.RISK_CRITIQUE, risk_prompt),
            (ModelTask.MARKET_THESIS, thesis_prompt),
            (ModelTask.CALIBRATION_NOTE, calibration_prompt),
        )
        if len(call_specs) > HYBRID_REVIEW_CALL_CAP:
            raise RuntimeError("hybrid review call cap exceeded")
        (
            primary_env,
            rapid_env,
            no_trade_env,
            critique_env,
            risk_env,
            thesis_env,
            calibration_env,
        ) = await asyncio.gather(
            *(
                self.router.call(task, prompt, context=context)
                for task, prompt in call_specs
            )
        )

        return {
            "model_mode": model_mode,
            "primary_forecast": primary_env,
            "rapid_forecast": rapid_env,
            "no_trade": no_trade_env,
            "critique": critique_env,
            "risk": risk_env,
            "thesis": thesis_env,
            "calibration": calibration_env,
        }
