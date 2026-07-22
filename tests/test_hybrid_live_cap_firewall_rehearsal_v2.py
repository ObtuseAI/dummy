"""Tests for V2 hybrid live-capped firewall rehearsal with strategy governor."""

import os
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from core import state as state_module
from core.config_loader import load_caps
from core.ontology import (
    AccountMode,
    ComplianceVerdict,
    EdgeEstimate,
    FirewallVerdict,
    LiveOrderResult,
    TradeProposal,
)
from execution.hybrid_path import HybridLiveCapRehearsalV2
from forecasting.model_probability_authority import ModelProbabilityAuthorityDecision
from live_firewall.firewall import LiveBrokerFirewall


@pytest.fixture(autouse=True)
def reset_state():
    fresh = state_module.DummyState()
    state_module.STATE = fresh
    import live_firewall.firewall as firewall_module

    firewall_module.STATE = fresh
    # Keep a dummy Kalshi API key ID so the live firewall secrets check passes,
    # but remove any PEM material so KalshiRealReadOnly raises CredentialsMissing
    # and falls back to deterministic mock market data.
    original_key = os.environ.get("KALSHI_API_KEY_ID")
    original_pem = os.environ.pop("KALSHI_API_PRIVATE_KEY_PEM", None)
    original_pem_path = os.environ.pop("KALSHI_API_PRIVATE_KEY_PEM_PATH", None)
    original_legacy_pem = os.environ.pop("KALSHI_API_PRIVATE_KEY", None)
    os.environ["KALSHI_API_KEY_ID"] = "test-key-id"
    try:
        yield
    finally:
        if original_key is None:
            os.environ.pop("KALSHI_API_KEY_ID", None)
        else:
            os.environ["KALSHI_API_KEY_ID"] = original_key
        if original_pem is not None:
            os.environ["KALSHI_API_PRIVATE_KEY_PEM"] = original_pem
        if original_pem_path is not None:
            os.environ["KALSHI_API_PRIVATE_KEY_PEM_PATH"] = original_pem_path
        if original_legacy_pem is not None:
            os.environ["KALSHI_API_PRIVATE_KEY"] = original_legacy_pem


def _caps_with_market(market: str):
    caps = load_caps()
    caps.allowed_markets = [market]
    return caps


def _patch_caps(market: str):
    caps = _caps_with_market(market)
    return (
        patch("live_firewall.firewall.load_caps", return_value=caps),
        patch("execution.hybrid_path.load_caps", return_value=caps),
    )


def _live_fixture_rehearsal() -> HybridLiveCapRehearsalV2:
    """Use deterministic inputs while exercising the live-only gate path."""
    rehearsal = HybridLiveCapRehearsalV2()
    rehearsal.disagreement.review = AsyncMock(
        return_value={
            "disagreement_score": Decimal("0.01"),
            "source_of_disagreement": None,
            "required_action": "none",
            "no_trade_bias_adjustment": Decimal("0"),
            "proof_reference": "test-disagreement-proof",
        }
    )
    loop = rehearsal.loop
    original_mock = loop._mock_market_data

    def imbalanced_mock():
        entries = original_mock()
        for market, _contract, book in entries:
            if market.ticker == "BTC-ABOVE-100K":
                book.bids[0].price = 49
                book.bids[0].size = 2000
                book.asks[0].price = 51
                book.asks[0].size = 1
        return entries

    loop._mock_market_data = imbalanced_mock
    original_run = loop.run_for_contract

    async def fixture_run(contract_ticker: str, max_markets: int = 5):
        details = await original_run(contract_ticker, max_markets)
        if details is not None:
            details["source"] = "live"
            details["model_mode"] = "LIVE_HYBRID"
            details["credentials_present"] = True
            details["opinion"].no_trade_reason = None
        return details

    loop.run_for_contract = fixture_run
    original_derive = rehearsal._derive_trade_decision

    def passive_fixture_proposal(*args, **kwargs):
        proposal = original_derive(*args, **kwargs)
        if proposal is not None:
            orderbook = args[3]
            proposal.price_cents = int(orderbook.bids[0].price)
        return proposal

    rehearsal._derive_trade_decision = passive_fixture_proposal
    rehearsal.firewall._verified_live_compliance_verdict = AsyncMock(
        return_value=FirewallVerdict(allow=True, reason="verified sports metadata")
    )
    return rehearsal


@pytest.mark.asyncio
async def test_rehearsal_blocked_by_default():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["status"] == "rehearsal"
    assert result["would_submit"] is False
    assert result["blocked_reason"] == "live_submit_disabled"
    assert result["live_submitted"] is False
    assert result["strategy_governor_decision"] == "APPROVE_FOR_FIREWALL_REHEARSAL"
    assert result["firewall_rehearsal"]["order"]["type"] == "limit"


@pytest.mark.asyncio
async def test_rehearsal_would_submit_when_enabled():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        with patch.object(
            LiveBrokerFirewall,
            "submit",
            new=AsyncMock(
                return_value=LiveOrderResult(
                    success=True, order_id="o1", proof_reference="p1"
                )
            ),
        ), patch.object(LiveBrokerFirewall, "_live_submit_enabled", return_value=True):
            rehearsal = _live_fixture_rehearsal()
            rehearsal.firewall.live_authority_verdict = lambda: FirewallVerdict(
                allow=True, reason="test authority"
            )
            result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["would_submit"] is True
    assert result["live_submitted"] is True
    assert result["status"] == "live_submitted"


@pytest.mark.asyncio
async def test_rehearsal_requires_autonomous_live_capped_mode():
    state_module.STATE.set_mode(AccountMode.READ_ONLY)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "mode"
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_equity_index_rehearsal_blocks_before_market_or_model_work():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    rehearsal = _live_fixture_rehearsal()
    rehearsal.loop.run_for_contract = AsyncMock()

    result = await rehearsal.rehearse(
        "SPX-ABOVE-5000",
        "SPX-ABOVE-5000-YES",
    )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "equity_index_target_quarantine"
    assert result["live_submitted"] is False
    rehearsal.loop.run_for_contract.assert_not_awaited()


@pytest.mark.asyncio
async def test_hybrid_rehearsal_requires_explicit_strategy_prediction_authority():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()

        class UndeclaredStrategy:
            name = "undeclared"

            def evaluate(self, *_args, **_kwargs):
                raise AssertionError("undeclared strategy must never run")

        rehearsal.intelligence.scanner.strategies = [UndeclaredStrategy()]
        rehearsal.firewall.submit_rehearsal = AsyncMock()

        result = await rehearsal.rehearse(
            "BTC-ABOVE-100K",
            "BTC-ABOVE-100K-YES",
        )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "strategy_prediction_authority"
    assert "proposal" not in result
    rehearsal.firewall.submit_rehearsal.assert_not_awaited()


@pytest.mark.asyncio
async def test_hybrid_rehearsal_blocks_forecast_orderbook_identity_mismatch():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    rehearsal = _live_fixture_rehearsal()
    original = rehearsal.loop.run_for_contract

    async def mismatched_book(*args, **kwargs):
        details = await original(*args, **kwargs)
        assert details is not None
        details["orderbook"].contract_ticker = "DIFFERENT-CONTRACT"
        return details

    rehearsal.loop.run_for_contract = mismatched_book
    rehearsal.intelligence.evaluate_quant_only = AsyncMock()
    rehearsal.firewall.submit_rehearsal = AsyncMock()

    result = await rehearsal.rehearse(
        "BTC-ABOVE-100K",
        "BTC-ABOVE-100K-YES",
    )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "context_integrity"
    assert result["identity_mismatches"] == ["orderbook"]
    assert "proposal" not in result
    rehearsal.intelligence.evaluate_quant_only.assert_not_awaited()
    rehearsal.firewall.submit_rehearsal.assert_not_awaited()


@pytest.mark.asyncio
async def test_hybrid_rehearsal_blocks_mismatched_selected_proposal_before_persistence():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        original_derive = rehearsal._derive_trade_decision

        def mismatched_proposal(*args, **kwargs):
            proposal = original_derive(*args, **kwargs)
            assert proposal is not None
            return proposal.model_copy(
                update={"contract_ticker": "KXTSLAA-26JUL22-B350"}
            )

        rehearsal._derive_trade_decision = mismatched_proposal
        rehearsal.firewall.submit_rehearsal = AsyncMock()
        result = await rehearsal.rehearse(
            "BTC-ABOVE-100K",
            "BTC-ABOVE-100K-YES",
        )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "context_integrity"
    assert "proposal" not in result
    rehearsal.firewall.submit_rehearsal.assert_not_awaited()


@pytest.mark.parametrize(
    "ticker",
    [
        "KXBAA-28JANDELIV-700",
        "KXEBAYA-28JANGMV-92000000000.0",
        "KXCVNAA-28JANUNITS-910000",
        "KXFA-28JANUSSALES-2300000.0",
        "KXUALA-28JANPAX-190000000",
    ],
)
@pytest.mark.asyncio
async def test_company_kpi_rehearsal_blocks_before_market_or_model_work(ticker):
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    rehearsal = _live_fixture_rehearsal()
    rehearsal.loop.run_for_contract = AsyncMock()

    result = await rehearsal.rehearse(ticker, ticker)

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "equity_index_target_quarantine"
    assert result["live_submitted"] is False
    rehearsal.loop.run_for_contract.assert_not_awaited()


@pytest.mark.asyncio
async def test_degraded_hybrid_review_cannot_advance_to_firewall():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    rehearsal = _live_fixture_rehearsal()
    original = rehearsal.loop.run_for_contract

    async def degraded(*args, **kwargs):
        details = await original(*args, **kwargs)
        assert details is not None
        details["model_mode"] = "DEGRADED_QUANT_ONLY"
        details["model_degradation_reasons"] = ["provider_error:risk"]
        return details

    rehearsal.loop.run_for_contract = degraded
    rehearsal.firewall.submit_rehearsal = AsyncMock()

    result = await rehearsal.rehearse(
        "BTC-ABOVE-100K",
        "BTC-ABOVE-100K-YES",
    )

    assert result["status"] == "no_trade"
    assert result["rejected_by"] == "hybrid_model_validation"
    assert result["live_submitted"] is False
    rehearsal.firewall.submit_rehearsal.assert_not_awaited()


@pytest.mark.asyncio
async def test_research_only_model_has_no_risk_or_disagreement_operational_input():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        rehearsal._risk_critique_from_review = AsyncMock()
        result = await rehearsal.rehearse(
            "BTC-ABOVE-100K",
            "BTC-ABOVE-100K-YES",
        )

    assert result["disagreement"]["operationally_authorized"] is False
    assert result["disagreement"]["disagreement_score"] == Decimal("0")
    rehearsal.disagreement.review.assert_not_awaited()
    rehearsal._risk_critique_from_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_sports_phase_has_no_order_authority():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        original = rehearsal.loop.run_for_contract

        async def ambiguous_sports_phase(*args, **kwargs):
            details = await original(*args, **kwargs)
            assert details is not None
            details["market"].category = "Sports"
            details["scores"]["live_phase"] = None
            details["scores"]["market_phase"] = "unknown"
            details["model_probability_authority"] = Decimal("0")
            return details

        rehearsal.loop.run_for_contract = ambiguous_sports_phase
        rehearsal.firewall.submit_rehearsal = AsyncMock()
        result = await rehearsal.rehearse(
            "BTC-ABOVE-100K",
            "BTC-ABOVE-100K-YES",
        )

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "sports_phase_authority"
    assert result["model_probability_authority"] == 0
    assert result["live_submitted"] is False
    rehearsal.firewall.submit_rehearsal.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_valid_panel_no_trade_reason_is_hard_veto():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    rehearsal = _live_fixture_rehearsal()
    original = rehearsal.loop.run_for_contract

    async def authorized_panel_veto(*args, **kwargs):
        details = await original(*args, **kwargs)
        assert details is not None
        details["model_probability_authority"] = Decimal("0.20")
        prior = details["model_probability_authority_decision"]
        details["model_probability_authority_decision"] = (
            ModelProbabilityAuthorityDecision(
                scope=prior.scope,
                weight=Decimal("0.20"),
                authorized=True,
                blockers=(),
                evidence_ref="typed-authorized-veto-test.json",
            )
        )
        details["opinion"].no_trade_reason = "  panel found unresolved settlement risk  "
        return details

    rehearsal.loop.run_for_contract = authorized_panel_veto
    rehearsal.loop._review_contract_failures = lambda _review: []
    rehearsal.intelligence.evaluate = AsyncMock()
    rehearsal.firewall.submit_rehearsal = AsyncMock()
    rehearsal.governor.evaluate = AsyncMock()

    result = await rehearsal.rehearse(
        "BTC-ABOVE-100K",
        "BTC-ABOVE-100K-YES",
    )

    assert result["status"] == "no_trade"
    assert result["rejected_by"] == "authorized_panel_no_trade"
    assert result["reason"] == "panel found unresolved settlement risk"
    assert result["strategy_governor_decision"] == "NOT_EVALUATED_PANEL_VETO"
    assert result["live_submitted"] is False
    rehearsal.intelligence.evaluate.assert_not_awaited()
    rehearsal.governor.evaluate.assert_not_awaited()
    rehearsal.firewall.submit_rehearsal.assert_not_awaited()


@pytest.mark.asyncio
async def test_zero_authority_mock_no_trade_text_cannot_veto():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        original = rehearsal.loop.run_for_contract

        async def research_only_text(*args, **kwargs):
            details = await original(*args, **kwargs)
            assert details is not None
            details["model_probability_authority"] = Decimal("0")
            details["opinion"].no_trade_reason = "mock fallback says stop"
            return details

        rehearsal.loop.run_for_contract = research_only_text
        rehearsal.firewall.submit_rehearsal = AsyncMock(
            wraps=rehearsal.firewall.submit_rehearsal
        )
        result = await rehearsal.rehearse(
            "BTC-ABOVE-100K",
            "BTC-ABOVE-100K-YES",
        )

    assert result["status"] == "rehearsal"
    assert result.get("rejected_by") != "authorized_panel_no_trade"
    assert result["disagreement"]["operationally_authorized"] is False
    assert result["live_submitted"] is False
    rehearsal.firewall.submit_rehearsal.assert_awaited_once()


@pytest.mark.asyncio
async def test_rehearsal_blocks_kill_switch():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.enable_kill_switch("test")
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["status"] == "blocked"
    assert "kill" in (result.get("blocked_reason") or "").lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_emergency_stop():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    state_module.STATE.trigger_emergency_stop()
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["status"] == "blocked"
    assert "emergency" in (result.get("blocked_reason") or "").lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_compliance_failure():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = _caps_with_market("BTC-ABOVE-100K")
    caps.blocked_categories = ["BTC-ABOVE-100K"]
    with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
        "execution.hybrid_path.load_caps", return_value=caps
    ):
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["status"] == "no_trade"
    assert result["strategy_governor_decision"] == "NO_TRADE"
    assert "compliance" in result["reason"].lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_poor_liquidity_via_governor():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    caps = _caps_with_market("MEME-STALE")
    with patch("live_firewall.firewall.load_caps", return_value=caps), patch(
        "execution.hybrid_path.load_caps", return_value=caps
    ):
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("MEME-STALE", "MEME-STALE-YES")

    assert result["status"] == "no_trade"
    assert result["strategy_governor_decision"] == "NO_TRADE"
    assert "liquidity" in result["reason"].lower()
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_blocks_missing_proof_reference():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        # Force a proposal with an empty strategy proof reference.
        rehearsal._derive_trade_decision = lambda *args, **kwargs: TradeProposal(
            id="bad",
            market_ticker="BTC-ABOVE-100K",
            contract_ticker="BTC-ABOVE-100K-YES",
            side="yes",
            price_cents=52,
            size=1,
            forecast_reference="forecast_1",
            edge_estimate=EdgeEstimate(
                expected_edge_bps=500, edge_after_fees_bps=450, confidence_score=Decimal("0.6")
            ),
            risk_estimate="low",
            confidence_estimate=Decimal("0.6"),
            expected_fill_behavior="limit",
            stop_condition="none",
            cancellation_condition="none",
            cap_impact={},
            compliance_verdict=ComplianceVerdict(
                passed=True, blocked_categories=[], reason=""
            ),
            proof_reference="",
        )
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["status"] == "blocked"
    assert result["rejected_by"] == "proof"
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_rehearsal_limit_order_only():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["firewall_rehearsal"]["order"]["type"] == "limit"
    assert result["live_submitted"] is False


@pytest.mark.asyncio
async def test_no_real_order_submitted_by_default():
    state_module.STATE.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    a, b = _patch_caps("BTC-ABOVE-100K")
    with a, b:
        rehearsal = _live_fixture_rehearsal()
        result = await rehearsal.rehearse("BTC-ABOVE-100K", "BTC-ABOVE-100K-YES")

    assert result["live_submitted"] is False
    assert result["order_result"] is None
