"""The enforced daily USD ceiling for paid model calls.

``CostTracker`` observes spend; ``LlmSpendGovernor`` stops it.  These tests
pin the enforcement contract: under the cap a paid call proceeds, at or over it
the call is refused fail-closed with a reason on the envelope, the counter
rolls at UTC midnight, it survives the process-per-cycle brain, and free
voices (mock, subscription-billed CLIs) never consume a cent of it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from model_router.config import ModelRoutingConfig, ProviderConfig
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision
from model_router.cost_tracker import CostTracker
from model_router.router import ModelRouter
from model_router.spend_governor import (
    DAILY_CAP_ENV,
    DEFAULT_DAILY_USD_CAP,
    DEFAULT_STATE_PATH,
    REASON_CAP_DISABLED,
    REASON_CAP_REACHED,
    REASON_ESTIMATE_INVALID,
    REASON_STATE_UNREADABLE,
    REASON_STATE_UNWRITABLE,
    STATE_PATH_ENV,
    LlmSpendGovernor,
    estimate_call_cost_usd,
    is_metered_route,
)
from model_router.tasks import ModelTask


# 2026-07-24T12:00:00Z and 2026-07-25T00:00:01Z.
DAY_ONE = 1784894400.0
DAY_TWO = 1784937601.0


def _governor(tmp_path: Path, cap: float = 1.0, now: float = DAY_ONE) -> LlmSpendGovernor:
    return LlmSpendGovernor(
        daily_usd_cap=cap,
        state_path=tmp_path / "llm_spend_budget.json",
        now_fn=lambda: now,
    )


def _paid_config(**overrides) -> ProviderConfig:
    base = {
        "api_base": "https://openrouter.ai/api",
        "api_key_env": "OPENROUTER_API_KEY",
        "model_name": "vendor/model",
        "prompt_cost_per_million": 2.0,
        "completion_cost_per_million": 10.0,
        "max_retries": 0,
    }
    base.update(overrides)
    return ProviderConfig(**base)


class TestReservationUnderCap:
    def test_under_cap_allows_and_records_the_reservation(self, tmp_path):
        governor = _governor(tmp_path, cap=1.0)

        decision = governor.reserve(0.25)

        assert decision.allowed is True
        assert decision.reason is None
        assert decision.reserved_usd == 0.25
        assert decision.spent_usd == 0.25
        assert decision.remaining_usd == 0.75
        assert governor.status()["spent_usd"] == 0.25
        assert governor.status()["calls"] == 1

    def test_reservation_landing_exactly_on_the_cap_is_allowed(self, tmp_path):
        governor = _governor(tmp_path, cap=1.0)
        assert governor.reserve(0.6).allowed is True

        decision = governor.reserve(0.4)

        assert decision.allowed is True
        assert decision.spent_usd == 1.0
        assert decision.remaining_usd == 0.0


class TestRefusalAtOrOverCap:
    def test_call_that_would_cross_the_cap_is_refused(self, tmp_path):
        governor = _governor(tmp_path, cap=1.0)
        governor.reserve(0.9)

        decision = governor.reserve(0.2)

        assert decision.allowed is False
        assert decision.reason == REASON_CAP_REACHED
        assert decision.reserved_usd == 0.0
        # A refusal must not move the ledger.
        assert governor.status()["spent_usd"] == 0.9

    def test_exhausted_day_refuses_every_further_call(self, tmp_path):
        governor = _governor(tmp_path, cap=0.5)
        assert governor.reserve(0.5).allowed is True

        for _ in range(3):
            decision = governor.reserve(0.000001)
            assert decision.allowed is False
            assert decision.reason == REASON_CAP_REACHED
        assert governor.status()["spent_usd"] == 0.5

    def test_zero_cap_closes_the_door_entirely(self, tmp_path):
        governor = _governor(tmp_path, cap=0.0)

        decision = governor.reserve(0.0)

        assert decision.allowed is False
        assert decision.reason == REASON_CAP_DISABLED

    @pytest.mark.parametrize("cap", [-1.0, float("nan"), float("inf")])
    def test_nonsense_cap_fails_closed_rather_than_open(self, tmp_path, cap):
        governor = _governor(tmp_path, cap=cap)

        assert governor.daily_usd_cap == 0.0
        assert governor.reserve(0.01).allowed is False

    @pytest.mark.parametrize("estimate", [float("nan"), float("inf"), -0.01, "free"])
    def test_nonsense_estimate_is_refused(self, tmp_path, estimate):
        governor = _governor(tmp_path, cap=10.0)

        decision = governor.reserve(estimate)

        assert decision.allowed is False
        assert decision.reason == REASON_ESTIMATE_INVALID


class TestLedgerIntegrityFailsClosed:
    def test_corrupt_ledger_refuses_instead_of_restarting_the_count(self, tmp_path):
        governor = _governor(tmp_path, cap=1.0)
        governor.reserve(0.1)
        (tmp_path / "llm_spend_budget.json").write_text("{not json", encoding="utf-8")

        decision = governor.reserve(0.1)

        assert decision.allowed is False
        assert decision.reason == REASON_STATE_UNREADABLE
        assert governor.status()["spent_usd"] is None
        assert governor.status()["remaining_usd"] == 0.0

    @pytest.mark.parametrize("payload", ["[]", '{"day": "2026-07-24", "spent_usd": -5}',
                                         '{"day": "2026-07-24", "spent_usd": "lots"}'])
    def test_semantically_invalid_ledger_refuses(self, tmp_path, payload):
        governor = _governor(tmp_path, cap=1.0)
        (tmp_path / "llm_spend_budget.json").write_text(payload, encoding="utf-8")

        decision = governor.reserve(0.01)

        assert decision.allowed is False
        assert decision.reason == REASON_STATE_UNREADABLE

    def test_unwritable_ledger_refuses_the_call(self, tmp_path, monkeypatch):
        governor = _governor(tmp_path, cap=1.0)
        monkeypatch.setattr(
            LlmSpendGovernor, "_save", lambda self, state: False)

        decision = governor.reserve(0.01)

        assert decision.allowed is False
        assert decision.reason == REASON_STATE_UNWRITABLE


class TestUtcDayRollover:
    def test_counter_rolls_over_at_utc_midnight(self, tmp_path):
        clock = {"now": DAY_ONE}
        governor = LlmSpendGovernor(
            daily_usd_cap=1.0,
            state_path=tmp_path / "llm_spend_budget.json",
            now_fn=lambda: clock["now"],
        )
        assert governor.reserve(1.0).allowed is True
        assert governor.reserve(0.01).allowed is False

        clock["now"] = DAY_TWO

        decision = governor.reserve(0.6)
        assert decision.allowed is True
        assert decision.day == "2026-07-25"
        assert decision.spent_usd == 0.6

    def test_rollover_does_not_resurrect_yesterdays_spend(self, tmp_path):
        path = tmp_path / "llm_spend_budget.json"
        path.write_text(
            json.dumps({"day": "2026-07-23", "spent_usd": 9.99, "calls": 40}),
            encoding="utf-8")
        governor = _governor(tmp_path, cap=1.0)

        assert governor.status()["day"] == "2026-07-24"
        assert governor.status()["spent_usd"] == 0.0


class TestPersistenceAcrossProcessRestarts:
    def test_a_fresh_governor_inherits_the_days_spend(self, tmp_path):
        first = _governor(tmp_path, cap=1.0)
        first.reserve(0.7)

        # New process, new object, same UTC day: the ledger is the only memory.
        second = _governor(tmp_path, cap=1.0)

        assert second.status()["spent_usd"] == 0.7
        assert second.reserve(0.5).allowed is False
        assert second.reserve(0.3).allowed is True

    def test_a_fresh_router_per_cycle_still_sees_the_exhausted_day(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(STATE_PATH_ENV, str(tmp_path / "llm_spend_budget.json"))
        monkeypatch.setenv(DAILY_CAP_ENV, "0.10")
        # ModelRouter builds its own governor on the real clock, so the ledger
        # seeded here must be written on the real clock too.  Freezing only the
        # seeding side made this pass exactly while real UTC was DAY_ONE and
        # fail every run after 2026-07-24: the router read a different day key,
        # took the rollover branch, and started the day clean.
        LlmSpendGovernor(
            daily_usd_cap=0.10,
            state_path=tmp_path / "llm_spend_budget.json",
        ).reserve(0.10)

        # Every cycle constructs its own router; the cap must still bind.
        for _ in range(3):
            router = ModelRouter()
            assert router.spend_governor.reserve(0.01).allowed is False
            assert router.spend_status()["remaining_usd"] == 0.0


class TestSettlement:
    def test_reported_cost_below_the_estimate_releases_the_difference(self, tmp_path):
        governor = _governor(tmp_path, cap=1.0)
        decision = governor.reserve(0.20)

        governor.settle(decision, 0.05)

        assert governor.status()["spent_usd"] == 0.05

    def test_reported_cost_above_the_estimate_is_charged_in_full(self, tmp_path):
        governor = _governor(tmp_path, cap=1.0)
        decision = governor.reserve(0.20)

        governor.settle(decision, 0.50)

        assert governor.status()["spent_usd"] == 0.50

    @pytest.mark.parametrize("reported", [None, "unknown", float("nan"), -1.0])
    def test_unreported_cost_leaves_the_estimate_standing(self, tmp_path, reported):
        governor = _governor(tmp_path, cap=1.0)
        decision = governor.reserve(0.20)

        governor.settle(decision, reported)

        assert governor.status()["spent_usd"] == 0.20

    def test_a_refused_reservation_never_moves_the_ledger(self, tmp_path):
        governor = _governor(tmp_path, cap=0.10)
        refused = governor.reserve(1.0)

        governor.settle(refused, 1.0)

        assert governor.status()["spent_usd"] == 0.0


class TestEstimator:
    def test_estimate_uses_the_routes_configured_list_prices(self):
        # 400 prompt chars -> 100 tokens @ $2/M, 512 completion tokens @ $10/M.
        estimate = estimate_call_cost_usd(_paid_config(), "x" * 400, 512)

        assert estimate == pytest.approx((100 * 2.0 + 512 * 10.0) / 1_000_000)

    def test_unpriced_route_falls_back_to_a_pessimistic_price(self):
        unpriced = _paid_config(
            prompt_cost_per_million=None, completion_cost_per_million=None)

        assert estimate_call_cost_usd(unpriced, "x" * 400, 512) > 0.0

    def test_estimate_is_never_negative(self):
        assert estimate_call_cost_usd(None, "", 0) == 0.0


class TestMeteredRouteClassification:
    def test_mock_and_none_are_free(self):
        assert is_metered_route("mock", None) is False
        assert is_metered_route("none", None) is False
        assert is_metered_route("", None) is False

    def test_cli_voices_bill_a_subscription_not_this_budget(self):
        cli = ProviderConfig(api_base="", api_key_env="", model_name="claude-sonnet-5")

        assert is_metered_route("claude_cli", cli) is False

    def test_http_route_is_metered(self):
        assert is_metered_route("claude_sonnet_5", _paid_config()) is True

    def test_unknown_route_without_config_is_assumed_to_bill(self):
        assert is_metered_route("mystery_model", None) is True


def _live_router(tmp_path, monkeypatch, cap: str = "1.00", *,
                 mock_fallback: bool = True) -> ModelRouter:
    """A router whose live gate is OPEN and whose provider is a paid stub."""
    monkeypatch.setenv(STATE_PATH_ENV, str(tmp_path / "llm_spend_budget.json"))
    monkeypatch.setenv(DAILY_CAP_ENV, cap)
    router = ModelRouter()
    router.config = ModelRoutingConfig(
        default_provider={ModelTask.FORECAST_OPINION.value: "paid_voice"},
        provider_configs={"paid_voice": _paid_config()},
        mock_fallback_enabled=mock_fallback,
        live_model_calls_enabled=True,
    )
    router.spend_governor = LlmSpendGovernor(
        state_path=tmp_path / "llm_spend_budget.json")
    return router


class _StubPaidProvider:
    """Stands in for an OpenRouter voice; records whether it was contacted."""

    available = True

    def __init__(self, cost_usd: float | None = 0.004):
        self.calls = 0
        self.cost_usd = cost_usd

    async def complete(self, prompt, task, max_tokens=512, temperature=0.2, **kwargs):
        self.calls += 1
        return (
            json.dumps({"thesis": "stub", "confidence": "0.60"}),
            {"provider": "paid_voice", "model": "vendor/model",
             "cost_usd": self.cost_usd, "error_class": None},
        )


class TestRouterEnforcement:
    @pytest.mark.asyncio
    async def test_under_cap_the_paid_provider_is_contacted(self, tmp_path, monkeypatch):
        router = _live_router(tmp_path, monkeypatch, cap="1.00")
        provider = _StubPaidProvider()
        router.providers["paid_voice"] = provider

        envelope = await router.call(ModelTask.FORECAST_OPINION, "estimate this")

        assert provider.calls == 1
        assert envelope.decision.provider_name == "paid_voice"
        assert envelope.decision.fallback_reason is None
        assert envelope.blocked_by is None
        # The reservation settled against the provider's reported cost.
        assert router.spend_status()["spent_usd"] == pytest.approx(0.004)

    @pytest.mark.asyncio
    async def test_over_cap_the_paid_provider_is_never_contacted(
        self, tmp_path, monkeypatch
    ):
        router = _live_router(tmp_path, monkeypatch, cap="0.001")
        provider = _StubPaidProvider()
        router.providers["paid_voice"] = provider
        router.spend_governor.reserve(0.001)

        envelope = await router.call(ModelTask.FORECAST_OPINION, "estimate this")

        assert provider.calls == 0, "a capped call must not reach the network"
        assert envelope.decision.provider_name == "mock"
        assert envelope.decision.fallback_reason == REASON_CAP_REACHED
        assert envelope.raw_metadata["spend_cap"]["allowed"] is False
        assert envelope.raw_metadata["spend_cap"]["reason"] == REASON_CAP_REACHED
        assert router.cost_tracker.summary()["spend_capped_calls"] == 1

    @pytest.mark.asyncio
    async def test_refusal_is_hard_when_there_is_no_mock_voice_to_degrade_to(
        self, tmp_path, monkeypatch
    ):
        router = _live_router(tmp_path, monkeypatch, cap="0.001", mock_fallback=False)
        provider = _StubPaidProvider()
        router.providers["paid_voice"] = provider
        router.spend_governor.reserve(0.001)

        envelope = await router.call(ModelTask.FORECAST_OPINION, "estimate this")

        assert provider.calls == 0
        assert envelope.blocked_by == REASON_CAP_REACHED
        assert envelope.decision.provider_name == "none"
        assert envelope.content == ""

    @pytest.mark.asyncio
    async def test_the_cap_binds_across_simulated_process_restarts(
        self, tmp_path, monkeypatch
    ):
        contacted = 0
        # Estimate per call: 4 prompt tokens @ $2/M + 8 completion @ $10/M.
        for _ in range(6):
            router = _live_router(tmp_path, monkeypatch, cap="0.0002")
            provider = _StubPaidProvider(cost_usd=None)
            router.providers["paid_voice"] = provider
            await router.call(ModelTask.FORECAST_OPINION, "abcd", max_tokens=8)
            contacted += provider.calls

        assert 0 < contacted < 6, "the ceiling must bind partway through the day"
        # What is left of the day can no longer buy another call.
        remaining = router.spend_status()["remaining_usd"]
        assert remaining < estimate_call_cost_usd(_paid_config(), "abcd", 8)

    @pytest.mark.asyncio
    async def test_failed_paid_call_keeps_its_reservation(self, tmp_path, monkeypatch):
        class _FailingProvider(_StubPaidProvider):
            async def complete(self, *args, **kwargs):
                self.calls += 1
                raise RuntimeError("provider exploded")

        router = _live_router(tmp_path, monkeypatch, cap="1.00")
        router.providers["paid_voice"] = _FailingProvider()

        envelope = await router.call(
            ModelTask.FORECAST_OPINION, "estimate this market " * 20)

        assert envelope.decision.fallback_reason == "paid_voice_request_failed"
        # A request that left the process may still have been billed.
        assert router.spend_status()["spent_usd"] > 0.0


class TestFreeVoicesDoNotConsumeBudget:
    @pytest.mark.asyncio
    async def test_mock_only_router_never_touches_the_ledger(self, tmp_path, monkeypatch):
        ledger = tmp_path / "llm_spend_budget.json"
        monkeypatch.setenv(STATE_PATH_ENV, str(ledger))
        monkeypatch.setenv(DAILY_CAP_ENV, "0.01")
        router = ModelRouter()

        for task in ModelTask:
            envelope = await router.call(task, f"prompt for {task.value}")
            assert envelope.decision.provider_name == "mock"

        assert not ledger.exists(), "free voices must not write a spend ledger"
        assert router.spend_status()["spent_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_closed_live_gate_spends_nothing_even_on_a_paid_route(
        self, tmp_path, monkeypatch
    ):
        router = _live_router(tmp_path, monkeypatch, cap="1.00")
        router.config = router.config.model_copy(
            update={"live_model_calls_enabled": False})
        provider = _StubPaidProvider()
        router.providers["paid_voice"] = provider

        envelope = await router.call(ModelTask.FORECAST_OPINION, "estimate this")

        assert provider.calls == 0
        assert envelope.decision.fallback_reason == "live_calls_disabled"
        assert router.spend_status()["spent_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_subscription_billed_cli_voice_does_not_consume_budget(
        self, tmp_path, monkeypatch
    ):
        router = _live_router(tmp_path, monkeypatch, cap="1.00")
        router.config = router.config.model_copy(update={
            "default_provider": {ModelTask.FORECAST_OPINION.value: "claude_cli"},
            "provider_configs": {"claude_cli": ProviderConfig(
                api_base="", api_key_env="", model_name="claude-sonnet-5")},
        })
        provider = _StubPaidProvider(cost_usd=None)
        router.providers["claude_cli"] = provider

        envelope = await router.call(ModelTask.FORECAST_OPINION, "estimate this")

        assert provider.calls == 1
        assert envelope.decision.provider_name == "claude_cli"
        assert router.spend_status()["spent_usd"] == 0.0


class TestDefaultsAndEnvOverride:
    def test_default_cap_applies_when_no_env_override(self, tmp_path, monkeypatch):
        monkeypatch.delenv(DAILY_CAP_ENV, raising=False)

        governor = LlmSpendGovernor(state_path=tmp_path / "ledger.json")

        assert governor.daily_usd_cap == DEFAULT_DAILY_USD_CAP

    def test_env_override_sets_the_cap(self, tmp_path, monkeypatch):
        monkeypatch.setenv(DAILY_CAP_ENV, "0.25")

        governor = LlmSpendGovernor(state_path=tmp_path / "ledger.json")

        assert governor.daily_usd_cap == 0.25

    @pytest.mark.parametrize("raw", ["", "free", "-1", "nan", "inf"])
    def test_garbage_env_override_falls_back_to_the_default(
        self, tmp_path, monkeypatch, raw
    ):
        monkeypatch.setenv(DAILY_CAP_ENV, raw)

        governor = LlmSpendGovernor(state_path=tmp_path / "ledger.json")

        assert governor.daily_usd_cap == DEFAULT_DAILY_USD_CAP

    def test_suite_runs_never_charge_the_live_ledger(self, tmp_path):
        """Isolation is the HARNESS's job, not the production module's.

        ``tests/conftest.py`` points ``DUMMY_LLM_SPEND_STATE_PATH`` at tmp for
        every test, so a governor built with no explicit path still cannot
        charge the operator's real daily ledger.  This replaced a
        ``PYTEST_CURRENT_TEST`` branch inside ``spend_governor`` itself -- i.e.
        production code that behaved differently under test.
        """
        governor = LlmSpendGovernor(daily_usd_cap=1.0)

        assert governor.state_path != DEFAULT_STATE_PATH
        assert governor.state_path == (
            tmp_path / "runtime" / "autonomy" / "llm_spend_budget.json"
        )
        governor.reserve(0.01)
        assert governor.state_path.exists()
        assert json.loads(
            governor.state_path.read_text(encoding="utf-8")
        )["spent_usd"] == 0.01

    def test_production_module_has_no_test_awareness(self):
        """The governor must never branch on pytest being the caller."""
        import model_router.spend_governor as spend_governor

        source = Path(spend_governor.__file__).read_text(encoding="utf-8")

        assert "PYTEST_CURRENT_TEST" not in source

    def test_state_path_env_override_is_honored(self, tmp_path, monkeypatch):
        target = tmp_path / "nested" / "spend.json"
        monkeypatch.setenv(STATE_PATH_ENV, str(target))

        governor = LlmSpendGovernor(daily_usd_cap=1.0)
        governor.reserve(0.01)

        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8"))["spent_usd"] == 0.01


class TestCostTrackerCountsRefusals:
    def _capped_envelope(self, reason: str) -> ModelResponseEnvelope:
        return ModelResponseEnvelope(
            task=ModelTask.FORECAST_OPINION,
            decision=ModelRouteDecision(
                task=ModelTask.FORECAST_OPINION,
                provider_name="mock",
                model_name="mock",
                reason="daily spend cap",
                fallback_reason=reason,
            ),
            prompt="p",
            content="c",
            raw_metadata={"cost_usd": 0.0},
            latency_ms=1.0,
        )

    def test_spend_capped_calls_are_counted_separately(self):
        tracker = CostTracker()

        tracker.record(self._capped_envelope(REASON_CAP_REACHED))
        tracker.record(self._capped_envelope(REASON_STATE_UNREADABLE))

        summary = tracker.summary()
        assert summary["spend_capped_calls"] == 2
        assert summary["gate_blocked_calls"] == 0
        assert summary["total_cost_usd"] == 0.0
