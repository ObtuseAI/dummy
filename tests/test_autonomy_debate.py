"""Tests for the five-model LLM debate adjudicator (fake router, no network)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from autonomy.debate import DebateResult, run_debate
from autonomy.ontology import MarketView, Vertical


class _Envelope:
    def __init__(self, content, provider="deepseek_v4_flash", blocked=None):
        self.content = content
        self.blocked_by = blocked

        class _D:
            provider_name = provider

        self.decision = _D()


class FakeRouter:
    """Router double: returns per-provider probabilities, records temperatures."""

    def __init__(self, provider_probs, reals=("deepseek_v4_flash", "minimax_m3")):
        self.provider_probs = provider_probs
        self._reals = list(reals)
        self.calls = []

    def available_real_providers(self):
        return list(self._reals)

    async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
        self.calls.append((provider_override, temperature))
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
    router = FakeRouter({"deepseek_v4_flash": 0.7, "minimax_m3": 0.8})
    result = asyncio.run(run_debate(router, _market(), base_prob=0.6))
    assert isinstance(result, DebateResult)
    assert 0.7 <= result.probability_yes <= 0.8
    assert len(result.opinions) >= 2


def test_debate_low_disagreement_tight_uncertainty():
    agree = FakeRouter({"deepseek_v4_flash": 0.75, "minimax_m3": 0.75})
    disagree = FakeRouter({"deepseek_v4_flash": 0.2, "minimax_m3": 0.9})
    u_agree = asyncio.run(run_debate(agree, _market())).uncertainty
    u_disagree = asyncio.run(run_debate(disagree, _market())).uncertainty
    assert u_disagree > u_agree


def test_debate_ignores_mock_fallback_votes():
    class MockOnlyRouter(FakeRouter):
        async def call(self, task, prompt, context=None, max_tokens=512, temperature=0.2, provider_override=None):
            return _Envelope(json.dumps({"dummy_probability": 0.5, "confidence_score": 0.5}), provider="mock")

    router = MockOnlyRouter({"deepseek_v4_flash": 0.7})
    assert asyncio.run(run_debate(router, _market())) is None


def test_debate_signal_recorded_and_refused_into_forecast(tmp_path, monkeypatch):
    """Brain adjudication path: debate signal re-fuses the top market."""
    from autonomy.brain import PredatorBrain
    from autonomy.executor import Executor
    from autonomy.forecaster import EnsembleForecaster
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

    router = FakeRouter({"deepseek_v4_flash": 0.95, "minimax_m3": 0.95})
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
        sigs = ledger.signals_for_market("KXBTC-26JUL10-T100000")
        assert any(s["source"] == "llm_debate" for s in sigs)
    finally:
        ledger.close()
