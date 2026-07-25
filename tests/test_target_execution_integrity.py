from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from autonomy.brain import PredatorBrain, _authoritative_live_candidate_allowlist
from autonomy.executor import Executor
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    SessionMode,
    Vertical,
)
from autonomy.reconciler import Reconciler
from autonomy.risk_brain import RiskBrain


def _market(
    ticker: str,
    *,
    vertical: Vertical,
    category: str | None = None,
) -> MarketView:
    raw = {} if category is None else {"category": category}
    return MarketView(
        ticker=ticker,
        title="target integrity fixture",
        vertical=vertical,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        yes_bid=40,
        yes_ask=42,
        no_bid=58,
        no_ask=60,
        volume=100,
        liquidity=1_000,
        raw=raw,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def _decision(ticker: str) -> Decision:
    forecast = Forecast(
        market_ticker=ticker,
        probability_yes=0.70,
        uncertainty=0.05,
        sources_used={"test": 1.0},
        market_implied_yes=0.41,
        edge_yes=0.29,
        rationale="target-integrity-test",
    )
    return Decision(
        decision_id=f"decision-{ticker}",
        market_ticker=ticker,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=40,
        count=1,
        ev_cents_per_contract=25.0,
        kelly_fraction=0.01,
        notional_cents=40,
        forecast=forecast,
        risk_snapshot={},
    )


def test_shadow_executor_requires_exact_authoritative_market_context():
    ticker = "KXBTCD-26JUL2217-T120000"
    decision = _decision(ticker)
    executor = Executor(SessionMode.SHADOW)

    missing = asyncio.run(executor.execute(decision))
    assert missing.kind is OutcomeKind.BLOCKED_LOCAL
    assert missing.detail["reason"] == "prediction_target_context_unverified"

    mismatch = asyncio.run(
        executor.execute(
            decision,
            market=_market(
                "KXETHD-26JUL2217-T5000",
                vertical=Vertical.CRYPTO,
                category="Crypto",
            ),
        )
    )
    assert mismatch.kind is OutcomeKind.BLOCKED_LOCAL
    assert mismatch.detail["reason"] == "prediction_target_context_mismatch"

    verified = asyncio.run(
        executor.execute(
            decision,
            market=_market(ticker, vertical=Vertical.CRYPTO, category="Crypto"),
        )
    )
    assert verified.kind is OutcomeKind.SHADOW
    assert verified.broker_contacted is False


def test_opaque_company_target_cannot_enter_shadow_book():
    market = _market(
        "OPAQUE-28JANMETRIC-700",
        vertical=Vertical.OTHER,
        category="Companies",
    )
    outcome = asyncio.run(
        Executor(SessionMode.SHADOW).execute(
            _decision(market.ticker),
            market=market,
        )
    )

    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.order_id is None
    assert outcome.detail["reason"] == "prediction_target_quarantine"


class _StaticScanner:
    watchlist: list[str] = []

    def __init__(self, markets: list[MarketView]) -> None:
        self._markets = markets

    def scan(self) -> list[MarketView]:
        return list(self._markets)


class _CountingRegistry:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_cycle_start(self) -> None:
        return None

    def signals_for(self, market: MarketView) -> list[object]:
        self.calls.append(market.ticker)
        return []


def _brain(
    tmp_path,
    *,
    mode: SessionMode,
    markets: list[MarketView],
    registry: _CountingRegistry,
) -> tuple[PredatorBrain, AutonomyLedger]:
    ledger = AutonomyLedger(db_path=tmp_path / f"{mode.value.lower()}.db")
    brain = PredatorBrain(
        mode=mode,
        ledger=ledger,
        registry=registry,
        scanner=_StaticScanner(markets),
        risk_brain=RiskBrain(state_path=tmp_path / f"risk-{mode.value}.json"),
        executor=Executor(
            mode,
            session_path=tmp_path / "missing-session.json",
            kill_path=tmp_path / "KILL",
        ),
        reconciler=Reconciler(
            ledger,
            fetch_market_result=lambda _ticker: {},
        ),
        learner=Learner(ledger),
        exchange_status_fn=lambda: {
            "exchange_active": True,
            "trading_active": True,
        },
        board_path=tmp_path / f"board-{mode.value}.json",
    )
    return brain, ledger


def test_brain_filters_opaque_company_before_signals_tiers_or_book(
    tmp_path,
):
    company = _market(
        "OPAQUE-28JANMETRIC-700",
        vertical=Vertical.OTHER,
        category="Companies",
    )
    registry = _CountingRegistry()
    brain, ledger = _brain(
        tmp_path,
        mode=SessionMode.SHADOW,
        markets=[company],
        registry=registry,
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.markets_scanned == 0
        assert report.signals_generated == 0
        assert report.decisions_made == 0
        assert report.orders_placed == 0
        assert registry.calls == []
        assert "target_authority_filtered=1" in report.notes
    finally:
        ledger.close()


def test_live_cycle_signal_generation_is_exactly_allowlisted(tmp_path, monkeypatch):
    allowed = _market(
        "KXBTCD-26JUL2217-T120000",
        vertical=Vertical.CRYPTO,
        category="Crypto",
    )
    outside = _market(
        "KXMLBGAME-26JUL22NYYBOS-NYY",
        vertical=Vertical.SPORTS,
        category="Sports",
    )
    monkeypatch.setattr(
        "autonomy.brain._authoritative_live_candidate_allowlist",
        lambda: (lambda ticker: ticker == allowed.ticker),
    )
    registry = _CountingRegistry()
    brain, ledger = _brain(
        tmp_path,
        mode=SessionMode.LIVE,
        markets=[allowed, outside],
        registry=registry,
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.markets_scanned == 1
        assert registry.calls == [allowed.ticker]
        assert report.orders_placed == 0
    finally:
        ledger.close()


@pytest.mark.parametrize("allowlist", [lambda ticker: False, None])
def test_empty_or_unavailable_live_allowlist_generates_no_signals_or_orders(
    tmp_path,
    monkeypatch,
    allowlist,
):
    market = _market(
        "KXBTCD-26JUL2217-T120000",
        vertical=Vertical.CRYPTO,
        category="Crypto",
    )
    monkeypatch.setattr(
        "autonomy.brain._authoritative_live_candidate_allowlist",
        lambda: allowlist,
    )
    registry = _CountingRegistry()
    brain, ledger = _brain(
        tmp_path,
        mode=SessionMode.LIVE,
        markets=[market],
        registry=registry,
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.markets_scanned == 0
        assert report.signals_generated == 0
        assert report.decisions_made == 0
        assert report.orders_placed == 0
        assert registry.calls == []
    finally:
        ledger.close()


def test_live_allowlist_loader_rejects_invalid_authority_or_entries(monkeypatch):
    monkeypatch.setattr(
        "core.caps_authority.evaluate_caps_authority",
        lambda: SimpleNamespace(config_integrity_valid=False),
    )
    assert _authoritative_live_candidate_allowlist() is None

    monkeypatch.setattr(
        "core.caps_authority.evaluate_caps_authority",
        lambda: SimpleNamespace(config_integrity_valid=True),
    )
    monkeypatch.setattr(
        "core.config_loader.load_caps",
        lambda: SimpleNamespace(allowed_markets=[" KXBTC-BAD-WHITESPACE"]),
    )
    assert _authoritative_live_candidate_allowlist() is None

    # A malformed series grant is refused on exactly the same terms, and a
    # caps payload predating allowed_series keeps working (exact-match only).
    monkeypatch.setattr(
        "core.config_loader.load_caps",
        lambda: SimpleNamespace(allowed_markets=[], allowed_series=[" KXSOL15M"]),
    )
    assert _authoritative_live_candidate_allowlist() is None

    monkeypatch.setattr(
        "core.config_loader.load_caps",
        lambda: SimpleNamespace(allowed_markets=[], allowed_series=["KXSOL15M", "KXSOL15M"]),
    )
    assert _authoritative_live_candidate_allowlist() is None

    monkeypatch.setattr(
        "core.config_loader.load_caps",
        lambda: SimpleNamespace(allowed_markets=["KXBTC-EXACT"]),
    )
    exact = _authoritative_live_candidate_allowlist()
    assert exact is not None
    assert exact("KXBTC-EXACT") is True
    assert exact("KXBTC-OTHER") is False


def test_live_candidacy_honors_a_whole_series_grant(monkeypatch):
    """A series grant must make rotating contracts live candidates.

    Wave-88 added ``allowed_series`` and taught the firewall to honor it, but
    this loader still read ``allowed_markets`` alone.  Against the shipped caps
    (``allowed_markets: []``, ``allowed_series: ["KXSOL15M"]``) that combination
    filtered every market out of a LIVE cycle: the firewall would have accepted
    a KXSOL15M order the brain could never propose, so an armed session scanned
    zero markets and silently placed nothing.
    """
    monkeypatch.setattr(
        "core.caps_authority.evaluate_caps_authority",
        lambda: SimpleNamespace(config_integrity_valid=True),
    )
    monkeypatch.setattr(
        "core.config_loader.load_caps",
        lambda: SimpleNamespace(allowed_markets=[], allowed_series=["KXSOL15M"]),
    )
    is_candidate = _authoritative_live_candidate_allowlist()
    assert is_candidate is not None
    assert is_candidate("KXSOL15M-26JUL250345-45") is True
    # A KXSOL15M grant authorizes neither a neighbouring sol family nor a
    # longer series that merely starts with the same characters.
    assert is_candidate("KXSOLD-26JUL2504-T73.7499") is False
    assert is_candidate("KXSOL15MEGA-26JUL250345-45") is False


def test_live_candidacy_matches_the_firewall_it_will_be_checked_against(monkeypatch):
    """Candidacy and the firewall deny gate must read one authority.

    Two separate allowlist implementations is how the brain came to propose a
    set the firewall would reject, and to withhold a set the firewall would
    accept.  Pin the loader to the firewall's own matcher.
    """
    from core.ontology import CapConfig
    from live_firewall.firewall import market_is_allowlisted

    caps = CapConfig(allowed_markets=["KXBTC-EXACT"], allowed_series=["KXSOL15M"])
    monkeypatch.setattr(
        "core.caps_authority.evaluate_caps_authority",
        lambda: SimpleNamespace(config_integrity_valid=True),
    )
    monkeypatch.setattr("core.config_loader.load_caps", lambda: caps)
    is_candidate = _authoritative_live_candidate_allowlist()
    assert is_candidate is not None
    for ticker in (
        "KXSOL15M-26JUL250345-45",
        "KXBTC-EXACT",
        "KXSOLD-26JUL2504-T73.7499",
        "KXSOL15MEGA-26JUL250345-45",
        "",
    ):
        assert is_candidate(ticker) is market_is_allowlisted(ticker, caps)


def test_live_cycle_scans_a_series_authorized_rotating_contract(tmp_path, monkeypatch):
    """End to end: a LIVE cycle proposes the series-authorized contract only."""
    rotating = _market(
        "KXSOL15M-26JUL250345-45",
        vertical=Vertical.CRYPTO,
        category="Crypto",
    )
    outside = _market(
        "KXSOLD-26JUL2504-T73.7499",
        vertical=Vertical.CRYPTO,
        category="Crypto",
    )
    monkeypatch.setattr(
        "core.caps_authority.evaluate_caps_authority",
        lambda: SimpleNamespace(config_integrity_valid=True),
    )
    monkeypatch.setattr(
        "core.config_loader.load_caps",
        lambda: SimpleNamespace(allowed_markets=[], allowed_series=["KXSOL15M"]),
    )
    registry = _CountingRegistry()
    brain, ledger = _brain(
        tmp_path,
        mode=SessionMode.LIVE,
        markets=[rotating, outside],
        registry=registry,
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.markets_scanned == 1
        assert registry.calls == [rotating.ticker]
        # Candidacy is not authority: absent the operator live gates the
        # firewall still refuses, so no order leaves the box.
        assert report.orders_placed == 0
    finally:
        ledger.close()
