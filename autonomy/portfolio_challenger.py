"""Capital-neutral portfolio research with nested concentration constraints.

This module is deliberately report-only. It compares a deterministic greedy
baseline with a CP-SAT portfolio under the same budget, worst-case-loss,
same-event, and broader common-factor caps. No selected row is an order and no
function here can submit, resize, or relax a production risk limit.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from autonomy.correlation import correlation_factors, group_key

UNKNOWN_FILL_PROBABILITY = 0.25
UNKNOWN_LIQUIDITY_SCORE = 0.50
UNKNOWN_UNCERTAINTY = 0.10
DEFAULT_UNCERTAINTY_PENALTY_SIGMAS = 0.50
ACTIONABLE_SPREAD_CENTS = 20.0


@dataclass(frozen=True)
class PortfolioCandidate:
    decision_id: str
    market_ticker: str
    action: str
    cost_cents: int
    expected_profit_cents: float
    group: str
    created_at: str
    max_profit_cents: int | None = None
    contract_count: int = 1
    uncertainty: float | None = None
    fill_probability: float | None = None
    liquidity_score: float | None = None
    estimated_slippage_cents: float = 0.0
    worst_case_loss_cents: int | None = None
    risk_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ScoredCandidate:
    candidate: PortfolioCandidate
    primary_groups: tuple[str, ...]
    conservative_value_cents: float
    uncertainty_penalty_cents: float
    effective_fill_probability: float
    effective_liquidity_score: float
    worst_case_loss_cents: int
    factors: tuple[str, ...]
    assumptions: tuple[str, ...]


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _invalid_reason(candidate: PortfolioCandidate) -> str | None:
    if not str(candidate.decision_id).strip() or not str(candidate.market_ticker).strip():
        return "missing_identity"
    if not str(candidate.group).strip():
        return "missing_primary_group"
    if not isinstance(candidate.cost_cents, int) or candidate.cost_cents <= 0:
        return "nonpositive_cost"
    if not isinstance(candidate.contract_count, int) or candidate.contract_count <= 0:
        return "nonpositive_contract_count"
    if not _finite_number(candidate.expected_profit_cents) or candidate.expected_profit_cents <= 0:
        return "nonpositive_or_nonfinite_expected_profit"
    if candidate.max_profit_cents is not None:
        if not isinstance(candidate.max_profit_cents, int) or candidate.max_profit_cents < 0:
            return "invalid_max_profit"
        if candidate.expected_profit_cents > candidate.max_profit_cents + 1e-6:
            return "expected_profit_exceeds_payoff_bound"
    if candidate.uncertainty is not None and (
        not _finite_number(candidate.uncertainty)
        or not 0.0 <= float(candidate.uncertainty) <= 0.5
    ):
        return "invalid_uncertainty"
    for field_name, value in (
        ("fill_probability", candidate.fill_probability),
        ("liquidity_score", candidate.liquidity_score),
    ):
        if value is not None and (
            not _finite_number(value) or not 0.0 <= float(value) <= 1.0
        ):
            return f"invalid_{field_name}"
    if (
        not _finite_number(candidate.estimated_slippage_cents)
        or candidate.estimated_slippage_cents < 0
    ):
        return "invalid_slippage"
    if candidate.worst_case_loss_cents is not None and (
        not isinstance(candidate.worst_case_loss_cents, int)
        or candidate.worst_case_loss_cents < 0
    ):
        return "invalid_worst_case_loss"
    if any(not isinstance(factor, str) or not factor.strip() for factor in candidate.risk_factors):
        return "invalid_risk_factor"
    return None


def _score_candidate(
    candidate: PortfolioCandidate,
    *,
    uncertainty_penalty_sigmas: float,
) -> _ScoredCandidate:
    assumptions: list[str] = []
    if candidate.uncertainty is None:
        uncertainty = UNKNOWN_UNCERTAINTY
        assumptions.append("unknown_uncertainty_policy")
    else:
        uncertainty = float(candidate.uncertainty)
    if candidate.fill_probability is None:
        fill_probability = UNKNOWN_FILL_PROBABILITY
        assumptions.append("unknown_fill_probability_policy")
    else:
        fill_probability = float(candidate.fill_probability)
    if candidate.liquidity_score is None:
        liquidity_score = UNKNOWN_LIQUIDITY_SCORE
        assumptions.append("unknown_liquidity_policy")
    else:
        liquidity_score = float(candidate.liquidity_score)

    uncertainty_penalty = (
        uncertainty_penalty_sigmas * uncertainty * 100.0 * candidate.contract_count
    )
    conditional_value = max(
        0.0,
        float(candidate.expected_profit_cents)
        - uncertainty_penalty
        - float(candidate.estimated_slippage_cents),
    )
    conservative_value = conditional_value * fill_probability * liquidity_score
    loss_bound = max(
        candidate.cost_cents,
        int(candidate.worst_case_loss_cents or 0),
    )
    primary_groups = tuple(dict.fromkeys((
        candidate.group, group_key(candidate.market_ticker),
    )))
    factors = tuple(dict.fromkeys((
        *primary_groups,
        *correlation_factors(candidate.market_ticker),
        *candidate.risk_factors,
    )))
    return _ScoredCandidate(
        candidate=candidate,
        primary_groups=primary_groups,
        conservative_value_cents=conservative_value,
        uncertainty_penalty_cents=uncertainty_penalty,
        effective_fill_probability=fill_probability,
        effective_liquidity_score=liquidity_score,
        worst_case_loss_cents=loss_bound,
        factors=factors,
        assumptions=tuple(assumptions),
    )


def _payload(scored: _ScoredCandidate) -> dict[str, Any]:
    payload = asdict(scored.candidate)
    payload.update({
        "primary_groups": list(scored.primary_groups),
        "risk_factors": list(scored.factors),
        "conservative_objective_cents": round(scored.conservative_value_cents, 6),
        "uncertainty_penalty_cents": round(scored.uncertainty_penalty_cents, 6),
        "effective_fill_probability": round(scored.effective_fill_probability, 6),
        "effective_liquidity_score": round(scored.effective_liquidity_score, 6),
        "worst_case_loss_cents": scored.worst_case_loss_cents,
        "assumptions": list(scored.assumptions),
    })
    return payload


def _totals(chosen: list[_ScoredCandidate]) -> dict[str, Any]:
    return {
        "selected_count": len(chosen),
        "total_cost_cents": sum(row.candidate.cost_cents for row in chosen),
        "total_worst_case_loss_cents": sum(row.worst_case_loss_cents for row in chosen),
        "total_expected_profit_cents": round(
            sum(row.candidate.expected_profit_cents for row in chosen), 6,
        ),
        "total_conservative_objective_cents": round(
            sum(row.conservative_value_cents for row in chosen), 6,
        ),
    }


def _greedy_baseline(
    pool: list[_ScoredCandidate],
    *,
    budget_cents: int,
    max_positions: int,
    max_group_cost_cents: int,
    max_group_positions: int,
    max_factor_cost_cents: int,
    max_factor_positions: int,
    max_portfolio_loss_cents: int,
) -> list[_ScoredCandidate]:
    """Risk-adjusted value-density greedy comparator under identical caps."""
    ordered = sorted(
        pool,
        key=lambda row: (
            -(row.conservative_value_cents / row.candidate.cost_cents),
            -row.conservative_value_cents,
            row.candidate.decision_id,
        ),
    )
    chosen: list[_ScoredCandidate] = []
    cost = loss = 0
    group_cost: defaultdict[str, int] = defaultdict(int)
    group_count: defaultdict[str, int] = defaultdict(int)
    factor_cost: defaultdict[str, int] = defaultdict(int)
    factor_count: defaultdict[str, int] = defaultdict(int)
    for row in ordered:
        candidate = row.candidate
        if len(chosen) >= max_positions:
            break
        if cost + candidate.cost_cents > budget_cents:
            continue
        if loss + row.worst_case_loss_cents > max_portfolio_loss_cents:
            continue
        if any(group_cost[group] + candidate.cost_cents > max_group_cost_cents
               for group in row.primary_groups):
            continue
        if any(group_count[group] + 1 > max_group_positions
               for group in row.primary_groups):
            continue
        if any(factor_cost[factor] + candidate.cost_cents > max_factor_cost_cents
               for factor in row.factors):
            continue
        if any(factor_count[factor] + 1 > max_factor_positions for factor in row.factors):
            continue
        chosen.append(row)
        cost += candidate.cost_cents
        loss += row.worst_case_loss_cents
        for group in row.primary_groups:
            group_cost[group] += candidate.cost_cents
            group_count[group] += 1
        for factor in row.factors:
            factor_cost[factor] += candidate.cost_cents
            factor_count[factor] += 1
    return chosen


def solve_portfolio_challenger(
    candidates: Iterable[PortfolioCandidate],
    *,
    budget_cents: int,
    max_positions: int = 10,
    max_group_cost_cents: int | None = None,
    max_group_positions: int = 1,
    max_factor_cost_cents: int | None = None,
    max_factor_positions: int = 2,
    max_portfolio_loss_cents: int | None = None,
    uncertainty_penalty_sigmas: float = DEFAULT_UNCERTAINTY_PENALTY_SIGMAS,
) -> dict[str, Any]:
    """Compare greedy and optimal selections without placing or authorizing orders."""
    raw_pool = list(candidates)
    invalid_reasons = Counter(
        reason for candidate in raw_pool if (reason := _invalid_reason(candidate)) is not None
    )
    valid = [candidate for candidate in raw_pool if _invalid_reason(candidate) is None]

    budget = max(0, int(budget_cents))
    positions_cap = max(0, int(max_positions))
    group_position_cap = max(0, int(max_group_positions))
    factor_position_cap = max(0, int(max_factor_positions))
    group_cost_cap = min(
        budget,
        max(0, int(max_group_cost_cents))
        if max_group_cost_cents is not None else budget,
    )
    factor_cost_cap = min(
        budget,
        max(0, int(max_factor_cost_cents))
        if max_factor_cost_cents is not None else budget,
    )
    loss_cap = min(
        budget,
        max(0, int(max_portfolio_loss_cents))
        if max_portfolio_loss_cents is not None else budget,
    )
    penalty_sigmas = max(0.0, float(uncertainty_penalty_sigmas))
    scored = [
        _score_candidate(candidate, uncertainty_penalty_sigmas=penalty_sigmas)
        for candidate in valid
    ]
    pool = [row for row in scored if row.conservative_value_cents > 0]
    assumptions = Counter(assumption for row in scored for assumption in row.assumptions)

    base = {
        "report_name": "PORTFOLIO_CHALLENGER_V2",
        "execution_authority": False,
        "orders_created": 0,
        "capital_authority_delta_cents": 0,
        "risk_limits_changed": False,
        "solver": "OR-Tools CP-SAT",
        "objective": "fill_liquidity_slippage_uncertainty_adjusted_expected_profit",
        "objective_units": "milli_cents",
        "budget_cents": budget,
        "max_positions": positions_cap,
        "max_group_positions": group_position_cap,
        "max_group_cost_cents": group_cost_cap,
        "max_factor_positions": factor_position_cap,
        "max_factor_cost_cents": factor_cost_cap,
        "max_portfolio_loss_cents": loss_cap,
        "uncertainty_penalty_sigmas": penalty_sigmas,
        "unknown_evidence_policy": {
            "uncertainty": UNKNOWN_UNCERTAINTY,
            "fill_probability": UNKNOWN_FILL_PROBABILITY,
            "liquidity_score": UNKNOWN_LIQUIDITY_SCORE,
        },
        "raw_candidate_count": len(raw_pool),
        "candidate_count": len(pool),
        "invalid_candidate_count": sum(invalid_reasons.values()),
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "nonpositive_conservative_value_count": len(scored) - len(pool),
        "assumption_counts": dict(sorted(assumptions.items())),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    empty_totals = _totals([])
    if (
        not pool or budget <= 0 or positions_cap <= 0 or loss_cap <= 0
        or group_position_cap <= 0 or factor_position_cap <= 0
    ):
        return {
            **base,
            "available": True,
            "status": "EMPTY",
            "selected": [],
            **empty_totals,
            "greedy_baseline": {
                "policy": "conservative_value_per_cost",
                "selected": [],
                **empty_totals,
            },
            "optimizer_advantage_cents": 0.0,
        }
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return {
            **base,
            "available": False,
            "status": "DEPENDENCY_UNAVAILABLE",
            "selected": [],
            **empty_totals,
            "greedy_baseline": None,
            "optimizer_advantage_cents": None,
        }

    greedy = _greedy_baseline(
        pool,
        budget_cents=budget,
        max_positions=positions_cap,
        max_group_cost_cents=group_cost_cap,
        max_group_positions=group_position_cap,
        max_factor_cost_cents=factor_cost_cap,
        max_factor_positions=factor_position_cap,
        max_portfolio_loss_cents=loss_cap,
    )

    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"candidate_{index}") for index in range(len(pool))]
    model.add(sum(selected[index] * row.candidate.cost_cents
                  for index, row in enumerate(pool)) <= budget)
    model.add(sum(selected[index] * row.worst_case_loss_cents
                  for index, row in enumerate(pool)) <= loss_cap)
    model.add(sum(selected) <= positions_cap)
    for group in sorted({group for row in pool for group in row.primary_groups}):
        model.add(sum(selected[index] * row.candidate.cost_cents
                      for index, row in enumerate(pool)
                      if group in row.primary_groups) <= group_cost_cap)
        model.add(sum(selected[index]
                      for index, row in enumerate(pool)
                      if group in row.primary_groups) <= group_position_cap)
    for factor in sorted({factor for row in pool for factor in row.factors}):
        model.add(sum(selected[index] * row.candidate.cost_cents
                      for index, row in enumerate(pool)
                      if factor in row.factors) <= factor_cost_cap)
        model.add(sum(selected[index]
                      for index, row in enumerate(pool)
                      if factor in row.factors) <= factor_position_cap)

    objective = [
        max(1, round(row.conservative_value_cents * 1000)) for row in pool
    ]
    model.maximize(sum(selected[index] * objective[index] for index in range(len(pool))))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status_code = solver.solve(model)
    status = solver.status_name(status_code)
    has_solution = status_code in {cp_model.FEASIBLE, cp_model.OPTIMAL}
    chosen = [
        row for index, row in enumerate(pool)
        if has_solution and solver.boolean_value(selected[index])
    ]
    chosen.sort(key=lambda row: row.candidate.decision_id)
    greedy.sort(key=lambda row: row.candidate.decision_id)
    chosen_totals = _totals(chosen)
    greedy_totals = _totals(greedy)
    advantage = (
        chosen_totals["total_conservative_objective_cents"]
        - greedy_totals["total_conservative_objective_cents"]
    )
    return {
        **base,
        "available": True,
        "status": status,
        "selected": [_payload(row) for row in chosen],
        **chosen_totals,
        "greedy_baseline": {
            "policy": "conservative_value_per_cost",
            "selected": [_payload(row) for row in greedy],
            **greedy_totals,
        },
        "optimizer_advantage_cents": round(advantage, 6),
    }


def _liquidity_score(raw_features: Any) -> float | None:
    """Conservative point-in-time score from the recorded market-prior quote."""
    try:
        features = json.loads(raw_features or "{}")
        spread = float(features["spread"])
        volume = float(features["volume"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not math.isfinite(spread) or not math.isfinite(volume) or spread < 0 or volume < 0:
        return None
    spread_quality = max(0.0, min(1.0, 1.0 - spread / ACTIONABLE_SPREAD_CENTS))
    volume_quality = min(1.0, math.log1p(volume) / math.log1p(1000.0))
    return round(min(spread_quality, volume_quality), 6)


def candidates_from_ledger(
    ledger: Any,
    *,
    limit: int = 1000,
    fill_probability: float | None = None,
) -> list[PortfolioCandidate]:
    """Extract PIT-safe latest open decisions with recorded quote quality."""
    rows = ledger._conn.execute(  # noqa: SLF001 - trusted read-only analysis
        """
        SELECT d.decision_id, d.market_ticker, d.action, d.count, d.ev_cents,
               d.notional_cents, d.price_cents, d.created_at,
               d.forecast_uncertainty,
               (
                   SELECT s.features FROM signal_history s
                   WHERE s.market_ticker = d.market_ticker
                     AND s.source = 'market_prior'
                     AND LOWER(COALESCE(s.mode, 'live')) = 'live'
                     AND julianday(s.created_at) <= julianday(d.created_at)
                     AND julianday(COALESCE(s.ingested_at, s.created_at))
                         <= julianday(d.created_at)
                   ORDER BY julianday(s.created_at) DESC, s.id DESC
                   LIMIT 1
               ) AS market_prior_features
        FROM decisions d
        WHERE d.action != 'ABSTAIN' AND d.count > 0 AND d.notional_cents > 0
          AND NOT EXISTS (
              SELECT 1 FROM settlements st
              WHERE st.market_ticker = d.market_ticker
          )
        ORDER BY julianday(d.created_at) DESC, d.decision_id DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    latest: dict[str, PortfolioCandidate] = {}
    for (
        decision_id, ticker, action, count, ev_cents, notional, price,
        created_at, uncertainty, market_prior_features,
    ) in rows:
        market_ticker = str(ticker)
        latest.setdefault(market_ticker, PortfolioCandidate(
            decision_id=str(decision_id),
            market_ticker=market_ticker,
            action=str(action),
            cost_cents=int(notional),
            expected_profit_cents=float(ev_cents) * int(count),
            group=group_key(market_ticker),
            created_at=str(created_at),
            max_profit_cents=int(count) * max(0, 100 - int(price)),
            contract_count=int(count),
            uncertainty=float(uncertainty) if uncertainty is not None else None,
            fill_probability=fill_probability,
            liquidity_score=_liquidity_score(market_prior_features),
            worst_case_loss_cents=int(notional),
            risk_factors=correlation_factors(market_ticker),
        ))
    return list(latest.values())


def portfolio_challenger_from_ledger(
    ledger: Any,
    *,
    budget_cents: int,
    max_positions: int = 10,
    max_group_cost_cents: int | None = None,
    max_group_positions: int = 1,
    max_factor_cost_cents: int | None = None,
    max_factor_positions: int = 2,
    max_portfolio_loss_cents: int | None = None,
) -> dict[str, Any]:
    fill_summary = ledger.execution_summary("shadow")
    fill_interval = fill_summary.get("observed_fill_rate_ci95") or {}
    observed_lower = fill_interval.get("lower")
    # No observed fill evidence means zero executable value, never a guessed fill.
    fill_probability = float(observed_lower) if _finite_number(observed_lower) else 0.0
    report = solve_portfolio_challenger(
        candidates_from_ledger(ledger, fill_probability=fill_probability),
        budget_cents=budget_cents,
        max_positions=max_positions,
        max_group_cost_cents=max_group_cost_cents,
        max_group_positions=max_group_positions,
        max_factor_cost_cents=max_factor_cost_cents,
        max_factor_positions=max_factor_positions,
        max_portfolio_loss_cents=max_portfolio_loss_cents,
    )
    return {
        **report,
        "fill_probability_evidence": {
            "scope": "shadow",
            "estimate_used": fill_probability,
            "interval": fill_interval or None,
            "method": "observed_fill_rate_wilson_95_lower_bound",
            "status": (
                "OBSERVED_LOWER_BOUND" if observed_lower is not None else "NO_EVIDENCE_ZERO"
            ),
        },
    }
