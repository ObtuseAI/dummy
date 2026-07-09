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
# A source "contests" a market when it disagrees with the market prior by at
# least this much — the population it would actually trade.
CONTESTED_DISAGREEMENT = 0.05
# Contested records smaller than this are noise; they neither cap the weight
# nor qualify a source at the canary gate.
MIN_CONTESTED_N = 20


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
        # Contested markets: the source materially disagreed with the market.
        # This is the population that actually gets traded, so it is the one
        # that decides trust. Beating the market on markets where you AGREED
        # with it proves nothing about edge.
        self.contested_n = 0
        self.contested_beat = 0
        self.contested_edge_sum = 0.0  # sum of (market_brier - source_brier)
        # Per calibration bin: [count, sum_predicted, sum_outcome].
        self.bins: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(CALIBRATION_BINS)]

    def observe(self, p: float, outcome: int, market_brier: float,
                market_p: float | None = None) -> None:
        self.n += 1
        source_brier = _brier(p, outcome)
        self.brier_sum += source_brier
        self.logloss_sum += _log_loss(p, outcome)
        if source_brier < market_brier:
            self.beat_market += 1
        if market_p is not None and abs(p - market_p) >= CONTESTED_DISAGREEMENT:
            self.contested_n += 1
            self.contested_edge_sum += market_brier - source_brier
            if source_brier < market_brier:
                self.contested_beat += 1
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
            "contested_n": self.contested_n,
            "contested_beat_rate": (round(self.contested_beat / self.contested_n, 3)
                                    if self.contested_n else None),
            "contested_net_brier_edge": round(self.contested_edge_sum, 4),
            "calibration": calibration,
        }

    def derived_weight(self) -> float:
        """Trust from realized performance.

        Base: mean Brier vs the 0.25 no-skill reference. When the contested
        record is large enough to mean something, the weight is additionally
        capped by contested performance — a source that looks well-calibrated
        overall but loses when it disagrees with the market must not carry an
        above-market voice into the fusion.
        """
        if self.n == 0:
            return 1.0
        mean_brier = self.brier_sum / self.n
        advantage = (0.25 - mean_brier) / 0.25
        weight = math.exp(1.2 * advantage)
        if self.contested_n >= MIN_CONTESTED_N:
            contested_rate = self.contested_beat / self.contested_n
            contested_weight = math.exp(2.5 * (contested_rate - 0.5))
            weight = min(weight, contested_weight)
        return max(WEIGHT_FLOOR, min(WEIGHT_CEILING, weight))


def run_backtest(ledger: AutonomyLedger, bootstrap_weights: bool = False) -> dict[str, Any]:
    """Score all sources against settled markets; optionally persist weights."""
    conn = ledger._conn  # noqa: SLF001 - backtester is a trusted ledger consumer
    settlements = {row[0]: int(row[1]) for row in conn.execute("SELECT market_ticker, result_yes FROM settlements")}
    if not settlements:
        return {"report_name": "AUTONOMY_BACKTEST", "settled_markets": 0,
                "note": "no settlements to score", "created_at": datetime.now(timezone.utc).isoformat()}

    from autonomy.scanner import classify_vertical

    trackers: dict[str, SourceScoreTracker] = {}
    scoped_trackers: dict[str, SourceScoreTracker] = {}
    for ticker, result in settlements.items():
        rows = conn.execute(
            "SELECT source, probability_yes FROM signals WHERE market_ticker=?", (ticker,)
        ).fetchall()
        latest: dict[str, float] = {}
        for source, prob in rows:
            latest[source] = float(prob)  # last write wins = latest opinion
        market_p = latest.get("market_prior", 0.5)
        market_brier = _brier(market_p, result)
        vertical = classify_vertical(ticker).value
        for source, prob in latest.items():
            trackers.setdefault(source, SourceScoreTracker(source)).observe(
                prob, result, market_brier, market_p=market_p)
            scoped_key = f"{source}@{vertical}"
            scoped_trackers.setdefault(scoped_key, SourceScoreTracker(scoped_key)).observe(
                prob, result, market_brier, market_p=market_p)

    # Realized decision P&L (settled decisions only).
    pnl_rows = conn.execute(
        "SELECT COALESCE(SUM(pnl_cents),0), COUNT(*) FROM outcomes "
        "WHERE pnl_cents IS NOT NULL AND kind IN ('SETTLED_WIN','SETTLED_LOSS')"
    ).fetchone()
    realized_pnl = int(pnl_rows[0])
    graded = int(pnl_rows[1])

    source_summaries = {s: t.summary() for s, t in trackers.items()}
    derived = {s: round(t.derived_weight(), 3) for s, t in trackers.items()}
    derived_scoped = {s: round(t.derived_weight(), 3) for s, t in scoped_trackers.items()}

    if bootstrap_weights:
        for source, weight in derived.items():
            ledger.update_weight(source, weight)
        for scoped_key, weight in derived_scoped.items():
            ledger.update_weight(scoped_key, weight)

    return {
        "report_name": "AUTONOMY_BACKTEST",
        "settled_markets": len(settlements),
        "sources": source_summaries,
        "sources_by_vertical": {s: {k: t.summary()[k] for k in
                                    ("n", "mean_brier", "contested_n", "contested_beat_rate")}
                                for s, t in scoped_trackers.items()},
        "derived_weights": derived,
        "derived_weights_by_vertical": derived_scoped,
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
