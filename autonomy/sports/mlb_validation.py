"""Three-head validation harness for MLB engines.

Grades a source's settled paper decisions on three independent heads:
  1. beat_close   - contested-Brier skill vs the market close (primary; the
                    money bar). Cluster-robust lower bound must clear zero.
  2. calibration  - full-surface Brier skill vs the market on all settled
                    decisions (a broad-calibration sanity guard).
  3. paper_pnl    - realized paper P&L (operational outcome).

Only the primary head gates champion readiness; the other two are surfaced so
a lucky contested streak or a mis-calibrated tail is visible. Pure and offline:
reads settled decisions, computes scores, writes nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HeadVerdict:
    name: str
    passed: bool
    metric: float | None
    n: int
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MlbEngineScorecard:
    source: str
    settled: int
    beat_close: HeadVerdict
    calibration: HeadVerdict
    paper_pnl: HeadVerdict

    @property
    def is_champion_ready(self) -> bool:
        """Only the primary head (beat the close) gates promotion."""
        return self.beat_close.passed


@dataclass(frozen=True)
class SettledDecision:
    source: str
    market_type: str
    event_cluster: str
    model_probability: float
    market_probability: float
    result_yes: bool
    pnl_cents: int | None = None


def settled_decisions_for(
    rows: Any, pnl_by_id: dict[str, int], source: str,
) -> list[SettledDecision]:
    """Settled decisions for one source, with realized P&L attached."""
    out: list[SettledDecision] = []
    for row in rows:
        if row.source != source or row.result_yes is None:
            continue
        pnl = pnl_by_id.get(row.observation_id)
        out.append(SettledDecision(
            source=row.source,
            market_type=row.market_type,
            event_cluster=row.event_cluster,
            model_probability=float(row.model_probability),
            market_probability=float(row.market_probability),
            result_yes=bool(row.result_yes),
            pnl_cents=None if pnl is None else int(pnl),
        ))
    return out
