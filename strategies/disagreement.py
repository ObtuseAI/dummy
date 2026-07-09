from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
import statistics
from typing import Any
import uuid

from core.ontology import ForecastOpinion
from model_router.router import ModelRouter
from model_router.tasks import ModelTask


class HybridDisagreementEngine:
    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

    async def review(self, task: ModelTask, prompt: str, context: dict | None = None) -> dict:
        primary = await self.router.call(task, prompt, context)
        secondary = await self.router.call(task, prompt, context)
        score = self._agreement(primary.content, secondary.content)
        adjustment = (
            Decimal("0")
            if score > Decimal("0.8")
            else Decimal("-0.15")
            if score > Decimal("0.5")
            else Decimal("-0.3")
        )
        verdict = "agree" if score > Decimal("0.8") else "disagree"
        return {
            "task": task.value,
            "primary": {"provider": primary.decision.provider_name, "content": primary.content},
            "secondary": {"provider": secondary.decision.provider_name, "content": secondary.content},
            "agreement_score": score,
            "confidence_adjustment": adjustment,
            "verdict": verdict,
            "reasoning": f"agreement_score={score}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "proof_reference": str(uuid.uuid4()),
        }

    def _agreement(self, a: str, b: str) -> Decimal:
        return Decimal(str(round(SequenceMatcher(None, a, b).ratio(), 4)))


class HybridDisagreementEngineV2:
    """Detect disagreement among seven forecast/trade decision sources.

    Sources compared:
      1. Market-implied probability (from the orderbook mid)
      2. Dummy statistical/model estimate (``opinion.dummy_probability``)
      3. DeepSeekV4Flash probability (independent model call)
      4. MinimaxM3 critique signal (independent model call)
      5. Strategy signal (caller-provided verdict/confidence)
      6. Risk governor value (caller-provided score/verdict)
      7. Calibration confidence (caller-provided score)

    The engine normalises every source to a [0, 1] probability-like score,
    computes a normalised standard-deviation disagreement score, identifies
    the source that deviates most from the consensus, and maps the score to
    a required action and a no-trade bias adjustment.
    """

    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()

    async def review(
        self,
        opinion: ForecastOpinion,
        strategy_signal: Any,
        risk_governor_value: Any,
        calibration_confidence: Decimal | float | str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}

        # Independent model estimates (mock fallback in tests keeps these deterministic).
        deepseek_response = await self.router.call(
            ModelTask.FORECAST_OPINION, self._build_prompt(opinion), context
        )
        minimax_response = await self.router.call(
            ModelTask.STRATEGY_CRITIQUE, self._build_prompt(opinion), context
        )

        deepseek_data = self._safe_json(deepseek_response.content)
        minimax_data = self._safe_json(minimax_response.content)

        sources: dict[str, Decimal] = {
            "market_implied_probability": self._to_probability(opinion.market_implied_probability),
            "dummy_estimate": self._to_probability(opinion.dummy_probability),
            "deepseek_v4_flash": self._to_probability(
                context.get("deepseek_probability")
                if context.get("deepseek_probability") is not None
                else deepseek_data.get("dummy_probability", opinion.dummy_probability)
            ),
            "minimax_m3": self._to_probability(
                context.get("minimax_probability")
                if context.get("minimax_probability") is not None
                else self._verdict_to_probability(minimax_data.get("verdict", "warn"))
            ),
            "strategy_signal": self._normalize_signal(strategy_signal),
            "risk_governor": self._normalize_risk(risk_governor_value),
            "calibration_confidence": self._to_probability(calibration_confidence),
        }

        score = self._disagreement_score(list(sources.values()))
        source_of_disagreement = self._primary_source_of_disagreement(sources)
        action = self._required_action(score)
        adjustment = self._bias_adjustment(score)

        return {
            "disagreement_score": score,
            "source_of_disagreement": source_of_disagreement,
            "required_action": action,
            "no_trade_bias_adjustment": adjustment,
            "proof_reference": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": {k: str(v) for k, v in sources.items()},
            "deepseek_provider": deepseek_response.decision.provider_name,
            "minimax_provider": minimax_response.decision.provider_name,
            "reasoning": (
                f"score={score}; primary_deviant={source_of_disagreement}; "
                f"action={action}; adjustment={adjustment}"
            ),
        }

    @staticmethod
    def _build_prompt(opinion: ForecastOpinion) -> str:
        return (
            f"Market: {opinion.market_ticker}/{opinion.contract_ticker}\n"
            f"Market-implied probability: {opinion.market_implied_probability}\n"
            f"Dummy probability: {opinion.dummy_probability}\n"
            f"Reasoning: {opinion.reasoning}\n"
            "Provide a concise assessment."
        )

    @staticmethod
    def _safe_json(content: str | None) -> dict[str, Any]:
        if not content:
            return {}
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _to_probability(value: Any, default: Decimal | None = None) -> Decimal:
        if value is None:
            return default if default is not None else Decimal("0.5")
        if isinstance(value, Decimal):
            result = value
        else:
            try:
                result = Decimal(str(value))
            except Exception:
                return default if default is not None else Decimal("0.5")
        if result < Decimal("0"):
            return Decimal("0")
        if result > Decimal("1"):
            return Decimal("1")
        return result.quantize(Decimal("0.0001"))

    @classmethod
    def _verdict_to_probability(cls, verdict: Any) -> Decimal:
        mapping = {
            "proceed": Decimal("0.85"),
            "approve": Decimal("0.85"),
            "agree": Decimal("0.85"),
            "warn": Decimal("0.55"),
            "review": Decimal("0.55"),
            "hold": Decimal("0.50"),
            "block": Decimal("0.20"),
            "reject": Decimal("0.15"),
            "disagree": Decimal("0.20"),
            "no_trade": Decimal("0.10"),
        }
        if verdict is None:
            return Decimal("0.5")
        key = str(verdict).strip().lower()
        return mapping.get(key, Decimal("0.5"))

    @classmethod
    def _risk_level_to_probability(cls, level: Any) -> Decimal:
        mapping = {
            "low": Decimal("0.80"),
            "minor": Decimal("0.75"),
            "medium": Decimal("0.60"),
            "moderate": Decimal("0.55"),
            "high": Decimal("0.35"),
            "critical": Decimal("0.15"),
            "severe": Decimal("0.10"),
        }
        if level is None:
            return Decimal("0.5")
        key = str(level).strip().lower()
        return mapping.get(key, Decimal("0.5"))

    @classmethod
    def _normalize_signal(cls, signal: Any) -> Decimal:
        if signal is None:
            return Decimal("0.5")
        if isinstance(signal, dict):
            if "probability" in signal:
                return cls._to_probability(signal["probability"])
            if "confidence" in signal:
                return cls._to_probability(signal["confidence"])
            if "verdict" in signal:
                return cls._verdict_to_probability(signal["verdict"])
            return Decimal("0.5")
        if isinstance(signal, (int, float, Decimal, str)) and cls._is_numeric(signal):
            return cls._to_probability(signal)
        return cls._verdict_to_probability(signal)

    @classmethod
    def _normalize_risk(cls, value: Any) -> Decimal:
        if value is None:
            return Decimal("0.5")
        if isinstance(value, dict):
            if "value" in value:
                return cls._to_probability(value["value"])
            if "score" in value:
                return cls._to_probability(value["score"])
            if "risk_level" in value:
                return cls._risk_level_to_probability(value["risk_level"])
            if "verdict" in value:
                return cls._verdict_to_probability(value["verdict"])
            return Decimal("0.5")
        if isinstance(value, (int, float, Decimal, str)) and cls._is_numeric(value):
            return cls._to_probability(value)
        return cls._risk_level_to_probability(value)

    @staticmethod
    def _is_numeric(value: Any) -> bool:
        try:
            Decimal(str(value))
            return True
        except Exception:
            return False

    @staticmethod
    def _disagreement_score(values: list[Decimal]) -> Decimal:
        floats = [float(v) for v in values]
        if len(floats) < 2:
            return Decimal("0")
        mean = statistics.mean(floats)
        variance = statistics.pvariance(floats, mu=mean)
        std_dev = variance ** 0.5
        # Normalise to [0, 1]; maximum possible std-dev for [0, 1] values is 0.5.
        score = min(1.0, 2.0 * std_dev)
        return Decimal(str(round(score, 4)))

    @classmethod
    def _primary_source_of_disagreement(cls, sources: dict[str, Decimal]) -> str:
        values = [float(v) for v in sources.values()]
        mean = statistics.mean(values)
        deviations = {name: abs(float(value) - mean) for name, value in sources.items()}
        return max(deviations, key=deviations.get)  # type: ignore[arg-type]

    @staticmethod
    def _required_action(score: Decimal) -> str:
        if score <= Decimal("0.15"):
            return "PROCEED"
        if score <= Decimal("0.30"):
            return "REQUIRE_MORE_EVIDENCE"
        if score <= Decimal("0.45"):
            return "REQUIRE_MINIMAX_REVIEW"
        if score <= Decimal("0.60"):
            return "REQUIRE_OPERATOR_REVIEW"
        return "NO_TRADE"

    @staticmethod
    def _bias_adjustment(score: Decimal) -> Decimal:
        if score <= Decimal("0.15"):
            return Decimal("0")
        if score <= Decimal("0.30"):
            return Decimal("-0.05")
        if score <= Decimal("0.45"):
            return Decimal("-0.10")
        if score <= Decimal("0.60"):
            return Decimal("-0.20")
        return Decimal("-0.35")
