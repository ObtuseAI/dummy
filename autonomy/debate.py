"""Five-model LLM debate adjudicator for shortlisted high-EV markets.

Cheap quantitative sources price the whole board; this panel only adjudicates
the handful of markets the allocator ranks highest. Each panelist (a distinct
provider, or the same provider at a distinct temperature, to reach ~5 voices)
estimates a probability with a confidence and a one-line rationale. A second
revision round shows each panelist the spread so it can update — that is the
"debate". The fused result is injected as one more trust-weighted signal, so
the learner grades the panel exactly like any other source.

Async-native (runs inside the brain's event loop). Degrades to None whenever
the router or credentials are absent, so the loop never depends on it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from autonomy.ontology import MarketView, Signal

MAX_PANELISTS = 5


@dataclass
class PanelOpinion:
    panelist: str
    probability_yes: float
    confidence: float
    rationale: str


@dataclass
class DebateResult:
    probability_yes: float
    uncertainty: float
    opinions: list[PanelOpinion] = field(default_factory=list)
    disagreement: float = 0.0

    def to_signal(self, market_ticker: str) -> Signal:
        panel = ", ".join(f"{o.panelist}={o.probability_yes:.2f}" for o in self.opinions)
        return Signal(
            source="llm_debate",
            market_ticker=market_ticker,
            probability_yes=self.probability_yes,
            uncertainty=self.uncertainty,
            rationale=f"panel[{len(self.opinions)}] {panel} disagreement={self.disagreement:.2f}",
            features={"disagreement": self.disagreement, "panel_size": len(self.opinions)},
        )


def _panel_configs(router: Any) -> list[tuple[str, str, float]]:
    """(label, provider_override, temperature) — up to MAX_PANELISTS voices.

    Distinct models first: give each real provider one voice (cycling
    temperatures) before ever reusing a provider, so model diversity — the
    thing that actually makes a debate informative — is maximized.
    """
    reals = router.available_real_providers()
    if not reals:
        return []
    temps = [0.2, 0.5, 0.8]
    configs: list[tuple[str, str, float]] = []
    # Pass 1: one voice per distinct model.
    for i, provider in enumerate(reals):
        configs.append((f"{provider}@{temps[i % len(temps)]}", provider, temps[i % len(temps)]))
        if len(configs) >= MAX_PANELISTS:
            return configs
    # Pass 2: only if we still have room, add temperature-varied extra voices.
    round_idx = 1
    while len(configs) < MAX_PANELISTS:
        added = False
        for provider in reals:
            temp = temps[round_idx % len(temps)]
            configs.append((f"{provider}@{temp}#{round_idx}", provider, temp))
            added = True
            if len(configs) >= MAX_PANELISTS:
                break
        round_idx += 1
        if not added:
            break
    return configs


def _prompt(market: MarketView, base_prob: float | None, peers: list[float] | None = None,
            context: str | None = None) -> str:
    peer_line = ""
    if peers:
        peer_line = f"\nOther analysts estimated: {', '.join(f'{p:.2f}' for p in peers)}. Reconsider and give your own best number."
    base_line = f"\nA quantitative model estimates {base_prob:.2f}." if base_prob is not None else ""
    context_line = f"\n{context}" if context else ""
    return (
        f"Market: {market.title}\nTicker: {market.ticker}\n"
        f"Rules: {str(market.raw.get('rules_primary',''))[:1200]}\n"
        f"Book: yes_bid={market.yes_bid} yes_ask={market.yes_ask} volume={market.volume}"
        f"{context_line}{base_line}{peer_line}\n"
        "Estimate the probability this resolves YES. Return STRICT JSON with keys "
        "dummy_probability (0..1), confidence_score (0..1), reasoning (one line): "
        '{"dummy_probability": <0..1>, "confidence_score": <0..1>, "reasoning": "<one line>"}'
    )


def _parse(content: str) -> tuple[float, float, str] | None:
    # Accept the router's FORECAST_OPINION schema keys (dummy_probability,
    # confidence_score) as well as the plain aliases, so a validated live
    # response is never silently dropped.
    try:
        data = json.loads(content)
        raw_p = data.get("dummy_probability", data.get("probability_yes"))
        raw_c = data.get("confidence_score", data.get("confidence", 0.5))
        p = float(raw_p)
        c = float(raw_c)
    except Exception:
        return None
    if not (0.0 < p < 1.0):
        return None
    return p, max(0.0, min(1.0, c)), str(data.get("reasoning", ""))[:200]


async def _ask(router: Any, task: Any, prompt: str, provider: str, temp: float) -> tuple[float, float, str] | None:
    try:
        envelope = await router.call(task, prompt, provider_override=provider, temperature=temp)
    except Exception:
        return None
    if getattr(envelope, "blocked_by", None):
        return None
    # A mock fallback (no real model answered) is not a real vote.
    if envelope.decision.provider_name == "mock":
        return None
    return _parse(envelope.content)


async def run_debate(router: Any, market: MarketView, base_prob: float | None = None,
                     revise: bool = True, context: str | None = None) -> DebateResult | None:
    import asyncio

    from model_router.tasks import ModelTask

    configs = _panel_configs(router)
    if not configs:
        return None

    round1 = await asyncio.gather(*[
        _ask(router, ModelTask.FORECAST_OPINION, _prompt(market, base_prob, context=context), provider, temp)
        for _label, provider, temp in configs
    ])
    opinions = [
        PanelOpinion(configs[i][0], r[0], r[1], r[2]) for i, r in enumerate(round1) if r is not None
    ]
    if not opinions:
        return None

    if revise and len(opinions) >= 2:
        peers = [o.probability_yes for o in opinions]
        round2 = await asyncio.gather(*[
            _ask(router, ModelTask.FORECAST_OPINION, _prompt(market, base_prob, peers, context=context),
                 provider, temp)
            for _label, provider, temp in configs[:len(opinions)]
        ])
        revised = [
            PanelOpinion(opinions[i].panelist, r[0], r[1], r[2])
            for i, r in enumerate(round2) if r is not None
        ]
        if revised:
            opinions = revised

    total_w = sum(o.confidence for o in opinions) or float(len(opinions))
    weights = [(o.confidence or 1.0) for o in opinions]
    probability = sum(o.probability_yes * w for o, w in zip(opinions, weights)) / sum(weights)
    mean = sum(o.probability_yes for o in opinions) / len(opinions)
    disagreement = (sum((o.probability_yes - mean) ** 2 for o in opinions) / len(opinions)) ** 0.5
    # Wider uncertainty when the panel disagrees or is small.
    size_penalty = 0.10 if len(opinions) < 3 else 0.03
    uncertainty = min(0.5, max(0.03, disagreement + size_penalty))
    return DebateResult(
        probability_yes=min(0.98, max(0.02, probability)),
        uncertainty=uncertainty,
        opinions=opinions,
        disagreement=disagreement,
    )
