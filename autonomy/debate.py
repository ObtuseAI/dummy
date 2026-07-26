"""Exact four-model LLM adjudicator for shortlisted high-EV markets.

Cheap quantitative sources price the whole board. Gemini 3.6 Flash and GPT-5.6
Luna handle fast structured first-pass work, Claude Sonnet 5 supplies deep
strategy synthesis, and GLM 5.2 independently attacks calibration and
hypotheses. The panel is deliberately deterministic: every directed model must
answer as itself, extra or duplicate configured voices cannot silently vote,
self-reported confidence cannot steer the mean, and each probability move is
bounded around the quantitative forecast. Raw per-model opinions remain
observational signals until settlement evidence earns exact-scope authority.

Async-native (runs inside the brain's event loop). Degrades to None whenever
the router or credentials are absent, so the loop never depends on it.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from autonomy.ontology import MarketView, Signal

MAX_PANELISTS = 5
MIN_DISTINCT_PANELISTS = 4
MAX_MOVE_FROM_QUANT_BASE = 0.15
LLM_PROBATION_UNCERTAINTY_FLOOR = 0.18
DEBATE_SOURCE_VERSION = "llm_debate_v3"
DEBATE_PROMPT_VERSION = "directed_four_model_panel_v3"
DEBATE_RESPONSE_SCHEMA_VERSION = "forecast_opinion_v1"
DEBATE_AGGREGATION_VERSION = "sealed_r1_peer_r2_bounded_mean_v3"

_HYBRID_ROLES = {
    "gemini_3_6_flash": "high-volume supplied-data extraction and rapid probability forecaster",
    "gpt_5_6_luna": "low-latency structured forecast and research-only trade-draft screener",
    "claude_sonnet_5": "deep strategy and synthesis reviewer",
    "glm_5_2": "independent adversarial risk, calibration, no-trade, and hypothesis critic",
}
_HYBRID_PROVIDER_SET = frozenset(_HYBRID_ROLES)


@dataclass
class PanelOpinion:
    panelist: str
    provider: str
    probability_yes: float
    raw_probability_yes: float
    confidence: float
    rationale: str
    # Sealed independent estimate. Peer revision may update the selected
    # fields above, but never overwrites this evidence.
    first_round_probability_yes: float = field(init=False)
    first_round_confidence: float = field(init=False)
    first_round_rationale: str = field(init=False)
    revised_probability_yes: float | None = None
    revised_confidence: float | None = None
    revised_rationale: str | None = None

    def __post_init__(self) -> None:
        self.first_round_probability_yes = self.raw_probability_yes
        self.first_round_confidence = self.confidence
        self.first_round_rationale = self.rationale


@dataclass
class DebateResult:
    probability_yes: float
    uncertainty: float
    opinions: list[PanelOpinion] = field(default_factory=list)
    disagreement: float = 0.0
    round1_disagreement: float = 0.0
    revision_disagreement: float = 0.0
    base_probability: float | None = None
    complete_hybrid: bool = False

    @property
    def source(self) -> str:
        return _debate_source(self.opinions)

    def to_signal(
        self, market_ticker: str, scope_features: dict[str, Any] | None = None,
    ) -> Signal:
        panel = ", ".join(f"{o.provider}={o.probability_yes:.2f}" for o in self.opinions)
        return Signal(
            source=self.source,
            market_ticker=market_ticker,
            probability_yes=self.probability_yes,
            uncertainty=self.uncertainty,
            rationale=f"panel[{len(self.opinions)}] {panel} disagreement={self.disagreement:.2f}",
            features={
                **(scope_features or {}),
                "challenger_only": True,
                "observational_only": True,
                # Generic challenger promotion is intentionally insufficient
                # for model output.  Only the separately verified exact-scope
                # model-authority dossier may ever grant operational weight.
                "promotion_eligible": False,
                "llm_probability_authority": "quarantined_until_exact_scope_promotion",
                "source_version": DEBATE_SOURCE_VERSION,
                "prompt_version": DEBATE_PROMPT_VERSION,
                "response_schema_version": DEBATE_RESPONSE_SCHEMA_VERSION,
                "aggregation_version": DEBATE_AGGREGATION_VERSION,
                "disagreement": self.disagreement,
                "round1_disagreement": self.round1_disagreement,
                "revision_disagreement": self.revision_disagreement,
                "panel_size": len(self.opinions),
                "providers": [o.provider for o in self.opinions],
                "provider_lineage": sorted({o.provider for o in self.opinions}),
                "required_provider_lineage": sorted(_HYBRID_PROVIDER_SET),
                "hybrid_contract": "exact_four_provider_v1",
                "first_round_probabilities": [
                    o.first_round_probability_yes for o in self.opinions
                ],
                "revised_probabilities": [
                    o.revised_probability_yes for o in self.opinions
                ],
                "raw_probabilities": [o.raw_probability_yes for o in self.opinions],
                "anchored_probabilities": [o.probability_yes for o in self.opinions],
                "self_reported_confidences": [o.confidence for o in self.opinions],
                "self_reported_confidence_affects_precision": False,
                "uncertainty_basis": "probation_floor_and_round_disagreement_only",
                "base_probability": self.base_probability,
                "complete_hybrid": self.complete_hybrid,
                "aggregation": "equal_weight_bounded_mean",
            },
        )

    def observation_signals(
        self, market_ticker: str, scope_features: dict[str, Any] | None = None,
    ) -> list[Signal]:
        """Sealed independent opinions for grading; peer revisions stay metadata."""
        signals: list[Signal] = []
        for opinion in self.opinions:
            signals.append(Signal(
                source=_panel_source(opinion.provider),
                market_ticker=market_ticker,
                probability_yes=opinion.first_round_probability_yes,
                uncertainty=max(
                    LLM_PROBATION_UNCERTAINTY_FLOOR,
                    self.round1_disagreement,
                ),
                rationale=opinion.first_round_rationale,
                features={
                    **(scope_features or {}),
                    "observational_only": True,
                    "challenger_only": True,
                    "promotion_eligible": False,
                    "llm_probability_authority": "zero_unless_exact_scope_dossier",
                    "source_version": DEBATE_SOURCE_VERSION,
                    "prompt_version": DEBATE_PROMPT_VERSION,
                    "response_schema_version": DEBATE_RESPONSE_SCHEMA_VERSION,
                    "round": 1,
                    "peer_exposed": False,
                    "provider": opinion.provider,
                    "self_reported_confidence": opinion.first_round_confidence,
                    "self_reported_confidence_affects_precision": False,
                    "revised_probability": opinion.revised_probability_yes,
                    "revised_confidence": opinion.revised_confidence,
                    "anchored_probability": opinion.probability_yes,
                    "base_probability": self.base_probability,
                    "role": _HYBRID_ROLES.get(opinion.provider, "independent forecaster"),
                },
            ))
        return signals


def _debate_source(opinions: list[PanelOpinion]) -> str:
    lineage = "|".join(sorted({o.provider for o in opinions}))
    identity = "|".join((
        DEBATE_SOURCE_VERSION,
        DEBATE_PROMPT_VERSION,
        DEBATE_RESPONSE_SCHEMA_VERSION,
        DEBATE_AGGREGATION_VERSION,
        lineage,
    ))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{DEBATE_SOURCE_VERSION}_{digest}"

def _panel_source(provider: str) -> str:
    identity = "|".join((
        DEBATE_SOURCE_VERSION,
        DEBATE_PROMPT_VERSION,
        DEBATE_RESPONSE_SCHEMA_VERSION,
        provider,
        "sealed_r1",
    ))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    provider_slug = "".join(c if c.isalnum() else "_" for c in provider).strip("_")
    return f"llm_panel_v3_{provider_slug}_{digest}"[:100]

def _is_cli(provider: str) -> bool:
    return provider.endswith("_cli")


def _panel_configs(router: Any, allow_cli: bool = True) -> list[tuple[str, str, float]]:
    """(label, provider_override, temperature) — up to MAX_PANELISTS voices.

    Distinct models first: give each real provider one voice (cycling
    temperatures) before ever reusing a provider, so model diversity — the
    thing that actually makes a debate informative — is maximized.

    ``allow_cli`` controls the local-CLI voices (claude/codex, which bill
    personal subscriptions): when True they move to the FRONT so an armed CLI
    voice is guaranteed a panel slot (otherwise, 7th/8th in provider order, it
    would never make the top-5); when False they are excluded, so a caller can
    keep the frontier voices to a small quota-capped slice of markets.
    """
    hybrid_names = getattr(router, "hybrid_provider_names", None)
    if callable(hybrid_names):
        # A production router with an explicit hybrid never falls through to
        # legacy panel models when the directed roster is incomplete or
        # contaminated by a duplicate/extra provider.
        try:
            names = list(hybrid_names())
            exact_roster = (
                all(isinstance(name, str) for name in names)
                and len(names) == MIN_DISTINCT_PANELISTS
                and set(names) == _HYBRID_PROVIDER_SET
            )
        except (TypeError, ValueError):
            return []
        if not exact_roster:
            return []
        return [
            (f"{provider}:{_HYBRID_ROLES.get(provider, 'reviewer')}", provider, 0.1)
            for provider in names
        ]

    reals = router.available_real_providers()
    cli = [p for p in reals if _is_cli(p)]
    http = [p for p in reals if not _is_cli(p)]
    reals = (cli + http) if allow_cli else http
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
            context: str | None = None, role: str = "independent forecaster") -> str:
    peer_line = ""
    if peers:
        peer_line = f"\nOther analysts estimated: {', '.join(f'{p:.2f}' for p in peers)}. Reconsider and give your own best number."
    base_line = f"\nA quantitative model estimates {base_prob:.2f}." if base_prob is not None else ""
    context_line = f"\n{context}" if context else ""
    return (
        f"Role: {role}.\n"
        f"Market: {market.title}\nTicker: {market.ticker}\n"
        f"Rules: {str(market.raw.get('rules_primary',''))[:1200]}\n"
        f"Book: yes_bid={market.yes_bid} yes_ask={market.yes_ask} volume={market.volume}"
        f"{context_line}{base_line}{peer_line}\n"
        "Use only the supplied rules, book, quantitative estimate, and tape. Do not "
        "invent news, injuries, prices, or statistics. Treat the resolution rules as "
        "primary; lower confidence when required evidence is missing. Estimate the "
        "probability this resolves YES. Return STRICT JSON with keys "
        "dummy_probability (0..1), confidence_score (0..1), reasoning (one line): "
        '{"dummy_probability": <0..1>, "confidence_score": <0..1>, "reasoning": "<one line>"}'
    )


def _parse(content: str) -> tuple[float, float, str] | None:
    # Accept the router's FORECAST_OPINION schema keys (dummy_probability,
    # confidence_score) as well as the plain aliases, so a validated live
    # response is never silently dropped.
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            return None
        raw_p = data.get("dummy_probability", data.get("probability_yes"))
        raw_c = data.get("confidence_score", data.get("confidence", 0.5))
        if isinstance(raw_p, bool) or isinstance(raw_c, bool):
            return None
        p = float(raw_p)
        c = float(raw_c)
    except Exception:
        return None
    reasoning = data.get("reasoning")
    if (
        not math.isfinite(p)
        or not math.isfinite(c)
        or not (0.0 < p < 1.0)
        or not (0.0 <= c <= 1.0)
        or not isinstance(reasoning, str)
        or not reasoning.strip()
    ):
        return None
    return p, c, reasoning.strip()[:200]


def _disagreement(probabilities: list[float]) -> float:
    if not probabilities:
        return 0.0
    mean = sum(probabilities) / len(probabilities)
    return (
        sum((probability - mean) ** 2 for probability in probabilities)
        / len(probabilities)
    ) ** 0.5


async def _ask(router: Any, task: Any, prompt: str, provider: str, temp: float) -> tuple[float, float, str] | None:
    try:
        envelope = await router.call(task, prompt, provider_override=provider, temperature=temp)
    except Exception:
        return None
    if getattr(envelope, "blocked_by", None):
        return None
    # A fallback, mislabeled response, or absent decision identity is not the
    # requested model's vote and invalidates the exact-panel batch.
    returned_provider = getattr(getattr(envelope, "decision", None), "provider_name", None)
    if returned_provider != provider:
        return None
    return _parse(getattr(envelope, "content", ""))


async def run_debate(router: Any, market: MarketView, base_prob: float | None = None,
                     revise: bool = True, context: str | None = None,
                     allow_cli: bool = True) -> DebateResult | None:
    import asyncio

    from model_router.tasks import ModelTask

    configs = _panel_configs(router, allow_cli=allow_cli)
    if not configs:
        return None

    round1 = await asyncio.gather(*[
        _ask(
            router, ModelTask.FORECAST_OPINION,
            _prompt(
                market, base_prob, context=context,
                role=_HYBRID_ROLES.get(provider, "independent forecaster"),
            ),
            provider, temp,
        )
        for _label, provider, temp in configs
    ])
    successful = [(configs[i], r) for i, r in enumerate(round1) if r is not None]
    opinions = [
        PanelOpinion(label, provider, r[0], r[0], r[1], r[2])
        for (label, provider, _temp), r in successful
    ]
    opinion_providers = [opinion.provider for opinion in opinions]
    if (
        len(opinion_providers) != MIN_DISTINCT_PANELISTS
        or set(opinion_providers) != _HYBRID_PROVIDER_SET
    ):
        return None

    round1_disagreement = _disagreement([
        opinion.first_round_probability_yes for opinion in opinions
    ])

    if revise and len(opinions) >= 2:
        peers = [o.probability_yes for o in opinions]
        round2 = await asyncio.gather(*[
            _ask(
                router, ModelTask.FORECAST_OPINION,
                _prompt(
                    market, base_prob, peers, context=context,
                    role=_HYBRID_ROLES.get(provider, "independent forecaster"),
                ),
                provider, temp,
            )
            for (_label, provider, temp), _r in successful
        ])
        if any(revised is None for revised in round2):
            return None
        for index, revised in enumerate(round2):
            assert revised is not None
            opinions[index].revised_probability_yes = revised[0]
            opinions[index].revised_confidence = revised[1]
            opinions[index].revised_rationale = revised[2]
            opinions[index].probability_yes = revised[0]
            opinions[index].raw_probability_yes = revised[0]
            opinions[index].confidence = revised[1]
            opinions[index].rationale = revised[2]

    revision_disagreement = _disagreement([
        opinion.raw_probability_yes for opinion in opinions
    ])

    anchor_distance = 0.0
    if base_prob is not None:
        base_prob = min(0.995, max(0.005, float(base_prob)))
        lower = max(0.005, base_prob - MAX_MOVE_FROM_QUANT_BASE)
        upper = min(0.995, base_prob + MAX_MOVE_FROM_QUANT_BASE)
        for opinion in opinions:
            opinion.probability_yes = min(upper, max(lower, opinion.raw_probability_yes))
        anchor_distance = sum(
            abs(o.raw_probability_yes - o.probability_yes) for o in opinions
        ) / len(opinions)

    # Confidence is a model claim, not empirical residual variance. It is
    # persisted for later grading but has no path into ensemble precision.
    # Peer herding likewise cannot erase sealed round-one disagreement.
    probability = math.fsum(o.probability_yes for o in opinions) / len(opinions)
    disagreement = _disagreement([o.probability_yes for o in opinions])
    uncertainty = min(
        0.5,
        max(
            LLM_PROBATION_UNCERTAINTY_FLOOR,
            disagreement,
            round1_disagreement,
            revision_disagreement,
            0.5 * anchor_distance,
        ),
    )
    return DebateResult(
        probability_yes=min(0.98, max(0.02, probability)),
        uncertainty=uncertainty,
        opinions=opinions,
        disagreement=disagreement,
        round1_disagreement=round1_disagreement,
        revision_disagreement=revision_disagreement,
        base_probability=base_prob,
        complete_hybrid=(
            len(opinion_providers) == MIN_DISTINCT_PANELISTS
            and set(opinion_providers) == _HYBRID_PROVIDER_SET
        ),
    )
