"""Tests for the exact four-model adjudicator (fake router, no network)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from autonomy.debate import DebateResult, run_debate
from autonomy.ontology import MarketView, Vertical

PANEL = (
    "gemini_3_6_flash",
    "gpt_5_6_luna",
    "claude_sonnet_5",
    "glm_5_2",
)


class _Envelope:
    def __init__(self, content, provider="mock", blocked=None):
        self.content = content
        self.blocked_by = blocked

        class _D:
            provider_name = provider

        self.decision = _D()


class FakeRouter:
    """Router double: returns per-provider probabilities, records temperatures."""

    def __init__(self, provider_probs, reals=PANEL):
        self.provider_probs = provider_probs
        self._reals = list(reals)
        self.calls = []
        self.prompts = []

    def available_real_providers(self):
        return list(self._reals)

    def hybrid_provider_names(self):
        return list(self._reals)

    async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
        self.calls.append((provider_override, temperature))
        self.prompts.append((provider_override, prompt))
        prob = self.provider_probs.get(provider_override, 0.5)
        return _Envelope(json.dumps({"dummy_probability": prob, "confidence_score": 0.8, "reasoning": "x"}),
                         provider=provider_override or "mock")


def _market():
    return MarketView(
        ticker="KXTEST-DEBATE", title="Test market", vertical=Vertical.OTHER, status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        yes_bid=40, yes_ask=50, no_bid=50, no_ask=60, volume=100, liquidity=100,
        raw={"rules_primary": "resolves yes if X"},
    )


def test_debate_none_when_no_real_providers():
    router = FakeRouter({}, reals=())
    result = asyncio.run(run_debate(router, _market()))
    assert result is None


def test_debate_aggregates_panel():
    router = FakeRouter(dict(zip(PANEL, (0.7, 0.8, 0.75, 0.65))))
    result = asyncio.run(run_debate(router, _market(), base_prob=0.6))
    assert isinstance(result, DebateResult)
    assert 0.7 <= result.probability_yes <= 0.8
    assert len(result.opinions) == 4
    assert result.complete_hybrid is True


def test_debate_low_disagreement_tight_uncertainty():
    agree = FakeRouter(dict.fromkeys(PANEL, 0.75))
    disagree = FakeRouter(dict(zip(PANEL, (0.2, 0.9, 0.25, 0.85))))
    u_agree = asyncio.run(run_debate(agree, _market())).uncertainty
    u_disagree = asyncio.run(run_debate(disagree, _market())).uncertainty
    assert u_disagree > u_agree


def test_debate_ignores_mock_fallback_votes():
    class MockOnlyRouter(FakeRouter):
        async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
            return _Envelope(json.dumps({"dummy_probability": 0.5, "confidence_score": 0.5}), provider="mock")

    router = MockOnlyRouter(dict.fromkeys(PANEL, 0.7))
    assert asyncio.run(run_debate(router, _market())) is None


def test_debate_requires_exact_four_directed_models():
    invalid_rosters = (
        PANEL[:-1],
        (PANEL[0], PANEL[0], PANEL[2], PANEL[3]),
        PANEL + ("unexpected_model",),
        ("gemini_3_5_flash", "gpt_5_6_terra"),
    )
    for roster in invalid_rosters:
        router = FakeRouter(dict.fromkeys(roster, 0.7), reals=roster)
        assert asyncio.run(run_debate(router, _market())) is None
        assert router.calls == []


def test_debate_accepts_exact_roster_in_any_order():
    reversed_panel = tuple(reversed(PANEL))
    result = asyncio.run(run_debate(
        FakeRouter(dict.fromkeys(PANEL, 0.7), reals=reversed_panel),
        _market(),
        revise=False,
    ))
    assert result is not None
    assert [opinion.provider for opinion in result.opinions] == list(reversed_panel)
    assert result.complete_hybrid is True


def test_debate_rejects_returned_provider_mismatch():
    class MislabeledRouter(FakeRouter):
        async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
            returned_provider = (
                "claude_sonnet_5" if provider_override == "glm_5_2" else provider_override
            )
            return _Envelope(json.dumps({
                "dummy_probability": 0.7,
                "confidence_score": 0.8,
                "reasoning": "x",
            }), provider=returned_provider)

    assert asyncio.run(run_debate(MislabeledRouter({}), _market())) is None


def test_debate_rejects_malformed_voice_and_partial_revision():
    malformed = FakeRouter({**dict.fromkeys(PANEL, 0.7), "glm_5_2": float("nan")})
    assert asyncio.run(run_debate(malformed, _market(), revise=False)) is None

    class PartialRevisionRouter(FakeRouter):
        async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
            if "Other analysts estimated" in prompt and provider_override == "glm_5_2":
                return _Envelope("{}", provider=provider_override)
            return await super().call(
                task, prompt, context, max_tokens, temperature, provider_override,
            )

    assert asyncio.run(run_debate(
        PartialRevisionRouter(dict.fromkeys(PANEL, 0.7)),
        _market(),
        revise=True,
    )) is None


def test_debate_prompts_each_model_with_its_directed_role():
    router = FakeRouter(dict.fromkeys(PANEL, 0.7))
    assert asyncio.run(run_debate(router, _market(), revise=False)) is not None
    prompts = dict(router.prompts)
    assert "supplied-data extraction and rapid probability" in prompts["gemini_3_6_flash"]
    assert "structured forecast and research-only trade-draft" in prompts["gpt_5_6_luna"]
    assert "deep strategy and synthesis reviewer" in prompts["claude_sonnet_5"]
    assert "adversarial risk, calibration, no-trade" in prompts["glm_5_2"]


def test_debate_bounds_model_move_and_exposes_raw_observations():
    router = FakeRouter(dict(zip(PANEL, (0.99, 0.98, 0.97, 0.96))))
    result = asyncio.run(run_debate(router, _market(), base_prob=0.50))
    assert result is not None
    assert result.probability_yes <= 0.65
    observations = result.observation_signals(_market().ticker)
    assert len(observations) == 4
    assert all(s.source.startswith("llm_panel_v3_") for s in observations)
    assert all(s.features["observational_only"] is True for s in observations)
    assert all(s.features["challenger_only"] is True for s in observations)
    assert all(s.probability_yes >= 0.96 for s in observations)


def test_debate_mean_is_not_steered_by_self_reported_confidence():
    class ConfidenceRouter(FakeRouter):
        async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
            probability, confidence = self.provider_probs[provider_override]
            return _Envelope(json.dumps({
                "dummy_probability": probability,
                "confidence_score": confidence,
                "reasoning": "x",
            }), provider=provider_override)

    high_low = asyncio.run(run_debate(ConfidenceRouter({
        "gemini_3_6_flash": (0.70, 1.0),
        "gpt_5_6_luna": (0.50, 0.01),
        "claude_sonnet_5": (0.60, 0.25),
        "glm_5_2": (0.40, 0.75),
    }), _market(), revise=False))
    low_high = asyncio.run(run_debate(ConfidenceRouter({
        "gemini_3_6_flash": (0.70, 0.01),
        "gpt_5_6_luna": (0.50, 1.0),
        "claude_sonnet_5": (0.60, 0.75),
        "glm_5_2": (0.40, 0.25),
    }), _market(), revise=False))
    assert high_low is not None and low_high is not None
    assert high_low.probability_yes == low_high.probability_yes == 0.55
    assert high_low.uncertainty == low_high.uncertainty


def test_peer_revision_does_not_overwrite_or_hide_round_one_disagreement():
    class HerdingRouter(FakeRouter):
        async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
            if "Other analysts estimated" in prompt:
                probability = 0.60
            else:
                probability = {
                    "gemini_3_6_flash": 0.20,
                    "gpt_5_6_luna": 0.90,
                    "claude_sonnet_5": 0.30,
                    "glm_5_2": 0.80,
                }[provider_override]
            return _Envelope(json.dumps({
                "dummy_probability": probability,
                "confidence_score": 1.0,
                "reasoning": "x",
            }), provider=provider_override)

    result = asyncio.run(run_debate(HerdingRouter({}), _market(), revise=True))
    assert result is not None
    assert [o.first_round_probability_yes for o in result.opinions] == [0.20, 0.90, 0.30, 0.80]
    assert [o.revised_probability_yes for o in result.opinions] == [0.60] * 4
    assert result.round1_disagreement >= 0.30
    assert result.uncertainty >= result.round1_disagreement
    signal = result.to_signal(_market().ticker)
    assert signal.features["first_round_probabilities"] == [0.20, 0.90, 0.30, 0.80]
    assert signal.features["revised_probabilities"] == [0.60] * 4


def test_debate_aggregate_is_graded_but_quarantined_until_exact_scope_promotion(tmp_path):
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.learner import Learner
    from autonomy.ledger import AutonomyLedger
    from autonomy.ontology import Signal
    from autonomy.promotion import PromotionRegistry

    market = _market()
    result = asyncio.run(run_debate(
        FakeRouter(dict.fromkeys(PANEL, 0.75)), market, revise=False,
    ))
    assert result is not None
    scope_features = {
        "vertical": "SPORTS", "market_type": "winner", "live": False,
    }
    challenger = result.to_signal(market.ticker, scope_features=scope_features)
    assert challenger.source.startswith("llm_debate_v3_")
    assert challenger.source != "llm_debate"
    assert challenger.features["challenger_only"] is True
    assert challenger.features["promotion_eligible"] is False

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        prior = Signal("market_prior", market.ticker, 0.40, 0.10, "book")
        assert ledger.record_signal(prior) is True
        assert ledger.record_signal(challenger) is True
        updates = Learner(ledger).apply_settlement(market.ticker, True)
        assert challenger.source in updates

        missing = PromotionRegistry(
            tmp_path / "missing-promotions.json", tmp_path / "demotions.json",
        )
        quarantined = EnsembleForecaster(
            ledger, promotion=missing, negative_scopes=frozenset(),
        ).fuse(market, [prior, challenger])
        assert quarantined is not None
        assert challenger.source not in quarantined.sources_used

        promotions = tmp_path / "promotions.json"
        promotions.write_text(json.dumps({"promotions": [{
            "source": challenger.source,
            "subject": "kxtest",
            "market_type": "winner",
            "horizon": "pre",
        }]}), encoding="utf-8")
        promoted = PromotionRegistry(promotions, tmp_path / "demotions.json")
        admitted = EnsembleForecaster(
            ledger, promotion=promoted, negative_scopes=frozenset(),
        ).fuse(market, [prior, challenger])
        assert admitted is not None
        assert challenger.source not in admitted.sources_used
    finally:
        ledger.close()


def test_debate_signal_recorded_and_refused_into_forecast(tmp_path, monkeypatch):
    """Brain path persists gradeable LLM evidence without implicit authority."""
    from autonomy.brain import PredatorBrain
    from autonomy.executor import Executor
    from autonomy.ledger import AutonomyLedger
    from autonomy.learner import Learner
    from autonomy.ontology import SessionMode
    from autonomy.reconciler import Reconciler
    from autonomy.risk_brain import RiskBrain
    from autonomy.scanner import MarketScanner
    from autonomy.signals.base import SourceRegistry
    from autonomy.signals.market_prior import MarketPriorSignal

    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    registry = SourceRegistry()
    registry.register(MarketPriorSignal())

    def fetch_series(series):
        if series != "KXBTC":
            return {"markets": []}
        return {"markets": [{
            "ticker": "KXBTC-26JUL10-T100000", "title": "BTC above 100k", "status": "active",
            "close_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "yes_bid": 40, "yes_ask": 50, "no_bid": 50, "no_ask": 60, "volume": 100, "liquidity": 100,
        }]}

    router = FakeRouter(dict.fromkeys(PANEL, 0.95))
    brain = PredatorBrain(
        mode=SessionMode.SHADOW, ledger=ledger, registry=registry,
        scanner=MarketScanner(fetch_series=fetch_series, watchlist=["KXBTC"]),
        risk_brain=RiskBrain(state_path=tmp_path / "risk.json"),
        executor=Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL"),
        reconciler=Reconciler(ledger, fetch_market_result=lambda t: {"result": ""}),
        learner=Learner(ledger), router=router,
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert any(note.startswith("debate:") for note in report.notes)
        sigs = ledger.calibration_signals_for_market("KXBTC-26JUL10-T100000")
        aggregate = [s for s in sigs if s["source"].startswith("llm_debate_v3_")]
        panels = [s for s in sigs if s["source"].startswith("llm_panel_v3_")]
        assert len(aggregate) == 1
        assert len(panels) == 4
        assert aggregate[0]["features"]["challenger_only"] is True
        assert aggregate[0]["features"]["observational_only"] is True
    finally:
        ledger.close()
