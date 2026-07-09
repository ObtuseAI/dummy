"""Learner: the recursive-improvement engine.

Three loops, all evidence-driven:
1. Calibration: on every settlement, score each source's logged signal for
   that market (Brier) and update its trust weight multiplicatively —
   sources that beat the market gain influence, sources that lose it fade.
   (Blunder's recursive_feedback_engine pattern, applied to signals.)
2. Risk: settled P&L per contract feeds the risk brain's stage evidence, so
   position size is always downstream of demonstrated edge.
3. Reflexion: periodically, losing decisions are summarized through the
   model router into short structured "lessons" stored in the ledger and fed
   back into the LLM analyst's context — verbal self-teaching, bounded and
   auditable.
"""
from __future__ import annotations

import json
from typing import Any

from autonomy.ledger import AutonomyLedger

# Multiplicative-weights learning rate. Small: one lucky settlement should
# not crown a source; a season of them should.
ETA = 0.15
WEIGHT_FLOOR = 0.05
WEIGHT_CEILING = 8.0


def brier(probability_yes: float, result_yes: bool) -> float:
    outcome = 1.0 if result_yes else 0.0
    return (probability_yes - outcome) ** 2


class Learner:
    def __init__(self, ledger: AutonomyLedger, router: Any | None = None):
        self.ledger = ledger
        self._router = router

    # ------------------------------------------------------------------
    # Loop 1: calibration -> trust weights
    # ------------------------------------------------------------------

    def apply_settlement(self, market_ticker: str, result_yes: bool) -> dict[str, float]:
        """Score every source that opined on this market; update weights.

        Reference point is the market-prior signal's own Brier: a source is
        rewarded for beating the market, not merely for being right when the
        market was righter.
        """
        signals = self.ledger.signals_for_market(market_ticker)
        if not signals:
            return {}
        from autonomy.scanner import classify_vertical

        vertical = classify_vertical(market_ticker).value
        by_source: dict[str, float] = {}
        for signal in signals:
            # Latest opinion per source wins.
            by_source[signal["source"]] = float(signal["probability_yes"])
        baseline = brier(by_source.get("market_prior", 0.5), result_yes)
        updated: dict[str, float] = {}
        for source, probability in by_source.items():
            score = brier(probability, result_yes)
            advantage = baseline - score  # positive = beat the market
            multiplier = pow(2.718281828, ETA * advantage / 0.25)  # 0.25 = max Brier scale
            old = self.ledger.get_weight(source, default=1.0)
            new = max(WEIGHT_FLOOR, min(WEIGHT_CEILING, old * multiplier))
            self.ledger.update_weight(source, new, brier=score)
            updated[source] = new
            # Vertical-scoped trust learns in parallel: same rule, own row.
            scoped_key = f"{source}@{vertical}"
            scoped_old = self.ledger.get_weight(scoped_key, default=1.0)
            scoped_new = max(WEIGHT_FLOOR, min(WEIGHT_CEILING, scoped_old * multiplier))
            self.ledger.update_weight(scoped_key, scoped_new, brier=score)
        return updated

    # ------------------------------------------------------------------
    # Loop 3: Reflexion lessons
    # ------------------------------------------------------------------

    def reflect(self, recent_losses: list[dict[str, Any]], max_lessons: int = 3) -> list[str]:
        if not recent_losses or self._router is None:
            return []
        import asyncio

        from model_router.tasks import ModelTask

        prompt = (
            "You are the self-critique module of an autonomous prediction-market trader. "
            "Here are recent losing decisions with their forecasts and outcomes:\n"
            + json.dumps(recent_losses[:10], default=str)[:4000]
            + "\nExtract at most "
            + str(max_lessons)
            + ' concrete, testable lessons. Return STRICT JSON: {"lessons": ["...", ...]}'
        )
        try:
            envelope = asyncio.run(self._router.call(ModelTask.MARKET_THESIS, prompt, context={}))
            lessons = json.loads(envelope.content).get("lessons", [])
        except Exception:
            return []
        stored: list[str] = []
        for lesson in lessons[:max_lessons]:
            text = str(lesson).strip()
            if text:
                self.ledger.record_lesson("reflexion", text, {"losses_considered": len(recent_losses)})
                stored.append(text)
        return stored
