"""Offline backtester: grade the ledger against reality, bootstrap weights.

Replays every recorded signal against the settlement that eventually landed,
scoring each source's Brier and log-loss and its calibration curve. Then it
derives trust weights from that realized performance so a fresh live session
starts with sources already ranked by how right they have been — no capital
risked to learn it. Also reports realized decision P&L and the ROI multiple.

Pure offline: reads the ledger, writes a report, optionally writes weights
back. No network, no broker, no market mutation.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.ledger import AutonomyLedger

# Same shape as the live learner so bootstrapped weights are consistent.
WEIGHT_FLOOR = 0.05
WEIGHT_CEILING = 8.0
CALIBRATION_BINS = 10


def _brier(p: float, outcome: int) -> float:
    return (p - outcome) ** 2


def _log_loss(p: float, outcome: int) -> float:
    eps = 1e-6
    p = min(1 - eps, max(eps, p))
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1 - p))


class SourceScoreTracker:
    """Accumulates Brier / log-loss / calibration for one signal source."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.n = 0
        self.brier_sum = 0.0
        self.logloss_sum = 0.0
        self.beat_market = 0
        # Per calibration bin: [count, sum_predicted, sum_outcome].
        self.bins: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(CALIBRATION_BINS)]

    def observe(self, p: float, outcome: int, market_brier: float) -> None:
        self.n += 1
        self.brier_sum += _brier(p, outcome)
        self.logloss_sum += _log_loss(p, outcome)
        if _brier(p, outcome) < market_brier:
            self.beat_market += 1
        b = min(CALIBRATION_BINS - 1, int(p * CALIBRATION_BINS))
        self.bins[b][0] += 1
        self.bins[b][1] += p
        self.bins[b][2] += outcome

    def summary(self) -> dict[str, Any]:
        calibration = []
        for i, (cnt, sum_p, sum_o) in enumerate(self.bins):
            if cnt:
                calibration.append({
                    "bin": i, "n": int(cnt),
                    "avg_pred": round(sum_p / cnt, 3),
                    "avg_actual": round(sum_o / cnt, 3),
                })
        return {
            "source": self.source,
            "n": self.n,
            "mean_brier": round(self.brier_sum / self.n, 4) if self.n else None,
            "mean_log_loss": round(self.logloss_sum / self.n, 4) if self.n else None,
            "beat_market_rate": round(self.beat_market / self.n, 3) if self.n else None,
            "calibration": calibration,
        }

    def derived_weight(self) -> float:
        """Weight from mean Brier vs the 0.25 no-skill reference (p=0.5)."""
        if self.n == 0:
            return 1.0
        mean_brier = self.brier_sum / self.n
        advantage = (0.25 - mean_brier) / 0.25
        weight = math.exp(1.2 * advantage)
        return max(WEIGHT_FLOOR, min(WEIGHT_CEILING, weight))


def run_backtest(ledger: AutonomyLedger, bootstrap_weights: bool = False) -> dict[str, Any]:
    """Score all sources against settled markets; optionally persist weights."""
    conn = ledger._conn  # noqa: SLF001 - backtester is a trusted ledger consumer
    settlements = {row[0]: int(row[1]) for row in conn.execute("SELECT market_ticker, result_yes FROM settlements")}
    if not settlements:
        return {"report_name": "AUTONOMY_BACKTEST", "settled_markets": 0,
                "note": "no settlements to score", "created_at": datetime.now(timezone.utc).isoformat()}

    trackers: dict[str, SourceScoreTracker] = {}
    for ticker, result in settlements.items():
        rows = conn.execute(
            "SELECT source, probability_yes FROM signals WHERE market_ticker=?", (ticker,)
        ).fetchall()
        latest: dict[str, float] = {}
        for source, prob in rows:
            latest[source] = float(prob)  # last write wins = latest opinion
        market_p = latest.get("market_prior", 0.5)
        market_brier = _brier(market_p, result)
        for source, prob in latest.items():
            trackers.setdefault(source, SourceScoreTracker(source)).observe(prob, result, market_brier)

    # Realized decision P&L (settled decisions only).
    pnl_rows = conn.execute(
        "SELECT COALESCE(SUM(pnl_cents),0), COUNT(*) FROM outcomes "
        "WHERE pnl_cents IS NOT NULL AND kind IN ('SETTLED_WIN','SETTLED_LOSS')"
    ).fetchone()
    realized_pnl = int(pnl_rows[0])
    graded = int(pnl_rows[1])

    source_summaries = {s: t.summary() for s, t in trackers.items()}
    derived = {s: round(t.derived_weight(), 3) for s, t in trackers.items()}

    if bootstrap_weights:
        for source, weight in derived.items():
            ledger.update_weight(source, weight)

    return {
        "report_name": "AUTONOMY_BACKTEST",
        "settled_markets": len(settlements),
        "sources": source_summaries,
        "derived_weights": derived,
        "weights_written": bootstrap_weights,
        "realized_decision_pnl_cents": realized_pnl,
        "graded_decisions": graded,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_backtest_report(report: dict[str, Any], out_dir: Path | None = None) -> Path:
    import os

    root = Path(os.environ.get("DUMMY_EVIDENCE_ROOT", "artifacts/dummy"))
    out_dir = out_dir or (root / "backtests")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = out_dir / f"AUTONOMY_BACKTEST_{ts}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path
