"""Report-only discrete portfolio challenger powered by OR-Tools CP-SAT."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from autonomy.correlation import group_key


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


def solve_portfolio_challenger(
    candidates: Iterable[PortfolioCandidate],
    *,
    budget_cents: int,
    max_positions: int = 10,
    max_group_cost_cents: int | None = None,
    max_group_positions: int = 1,
) -> dict[str, Any]:
    """Solve a deterministic binary selection problem without placing orders."""
    raw_pool = list(candidates)
    invalid = [
        candidate for candidate in raw_pool
        if candidate.max_profit_cents is not None
        and candidate.expected_profit_cents > candidate.max_profit_cents + 1e-6
    ]
    pool = [candidate for candidate in raw_pool
            if candidate.cost_cents > 0 and candidate.expected_profit_cents > 0
            and candidate not in invalid]
    base = {
        "report_name": "PORTFOLIO_CHALLENGER",
        "execution_authority": False,
        "solver": "OR-Tools CP-SAT",
        "budget_cents": max(0, int(budget_cents)),
        "max_positions": max(0, int(max_positions)),
        "max_group_positions": max(0, int(max_group_positions)),
        "max_group_cost_cents": (
            max(0, int(max_group_cost_cents))
            if max_group_cost_cents is not None else max(0, int(budget_cents))
        ),
        "candidate_count": len(pool),
        "invalid_candidate_count": len(invalid),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if not pool or budget_cents <= 0 or max_positions <= 0:
        return {**base, "available": True, "status": "EMPTY", "selected": [],
                "selected_count": 0, "total_cost_cents": 0,
                "total_expected_profit_cents": 0.0}
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return {**base, "available": False, "status": "DEPENDENCY_UNAVAILABLE",
                "selected": [], "selected_count": 0, "total_cost_cents": 0,
                "total_expected_profit_cents": 0.0}

    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"candidate_{index}") for index in range(len(pool))]
    model.add(sum(selected[index] * candidate.cost_cents
                  for index, candidate in enumerate(pool)) <= int(budget_cents))
    model.add(sum(selected) <= int(max_positions))
    group_cap = int(max_group_cost_cents if max_group_cost_cents is not None else budget_cents)
    for group in sorted({candidate.group for candidate in pool}):
        model.add(sum(selected[index] * candidate.cost_cents
                      for index, candidate in enumerate(pool)
                      if candidate.group == group) <= group_cap)
        model.add(sum(selected[index]
                      for index, candidate in enumerate(pool)
                      if candidate.group == group) <= int(max_group_positions))

    # CP-SAT objectives are integers; milli-cents preserve sub-cent ordering.
    objective = [round(candidate.expected_profit_cents * 1000) for candidate in pool]
    model.maximize(sum(selected[index] * objective[index] for index in range(len(pool))))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status_code = solver.solve(model)
    status = solver.status_name(status_code)
    chosen = [candidate for index, candidate in enumerate(pool)
              if solver.boolean_value(selected[index])]
    return {
        **base,
        "available": True,
        "status": status,
        "objective_units": "milli_cents",
        "selected": [asdict(candidate) for candidate in chosen],
        "selected_count": len(chosen),
        "total_cost_cents": sum(candidate.cost_cents for candidate in chosen),
        "total_expected_profit_cents": round(
            sum(candidate.expected_profit_cents for candidate in chosen), 6,
        ),
    }


def candidates_from_ledger(ledger: Any, *, limit: int = 1000) -> list[PortfolioCandidate]:
    """Extract the latest actionable recorded decision for each market."""
    rows = ledger._conn.execute(  # noqa: SLF001 - trusted read-only analysis
        """
        SELECT decision_id, market_ticker, action, count, ev_cents,
               notional_cents, price_cents, created_at
        FROM decisions
        WHERE action != 'ABSTAIN' AND count > 0 AND notional_cents > 0
          AND NOT EXISTS (
              SELECT 1 FROM settlements
              WHERE settlements.market_ticker = decisions.market_ticker
          )
        ORDER BY created_at DESC, decision_id DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    latest: dict[str, PortfolioCandidate] = {}
    for decision_id, ticker, action, count, ev_cents, notional, price, created_at in rows:
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
        ))
    return list(latest.values())


def portfolio_challenger_from_ledger(
    ledger: Any,
    *,
    budget_cents: int,
    max_positions: int = 10,
    max_group_cost_cents: int | None = None,
    max_group_positions: int = 1,
) -> dict[str, Any]:
    return solve_portfolio_challenger(
        candidates_from_ledger(ledger),
        budget_cents=budget_cents,
        max_positions=max_positions,
        max_group_cost_cents=max_group_cost_cents,
        max_group_positions=max_group_positions,
    )
