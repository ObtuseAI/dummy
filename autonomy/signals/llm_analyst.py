"""LLM analyst signal: model-router-driven reasoning over market title/rules.

Used sparingly — only for markets short-listed by the cheaper quantitative
sources — and always through the repo's ModelRouter (prompt/output firewalls,
cost tracking). Returns None whenever the router or credentials are absent,
so the loop degrades gracefully to pure-quant mode. Its trust weight, like
every source's, is earned through the calibration ledger.
"""
from __future__ import annotations

import json
from typing import Any

from autonomy.ontology import MarketView, Signal


class LlmAnalystSignal:
    name = "llm_analyst"

    def __init__(self, router: Any | None = None):
        self._router = router
        self._router_failed = False

    def _get_router(self):
        if self._router is not None or self._router_failed:
            return self._router
        try:
            from model_router.router import ModelRouter

            self._router = ModelRouter()
        except Exception:
            self._router_failed = True
        return self._router

    def applicable(self, market: MarketView) -> bool:
        return bool(market.title)

    def generate(self, market: MarketView) -> Signal | None:
        router = self._get_router()
        if router is None:
            return None
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            # Called from inside the brain's event loop: skip rather than
            # nest asyncio.run. The quant sources carry the cycle; a
            # dedicated async analyst worker is the V2 path.
            return None

        from model_router.tasks import ModelTask

        rules = str(market.raw.get("rules_primary", ""))[:1500]
        prompt = (
            f"Market: {market.title}\n"
            f"Ticker: {market.ticker}\n"
            f"Rules excerpt: {rules}\n"
            f"Current book: yes_bid={market.yes_bid} yes_ask={market.yes_ask} volume={market.volume}\n"
            "Estimate the probability the market resolves YES. Think about base rates, "
            "the exact settlement rule, and time remaining. Return STRICT JSON using "
            "the FORECAST_OPINION contract: "
            '{"dummy_probability": <0..1>, "confidence_score": <0..1>, '
            '"reasoning": "<one paragraph>"}'
        )
        try:
            envelope = asyncio.run(
                router.call(ModelTask.FORECAST_OPINION, prompt, context={"market_ticker": market.ticker})
            )
            decision = envelope.decision
            expected_provider = router.config.default_provider.get(
                ModelTask.FORECAST_OPINION.value
            )
            if (
                envelope.blocked_by
                or decision.fallback_reason
                or decision.provider_name != expected_provider
                or decision.provider_name in {"mock", "none"}
            ):
                return None
            data = json.loads(envelope.content)
            p_yes = float(data["dummy_probability"])
            confidence = float(data["confidence_score"])
        except Exception:
            return None
        if not (0.0 < p_yes < 1.0):
            return None
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=min(0.995, max(0.005, p_yes)),
            uncertainty=min(0.5, max(0.05, 0.5 * (1.0 - confidence))),
            rationale=str(data.get("reasoning", ""))[:400],
            features={
                "confidence": confidence,
                "challenger_only": True,
                "observational_only": True,
                "promotion_eligible": False,
                "llm_probability_authority": "zero_unless_exact_scope_dossier",
            },
        )
