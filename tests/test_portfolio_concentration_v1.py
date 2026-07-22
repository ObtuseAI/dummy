"""Adversarial portfolio-correlation and conservative-ranking regressions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.correlation import correlation_factors, group_key
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Decision, DecisionAction, Forecast, Signal
from autonomy.portfolio_challenger import (
    PortfolioCandidate,
    candidates_from_ledger,
    portfolio_challenger_from_ledger,
    solve_portfolio_challenger,
)


def _candidate(
    decision_id: str,
    ticker: str,
    *,
    cost: int,
    profit: float,
    group: str | None = None,
    count: int = 1,
    uncertainty: float | None = 0.0,
    fill_probability: float | None = 1.0,
    liquidity_score: float | None = 1.0,
    slippage: float = 0.0,
    loss: int | None = None,
    factors: tuple[str, ...] = (),
) -> PortfolioCandidate:
    return PortfolioCandidate(
        decision_id=decision_id,
        market_ticker=ticker,
        action="BUY_YES",
        cost_cents=cost,
        expected_profit_cents=profit,
        group=group or group_key(ticker),
        created_at="2026-07-21T12:00:00+00:00",
        max_profit_cents=10_000,
        contract_count=count,
        uncertainty=uncertainty,
        fill_probability=fill_probability,
        liquidity_score=liquidity_score,
        estimated_slippage_cents=slippage,
        worst_case_loss_cents=loss,
        risk_factors=factors,
    )


def test_every_known_surface_of_one_game_consumes_one_primary_risk_group() -> None:
    tickers = (
        "KXMLBGAME-26JUL211910BALBOS-BAL",
        "KXMLBSPREAD-26JUL211910BALBOS-BAL2",
        "KXMLBTOTAL-26JUL211910BALBOS-9",
        "KXMLBTEAMTOTAL-26JUL211910BALBOS-BAL5",
        "KXMLBF5TOTAL-26JUL211910BALBOS-5",
        "KXMLBHIT-26JUL211910BALBOS-BALPALONSO25-1",
        "KXMLBHR-26JUL211910BALBOS-BALPALONSO25-1",
    )
    assert len({group_key(ticker) for ticker in tickers}) == 1
    assert group_key(tickers[0]) != group_key(
        "KXMLBGAME-26JUL221910BALBOS-BAL"
    )


def test_optimizer_recomputes_canonical_group_instead_of_trusting_stale_labels() -> None:
    candidates = [
        _candidate(
            "winner", "KXMLBGAME-26JUL211910BALBOS-BAL", cost=40, profit=30,
            group="STALE:WINNER",
        ),
        _candidate(
            "spread", "KXMLBSPREAD-26JUL211910BALBOS-BAL2", cost=40, profit=29,
            group="STALE:SPREAD",
        ),
        _candidate(
            "other", "KXMLBGAME-26JUL221910BALBOS-BAL", cost=40, profit=20,
        ),
    ]
    report = solve_portfolio_challenger(
        candidates,
        budget_cents=80,
        max_positions=2,
        max_group_positions=1,
        max_factor_positions=3,
    )
    chosen = {row["decision_id"] for row in report["selected"]}
    assert chosen == {"winner", "other"}
    assert report["selected_count"] == 2


def test_player_and_team_prop_factors_are_nested_but_other_players_are_distinct() -> None:
    judge_hr = set(correlation_factors(
        "KXMLBHR-26JUL171905LADNYY-NYYAJUDGE1-1"
    ))
    judge_hit = set(correlation_factors(
        "KXMLBHIT-26JUL171905LADNYY-NYYAJUDGE1-2"
    ))
    stanton_hr = set(correlation_factors(
        "KXMLBHR-26JUL171905LADNYY-NYYSTANTON1-1"
    ))

    player = next(factor for factor in judge_hr if ":PLAYER_DAY:" in factor)
    team = next(factor for factor in judge_hr if ":TEAM_DAY:" in factor)
    assert player in judge_hit
    assert player not in stanton_hr
    assert team in judge_hit and team in stanton_hr


def test_crypto_assets_share_beta_expiry_factor_without_collapsing_primary_groups() -> None:
    btc = correlation_factors("KXBTC15M-26JUL161200-15")
    eth = correlation_factors("KXETH15M-26JUL161200-15")
    daily = correlation_factors("KXBTCD-26JUL161200-T65000")

    assert btc[0] != eth[0]
    beta = next(factor for factor in btc if ":BETA_EXPIRY:" in factor)
    assert beta in eth
    assert beta not in daily


def test_optimizer_enforces_derived_crypto_common_factor_when_groups_are_distinct() -> None:
    candidates = [
        _candidate("btc", "KXBTC15M-26JUL161200-15", cost=40, profit=20),
        _candidate("eth", "KXETH15M-26JUL161200-15", cost=40, profit=19),
        _candidate(
            "sports", "KXMLBGAME-26JUL211910BALBOS-BAL", cost=40, profit=18,
        ),
    ]
    report = solve_portfolio_challenger(
        candidates,
        budget_cents=80,
        max_positions=2,
        max_group_positions=2,
        max_factor_positions=1,
    )
    chosen = {row["decision_id"] for row in report["selected"]}
    assert chosen == {"btc", "sports"}
    assert report["execution_authority"] is False
    assert report["capital_authority_delta_cents"] == 0


def test_quality_adjusted_ranking_rejects_flashy_raw_ev_with_bad_fill_and_liquidity() -> None:
    candidates = [
        _candidate(
            "flashy", "KXALPHA-ONE-X", cost=50, profit=80,
            uncertainty=0.50, fill_probability=0.10, liquidity_score=0.20,
        ),
        _candidate(
            "clean", "KXBETA-TWO-X", cost=50, profit=40,
            uncertainty=0.02, fill_probability=0.90, liquidity_score=0.90,
        ),
    ]
    report = solve_portfolio_challenger(
        candidates, budget_cents=50, max_positions=1,
    )
    assert [row["decision_id"] for row in report["selected"]] == ["clean"]
    selected = report["selected"][0]
    assert selected["conservative_objective_cents"] < selected["expected_profit_cents"]
    assert selected["effective_fill_probability"] == 0.9


def test_cp_sat_can_beat_constrained_value_density_greedy() -> None:
    candidates = [
        _candidate("a", "KXALPHA-ONE-X", cost=51, profit=60),
        _candidate("b", "KXBETA-TWO-X", cost=50, profit=58),
        _candidate("c", "KXGAMMA-THREE-X", cost=50, profit=58),
    ]
    report = solve_portfolio_challenger(
        candidates,
        budget_cents=100,
        max_positions=2,
        max_group_positions=2,
        max_factor_positions=2,
    )
    assert {row["decision_id"] for row in report["greedy_baseline"]["selected"]} == {"a"}
    assert {row["decision_id"] for row in report["selected"]} == {"b", "c"}
    assert report["optimizer_advantage_cents"] == 56.0


def test_worst_case_loss_cap_is_independent_of_cash_budget() -> None:
    candidates = [
        _candidate(
            "tail", "KXALPHA-LOSS-X", cost=40, profit=40, loss=80,
        ),
        _candidate(
            "bounded", "KXBETA-LOSS-X", cost=40, profit=30, loss=40,
        ),
    ]
    report = solve_portfolio_challenger(
        candidates,
        budget_cents=100,
        max_positions=2,
        max_portfolio_loss_cents=60,
    )
    assert [row["decision_id"] for row in report["selected"]] == ["bounded"]
    assert report["total_worst_case_loss_cents"] <= 60


def test_nonfinite_candidate_is_quarantined_and_never_gains_authority() -> None:
    bad = _candidate("nan", "KXBAD-NAN-X", cost=10, profit=float("nan"))
    report = solve_portfolio_challenger([bad], budget_cents=100)
    assert report["status"] == "EMPTY"
    assert report["invalid_reasons"] == {
        "nonpositive_or_nonfinite_expected_profit": 1,
    }
    assert report["orders_created"] == 0
    assert report["risk_limits_changed"] is False


def test_ledger_candidate_uses_only_received_live_prior_before_decision(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXMLBGAME-26JUL211910BALBOS-BAL"
    now = datetime.now(timezone.utc)
    decision_at = now + timedelta(minutes=4)
    try:
        assert ledger.record_signal(Signal(
            source="market_prior",
            market_ticker=ticker,
            probability_yes=0.50,
            uncertainty=0.10,
            rationale="admissible quote",
            features={"spread": 5, "volume": 1000},
            created_at=(now - timedelta(minutes=1)).isoformat(),
        ))
        assert ledger.record_signal(Signal(
            source="market_prior",
            market_ticker=ticker,
            probability_yes=0.90,
            uncertainty=0.50,
            rationale="future quote",
            features={"spread": 19, "volume": 1},
            created_at=(now + timedelta(minutes=5)).isoformat(),
        ))
        assert ledger.record_signal(Signal(
            source="market_prior",
            market_ticker=ticker,
            probability_yes=0.10,
            uncertainty=0.50,
            rationale="retro quote",
            features={"spread": 20, "volume": 0},
            created_at=now.isoformat(),
        ), mode="retro")
        ledger.record_decision(Decision(
            decision_id="decision",
            market_ticker=ticker,
            action=DecisionAction.BUY_YES,
            side="yes",
            price_cents=40,
            count=2,
            ev_cents_per_contract=10.0,
            kelly_fraction=0.01,
            notional_cents=80,
            forecast=Forecast(
                market_ticker=ticker,
                probability_yes=0.60,
                uncertainty=0.12,
                sources_used={"market_prior": 0.5, "model": 0.5},
                market_implied_yes=0.50,
                edge_yes=0.10,
                rationale="fixture",
            ),
            risk_snapshot={},
            created_at=decision_at.isoformat(),
        ))

        rows = candidates_from_ledger(ledger, fill_probability=0.8)
        assert len(rows) == 1
        candidate = rows[0]
        assert candidate.uncertainty == 0.12
        assert candidate.fill_probability == 0.8
        assert candidate.liquidity_score == 0.75
        assert candidate.group == group_key(ticker)
    finally:
        ledger.close()


def test_ledger_portfolio_values_missing_fill_evidence_at_zero(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXMLBGAME-26JUL221910BALBOS-BAL"
    try:
        ledger.record_decision(Decision(
            decision_id="unfilled",
            market_ticker=ticker,
            action=DecisionAction.BUY_YES,
            side="yes",
            price_cents=40,
            count=1,
            ev_cents_per_contract=20.0,
            kelly_fraction=0.01,
            notional_cents=40,
            forecast=Forecast(
                market_ticker=ticker,
                probability_yes=0.70,
                uncertainty=0.05,
                sources_used={"model": 1.0},
                market_implied_yes=0.50,
                edge_yes=0.20,
                rationale="fixture",
            ),
            risk_snapshot={},
        ))
        report = portfolio_challenger_from_ledger(
            ledger,
            budget_cents=100,
        )
        assert report["status"] == "EMPTY"
        assert report["selected"] == []
        assert report["fill_probability_evidence"] == {
            "scope": "shadow",
            "estimate_used": 0.0,
            "interval": None,
            "method": "observed_fill_rate_wilson_95_lower_bound",
            "status": "NO_EVIDENCE_ZERO",
        }
    finally:
        ledger.close()
