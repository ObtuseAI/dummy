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
