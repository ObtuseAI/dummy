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
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.fees import kalshi_taker_fee_cents
from autonomy.ledger import AutonomyLedger
from autonomy.stats import mean_ci95

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
BOOTSTRAP_SAMPLES = 1000


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _mean_ci95(values: list[float]) -> dict[str, Any] | None:
    # A lone sample collapses to a point interval here (report continuity).
    return mean_ci95(values, collapse_single=True)


def _wilson_ci(successes: int, n: int) -> dict[str, Any] | None:
    if n <= 0:
        return None
    z = 1.96
    rate = successes / n
    denominator = 1.0 + z * z / n
    center = (rate + z * z / (2.0 * n)) / denominator
    margin = z * math.sqrt(rate * (1.0 - rate) / n + z * z / (4.0 * n * n)) / denominator
    return {
        "rate": round(rate, 6),
        "lower": round(max(0.0, center - margin), 6),
        "upper": round(min(1.0, center + margin), 6),
        "method": "wilson_95",
        "n": n,
    }


def _cluster_bootstrap_mean_ci(
    values_by_cluster: dict[str, list[float]], *, seed: str,
) -> dict[str, Any] | None:
    """Market-weighted mean CI while resampling correlated event clusters."""
    aggregates = [
        (sum(values), len(values)) for values in values_by_cluster.values() if values
    ]
    if not aggregates:
        return None
    observed = sum(total for total, _n in aggregates) / sum(n for _total, n in aggregates)
    if len(aggregates) == 1:
        lower = upper = observed
    else:
        rng = random.Random(seed)
        samples: list[float] = []
        for _ in range(BOOTSTRAP_SAMPLES):
            total = 0.0
            n = 0
            for _cluster in aggregates:
                sampled_total, sampled_n = aggregates[rng.randrange(len(aggregates))]
                total += sampled_total
                n += sampled_n
            samples.append(total / n)
        lower = float(_percentile(samples, 0.025) or 0.0)
        upper = float(_percentile(samples, 0.975) or 0.0)
    return {
        "mean": round(observed, 6),
        "lower": round(lower, 6),
        "upper": round(upper, 6),
        "method": "event_cluster_bootstrap_95",
        "clusters": len(aggregates),
        "resamples": BOOTSTRAP_SAMPLES if len(aggregates) > 1 else 0,
    }


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
        self.contested_edges: list[float] = []
        self.contested_edges_by_cluster: dict[str, list[float]] = {}
        self.probability_sum = 0.0
        self.outcome_sum = 0
        # Per calibration bin: [count, sum_predicted, sum_outcome].
        self.bins: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(CALIBRATION_BINS)]

    def observe(self, p: float, outcome: int, market_brier: float,
                market_p: float | None = None, cluster_key: str | None = None) -> None:
        self.n += 1
        self.probability_sum += p
        self.outcome_sum += outcome
        source_brier = _brier(p, outcome)
        self.brier_sum += source_brier
        self.logloss_sum += _log_loss(p, outcome)
        if source_brier < market_brier:
            self.beat_market += 1
        if market_p is not None and abs(p - market_p) >= CONTESTED_DISAGREEMENT:
            self.contested_n += 1
            brier_edge = market_brier - source_brier
            self.contested_edge_sum += brier_edge
            self.contested_edges.append(brier_edge)
            cluster = cluster_key or f"observation:{self.n}"
            self.contested_edges_by_cluster.setdefault(cluster, []).append(brier_edge)
            if source_brier < market_brier:
                self.contested_beat += 1
        b = min(CALIBRATION_BINS - 1, int(p * CALIBRATION_BINS))
        self.bins[b][0] += 1
        self.bins[b][1] += p
        self.bins[b][2] += outcome

    def summary(self) -> dict[str, Any]:
        calibration = []
        calibration_error_sum = 0.0
        max_calibration_error = 0.0
        for i, (cnt, sum_p, sum_o) in enumerate(self.bins):
            if cnt:
                average_prediction = sum_p / cnt
                average_actual = sum_o / cnt
                gap = abs(average_prediction - average_actual)
                calibration_error_sum += cnt * gap
                max_calibration_error = max(max_calibration_error, gap)
                calibration.append({
                    "bin": i, "n": int(cnt),
                    "avg_pred": round(average_prediction, 3),
                    "avg_actual": round(average_actual, 3),
                    "absolute_gap": round(gap, 4),
                })
        cluster_ci = _cluster_bootstrap_mean_ci(
            self.contested_edges_by_cluster, seed=f"source:{self.source}",
        )
        return {
            "source": self.source,
            "n": self.n,
            "mean_brier": round(self.brier_sum / self.n, 4) if self.n else None,
            "mean_log_loss": round(self.logloss_sum / self.n, 4) if self.n else None,
            "beat_market_rate": round(self.beat_market / self.n, 3) if self.n else None,
            "contested_n": self.contested_n,
            "contested_beat_rate": (round(self.contested_beat / self.contested_n, 3)
                                    if self.contested_n else None),
            "contested_beat_rate_ci95": _wilson_ci(
                self.contested_beat, self.contested_n,
            ),
            "contested_net_brier_edge": round(self.contested_edge_sum, 4),
            "contested_mean_brier_edge": (
                round(self.contested_edge_sum / self.contested_n, 6)
                if self.contested_n else None
            ),
            "contested_mean_brier_edge_ci95": cluster_ci,
            "contested_event_clusters": len(self.contested_edges_by_cluster),
            "expected_calibration_error": (
                round(calibration_error_sum / self.n, 6) if self.n else None
            ),
            "maximum_calibration_error": (
                round(max_calibration_error, 6) if self.n else None
            ),
            "mean_prediction": (
                round(self.probability_sum / self.n, 6) if self.n else None
            ),
            "outcome_prevalence": (
                round(self.outcome_sum / self.n, 6) if self.n else None
            ),
            "calibration": calibration,
        }

    def derived_weight(self) -> float:
        """Trust from realized performance.

        Base accuracy is capped by shrinkage-adjusted performance on contested
        markets. A tiny sample cannot crown a source, and many small wins
        cannot hide a few large Brier losses. Sources with no contested record
        remain neutral at best until they demonstrate actionable disagreement.
        """
        if self.n == 0:
            return 1.0
        mean_brier = self.brier_sum / self.n
        advantage = (0.25 - mean_brier) / 0.25
        weight = math.exp(1.2 * advantage)
        if self.source == "market_prior":
            return max(WEIGHT_FLOOR, min(WEIGHT_CEILING, weight))
        if self.contested_n > 0:
            confidence = min(1.0, self.contested_n / MIN_CONTESTED_N)
            contested_rate = self.contested_beat / self.contested_n
            rate_weight = math.exp(2.5 * (contested_rate - 0.5) * confidence)
            mean_edge = self.contested_edge_sum / self.contested_n
            magnitude_weight = math.exp(10.0 * mean_edge * confidence)
            weight = min(weight, rate_weight, magnitude_weight)
        else:
            weight = min(weight, 1.0)
        return max(WEIGHT_FLOOR, min(WEIGHT_CEILING, weight))


def _forecast_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    forecast_briers = [_brier(row["forecast"], row["result"]) for row in rows]
    market_briers = [_brier(row["market"], row["result"]) for row in rows]
    forecast_losses = [_log_loss(row["forecast"], row["result"]) for row in rows]
    market_losses = [_log_loss(row["market"], row["result"]) for row in rows]
    forecast_brier = sum(forecast_briers) / len(rows)
    market_brier = sum(market_briers) / len(rows)
    forecast_logloss = sum(forecast_losses) / len(rows)
    market_logloss = sum(market_losses) / len(rows)
    prevalence = sum(row["result"] for row in rows) / len(rows)
    null_brier = sum(_brier(prevalence, row["result"]) for row in rows) / len(rows)

    tracker = SourceScoreTracker("ensemble")
    for row, market_score in zip(rows, market_briers):
        tracker.observe(
            row["forecast"], row["result"], market_score,
            market_p=row["market"], cluster_key=row["cluster"],
        )
    calibration = tracker.summary()
    brier_advantages = [
        market_score - forecast_score
        for market_score, forecast_score in zip(market_briers, forecast_briers)
    ]
    logloss_advantages = [
        market_score - forecast_score
        for market_score, forecast_score in zip(market_losses, forecast_losses)
    ]
    return {
        "n": len(rows),
        "event_clusters": len({row["cluster"] for row in rows}),
        "outcome_prevalence": round(prevalence, 6),
        "forecast_brier": round(forecast_brier, 6),
        "market_brier": round(market_brier, 6),
        "null_prevalence_brier": round(null_brier, 6),
        "brier_skill_vs_market": (
            round(1.0 - forecast_brier / market_brier, 4) if market_brier > 0 else None
        ),
        "mean_brier_advantage_vs_market": round(market_brier - forecast_brier, 6),
        "mean_brier_advantage_ci95": _mean_ci95(brier_advantages),
        "forecast_log_loss": round(forecast_logloss, 6),
        "market_log_loss": round(market_logloss, 6),
        "mean_log_loss_advantage_vs_market": round(market_logloss - forecast_logloss, 6),
        "mean_log_loss_advantage_ci95": _mean_ci95(logloss_advantages),
        "expected_calibration_error": calibration["expected_calibration_error"],
        "maximum_calibration_error": calibration["maximum_calibration_error"],
        "calibration": calibration["calibration"],
    }


def _summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = [int(trade["pnl_cents"]) for trade in trades]
    cost = [int(trade["cost_cents"]) for trade in trades]
    running = 0
    peak = 0
    max_drawdown = 0
    for value in pnl:
        running += value
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)
    gross_profit = sum(value for value in pnl if value > 0)
    gross_loss = -sum(value for value in pnl if value < 0)
    return {
        "trades": len(trades),
        "event_clusters": len({trade["cluster"] for trade in trades}),
        "net_pnl_cents": sum(pnl),
        "entry_cost_cents": sum(cost),
        "average_pnl_cents": round(sum(pnl) / len(pnl), 3) if pnl else None,
        "mean_pnl_ci95": _mean_ci95([float(value) for value in pnl]),
        "win_rate": (
            round(sum(1 for trade in trades if trade["won"]) / len(trades), 3)
            if trades else None
        ),
        "roi_on_entry_cost": round(sum(pnl) / sum(cost), 4) if cost and sum(cost) else None,
        "profit_factor": (
            round(gross_profit / gross_loss, 4) if gross_loss else None
        ),
        "no_losing_trades": bool(pnl) and gross_loss == 0,
        "max_drawdown_cents": max_drawdown,
    }


def _threshold_trades(
    rows: list[dict[str, Any]], threshold_cents: int,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for row in rows:
        edge = row["forecast"] - row["market"]
        if abs(edge) * 100.0 < threshold_cents:
            continue
        if edge > 0:
            price = max(1, min(99, round(row["market"] * 100.0)))
            won = bool(row["result"])
        else:
            price = max(1, min(99, round((1.0 - row["market"]) * 100.0)))
            won = not bool(row["result"])
        fee = kalshi_taker_fee_cents(price, 1, row["ticker"])
        trades.append({
            "ticker": row["ticker"],
            "cluster": row["cluster"],
            "created_at": row["created_at"],
            "pnl_cents": (100 - price if won else -price) - fee,
            "cost_cents": price + fee,
            "won": won,
        })
    return trades


def _temporal_folds(rows: list[dict[str, Any]], requested: int = 4) -> list[list[dict[str, Any]]]:
    """Strictly chronological folds; clustered uncertainty is handled separately."""
    ordered = sorted(rows, key=lambda row: (row["created_at"], row["ticker"]))
    fold_count = min(requested, len(ordered))
    if fold_count == 0:
        return []
    folds: list[list[dict[str, Any]]] = [[] for _ in range(fold_count)]
    for index, row in enumerate(ordered):
        fold_index = min(fold_count - 1, index * fold_count // len(ordered))
        folds[fold_index].append(row)
    return folds


def _walk_forward_threshold_report(folds: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Tune the edge cutoff only on history, then score the next unseen fold."""
    if len(folds) < 2:
        return {"folds": 0, "note": "need at least two chronological event folds"}
    history: list[dict[str, Any]] = list(folds[0])
    fold_reports: list[dict[str, Any]] = []
    out_of_sample_trades: list[dict[str, Any]] = []
    for fold_number, test_rows in enumerate(folds[1:], start=2):
        test_start = min(row["created_at"] for row in test_rows)
        # Outcomes are allowed into training only if they were actually known
        # before the first decision in the test fold.
        training = [
            row for row in history if row["settled_at"] < test_start
        ]
        training_clusters = {row["cluster"] for row in training}
        purged_test_rows = [
            row for row in test_rows if row["cluster"] not in training_clusters
        ]
        candidates = []
        for threshold in range(1, 11):
            trades = _threshold_trades(training, threshold)
            summary = _summarize_trades(trades)
            candidates.append((threshold, summary))
        eligible = [candidate for candidate in candidates if candidate[1]["trades"] >= 10]
        pool = eligible or [candidate for candidate in candidates if candidate[1]["trades"] > 0]
        if not pool:
            history.extend(test_rows)
            continue
        selected_threshold, training_summary = max(
            pool,
            key=lambda candidate: (
                candidate[1]["net_pnl_cents"],
                candidate[1]["roi_on_entry_cost"] or float("-inf"),
                candidate[0],
            ),
        )
        test_trades = _threshold_trades(purged_test_rows, selected_threshold)
        test_summary = _summarize_trades(test_trades)
        out_of_sample_trades.extend(test_trades)
        fold_reports.append({
            "fold": fold_number,
            "train_rows": len(training),
            "test_rows": len(test_rows),
            "purged_test_rows": len(test_rows) - len(purged_test_rows),
            "selected_edge_threshold_cents": selected_threshold,
            "training_result": training_summary,
            "out_of_sample_result": test_summary,
            "test_start": test_start,
            "test_end": max(row["created_at"] for row in test_rows),
        })
        history.extend(test_rows)
    return {
        "method": "expanding_window_point_in_time_with_event_cluster_purge",
        "training_availability_rule": "settled_at strictly before test_start",
        "selection_objective": "maximize training net PnL; minimum 10 training trades when possible",
        "folds": len(fold_reports),
        "fold_results": fold_reports,
        "aggregate_out_of_sample": _summarize_trades(out_of_sample_trades),
    }


def _decision_policy_report(conn) -> dict[str, Any]:
    """Leakage-resistant final-ensemble evidence at the decision timestamp.

    One earliest snapshot per settled market prevents ten-minute cycle repeats
    from dominating the score. The threshold simulation uses the recorded
    market midpoint and taker fees, so it is a conservative directional-edge
    diagnostic, not a claim that a resting maker order would have filled.
    """
    raw = conn.execute(
        """
        SELECT d.market_ticker, d.probability_yes, d.market_implied_yes,
               d.created_at, s.result_yes, s.settled_at
        FROM decisions d JOIN settlements s ON s.market_ticker = d.market_ticker
        WHERE d.market_implied_yes IS NOT NULL
        ORDER BY d.created_at, d.decision_id
        """
    ).fetchall()
    earliest: dict[str, dict[str, Any]] = {}
    from autonomy.correlation import group_key

    for ticker, q, market, created_at, result, settled_at in raw:
        try:
            row = {
                "ticker": str(ticker),
                "forecast": float(q),
                "market": float(market),
                "created_at": str(created_at),
                "settled_at": str(settled_at),
                "result": int(result),
                "cluster": group_key(str(ticker)),
            }
        except (TypeError, ValueError):
            continue
        if not (0.0 < row["forecast"] < 1.0 and 0.0 < row["market"] < 1.0):
            continue
        earliest.setdefault(row["ticker"], row)
    rows = sorted(earliest.values(), key=lambda row: (row["created_at"], row["ticker"]))
    if not rows:
        return {"settled_markets": 0, "note": "no settled decision snapshots"}

    from autonomy.scanner import classify_vertical

    by_vertical: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_vertical.setdefault(classify_vertical(row["ticker"]).value, []).append(row)

    thresholds = []
    for threshold_cents in range(1, 11):
        summary = _summarize_trades(_threshold_trades(rows, threshold_cents))
        thresholds.append({"edge_threshold_cents": threshold_cents, **summary})

    folds = _temporal_folds(rows)
    temporal_stability = []
    for index, fold in enumerate(folds, start=1):
        temporal_stability.append({
            "fold": index,
            "start": min(row["created_at"] for row in fold),
            "end": max(row["created_at"] for row in fold),
            "metrics": _forecast_metrics(fold),
        })

    brier_by_cluster: dict[str, list[float]] = {}
    logloss_by_cluster: dict[str, list[float]] = {}
    for row in rows:
        brier_by_cluster.setdefault(row["cluster"], []).append(
            _brier(row["market"], row["result"])
            - _brier(row["forecast"], row["result"])
        )
        logloss_by_cluster.setdefault(row["cluster"], []).append(
            _log_loss(row["market"], row["result"])
            - _log_loss(row["forecast"], row["result"])
        )

    from autonomy.drift import adwin_drift_report

    # Positive values mean Dummy's forecast lost more Brier score than the
    # contemporaneous market. This remains a report-only alarm.
    brier_excess = [
        _brier(row["forecast"], row["result"])
        - _brier(row["market"], row["result"])
        for row in rows
    ]
    drift = adwin_drift_report(
        brier_excess,
        timestamps=[row["created_at"] for row in rows],
    )

    return {
        "settled_markets": len(rows),
        "event_clusters": len({row["cluster"] for row in rows}),
        "one_snapshot_per_market": "earliest_decision",
        "ensemble_metrics": _forecast_metrics(rows),
        "ensemble_metrics_by_vertical": {
            vertical: _forecast_metrics(vertical_rows)
            for vertical, vertical_rows in sorted(by_vertical.items())
        },
        "cluster_robust_advantage": {
            "brier": _cluster_bootstrap_mean_ci(
                brier_by_cluster, seed="decision-policy-brier",
            ),
            "log_loss": _cluster_bootstrap_mean_ci(
                logloss_by_cluster, seed="decision-policy-logloss",
            ),
        },
        "temporal_stability": temporal_stability,
        "online_forecast_drift": {
            **drift,
            "metric": "forecast_brier_minus_market_brier",
        },
        "counterfactual_mid_taker_thresholds": thresholds,
        "walk_forward_threshold_selection": _walk_forward_threshold_report(folds),
        "fill_adjusted": False,
        "caveat": (
            "Midpoint threshold results measure forecast direction after taker fees; "
            "they do not assume that Dummy's resting maker quotes filled. Full-sample "
            "threshold rows are descriptive; use walk_forward_threshold_selection for "
            "out-of-sample threshold evidence."
        ),
    }


def _realized_trade_report(conn) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT o.created_at, o.pnl_cents, o.fill_count, d.price_cents,
               d.market_ticker
        FROM outcomes o JOIN decisions d USING(decision_id)
        WHERE o.pnl_cents IS NOT NULL AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          AND EXISTS (
              SELECT 1 FROM outcomes fill
              WHERE fill.decision_id=o.decision_id AND fill.id<o.id
                AND fill.fill_count>0
          )
        ORDER BY o.created_at, o.id
        """
    ).fetchall()
    trades = []
    from autonomy.correlation import group_key

    for created_at, pnl_cents, fill_count, price_cents, ticker in rows:
        trades.append({
            "created_at": str(created_at),
            "pnl_cents": int(pnl_cents),
            "cost_cents": int(price_cents) * max(1, int(fill_count)),
            "won": int(pnl_cents) > 0,
            "cluster": group_key(str(ticker)),
        })
    return _summarize_trades(trades)


def _fill_witness_datetime(recorded_at: str, raw_detail: str) -> datetime:
    try:
        detail = json.loads(raw_detail or "{}")
    except Exception:
        detail = {}
    raw = detail.get("fill_witness_at") or detail.get("trade_created_time")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            pass
    if detail.get("candle_end_ts") is not None:
        try:
            return datetime.fromtimestamp(float(detail["candle_end_ts"]), timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    return datetime.fromisoformat(str(recorded_at).replace("Z", "+00:00"))


def _shadow_ttl_sensitivity_report(conn) -> dict[str, Any]:
    """Counterfactual retention of witnessed fills under shorter maker leases."""
    rows = conn.execute(
        """
        WITH first_fill AS (
            SELECT o.* FROM outcomes o
            WHERE o.id=(SELECT MIN(o2.id) FROM outcomes o2
                        WHERE o2.decision_id=o.decision_id AND o2.fill_count>0)
        ), book AS (
            SELECT decision_id,MAX(CASE WHEN kind='SHADOW' THEN 1 ELSE 0 END) is_shadow
            FROM outcomes GROUP BY decision_id
        )
        SELECT d.decision_id,d.created_at,f.created_at,f.detail,
               (SELECT pnl_cents FROM outcomes p
                WHERE p.decision_id=d.decision_id
                  AND p.kind IN ('SETTLED_WIN','SETTLED_LOSS')
                ORDER BY p.id DESC LIMIT 1) AS pnl_cents
        FROM decisions d JOIN first_fill f USING(decision_id)
        JOIN book b USING(decision_id)
        WHERE b.is_shadow=1
        ORDER BY d.created_at
        """
    ).fetchall()
    fills: list[dict[str, Any]] = []
    for decision_id, submitted_at, recorded_at, detail, pnl_cents in rows:
        try:
            submitted = datetime.fromisoformat(str(submitted_at).replace("Z", "+00:00"))
            witnessed = _fill_witness_datetime(str(recorded_at), str(detail or "{}"))
        except (TypeError, ValueError):
            continue
        fills.append({
            "decision_id": str(decision_id),
            "delay_seconds": max(0.0, (witnessed - submitted).total_seconds()),
            "pnl_cents": int(pnl_cents) if pnl_cents is not None else None,
        })
    thresholds = []
    for minutes in (1, 3, 5, 10, 20, 45):
        retained = [row for row in fills if row["delay_seconds"] <= minutes * 60]
        settled = [row for row in retained if row["pnl_cents"] is not None]
        thresholds.append({
            "ttl_minutes": minutes,
            "witnessed_fills_retained": len(retained),
            "settled_fills_retained": len(settled),
            "settled_net_pnl_cents": sum(int(row["pnl_cents"]) for row in settled),
            "settled_wins": sum(int(row["pnl_cents"]) > 0 for row in settled),
        })
    return {
        "method": "historical_witness_time_censoring",
        "observed_shadow_fills": len(fills),
        "thresholds": thresholds,
        "caveat": (
            "Shorter-TTL rows remove fills witnessed after the threshold; they do not "
            "invent fills or assume an order could be canceled after execution."
        ),
    }


def _fill_conditioned_policy_report(conn) -> dict[str, Any]:
    """Score forecasts only where the shadow maker policy witnessed a fill."""
    rows = conn.execute(
        """
        SELECT d.market_ticker,d.probability_yes,d.market_implied_yes,d.created_at,
               s.result_yes,s.settled_at
        FROM decisions d JOIN settlements s USING(market_ticker)
        WHERE d.market_implied_yes IS NOT NULL
          AND EXISTS (SELECT 1 FROM outcomes f
                      WHERE f.decision_id=d.decision_id AND f.fill_count>0)
        ORDER BY d.created_at,d.decision_id
        """
    ).fetchall()
    from autonomy.correlation import group_key

    samples = [{
        "ticker": str(ticker), "forecast": float(forecast), "market": float(market),
        "created_at": str(created_at), "settled_at": str(settled_at),
        "result": int(result), "cluster": group_key(str(ticker)),
    } for ticker, forecast, market, created_at, result, settled_at in rows]
    metrics = _forecast_metrics(samples)
    return {
        **metrics,
        "selection": "decisions_with_witnessed_fill_and_settlement",
        "event_clusters": len({row["cluster"] for row in samples}),
        "warning": (
            "Fill-conditioned evidence is selection-biased toward adverse maker fills; "
            "it is the operational complement to full-surface calibration."
        ),
    }


def _execution_drift_report(conn, scope: str) -> dict[str, Any]:
    """ADWIN diagnostic on terminal order failure (1=unfilled, 0=filled)."""
    rows = conn.execute(
        """
        WITH per_decision AS (
            SELECT decision_id,
                   MIN(CASE WHEN kind IN ('SHADOW','ACCEPTED') THEN created_at END)
                       AS submitted_at,
                   MAX(CASE WHEN kind IN ('SHADOW','ACCEPTED','PARTIALLY_FILLED',
                                          'FILLED','CANCELED','EXPIRED')
                            THEN fill_count ELSE 0 END) AS filled_count,
                   MAX(CASE WHEN kind IN ('CANCELED','EXPIRED') THEN 1 ELSE 0 END)
                       AS terminal,
                   MAX(CASE WHEN kind='SHADOW' THEN 1 ELSE 0 END) AS is_shadow,
                   MAX(broker_contacted) AS is_live
            FROM outcomes GROUP BY decision_id
        )
        SELECT submitted_at, filled_count, terminal, is_shadow, is_live
        FROM per_decision
        WHERE submitted_at IS NOT NULL AND (filled_count>0 OR terminal=1)
        ORDER BY submitted_at, decision_id
        """
    ).fetchall()
    filtered = [
        row for row in rows
        if (scope == "shadow" and int(row[3]) == 1)
        or (scope == "live" and int(row[4]) == 1 and int(row[3]) == 0)
    ]
    from autonomy.drift import adwin_drift_report

    report = adwin_drift_report(
        [0.0 if int(row[1]) > 0 else 1.0 for row in filtered],
        timestamps=[str(row[0]) for row in filtered],
        min_degradation=0.10,
    )
    return {**report, "metric": "terminal_order_unfilled", "book_scope": scope}


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    left = [pair[0] for pair in pairs]
    right = [pair[1] for pair in pairs]
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in pairs)
    denominator = math.sqrt(
        sum((a - mean_left) ** 2 for a in left)
        * sum((b - mean_right) ** 2 for b in right)
    )
    return round(numerator / denominator, 6) if denominator > 0 else None


def _crypto_fill_diagnostics(conn) -> dict[str, Any]:
    """Expose the selection gap hidden by easy full-surface crypto tails."""
    filled_rows = conn.execute(
        """
        SELECT d.decision_id,d.market_ticker,d.probability_yes,d.market_implied_yes,
               d.ev_cents,d.price_cents,d.sources_used,d.created_at,
               s.result_yes,o.pnl_cents,s.settled_at
        FROM decisions d JOIN settlements s USING(market_ticker)
        JOIN outcomes o USING(decision_id)
        WHERE (d.market_ticker GLOB 'KXBTC*' OR d.market_ticker GLOB 'KXETH*')
          AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          AND EXISTS (SELECT 1 FROM outcomes f WHERE f.decision_id=d.decision_id
                      AND f.id<o.id AND f.kind IN ('FILLED','PARTIALLY_FILLED')
                      AND f.fill_count>0)
        ORDER BY d.created_at,d.decision_id
        """
    ).fetchall()
    samples = []
    source_errors: dict[str, list[float]] = {}
    for (decision_id, ticker, forecast, market, ev, price, sources_used,
         created_at, result, pnl, settled_at) in filled_rows:
        if market is None:
            continue
        row = {
            "decision_id": str(decision_id), "ticker": str(ticker),
            "forecast": float(forecast), "market": float(market),
            "ev_cents": float(ev), "price_cents": int(price),
            "created_at": str(created_at), "settled_at": str(settled_at),
            "result": int(result), "pnl_cents": int(pnl),
            "prior_share": float((json.loads(sources_used or "{}") or {}).get("market_prior", 0.0)),
        }
        samples.append(row)
        latest: dict[str, float] = {}
        signal_rows = conn.execute(
            "SELECT source,probability_yes FROM signals WHERE market_ticker=?"
            " AND created_at<=? ORDER BY created_at DESC,id DESC",
            (ticker, created_at),
        ).fetchall()
        for source, probability in signal_rows:
            latest.setdefault(str(source), float(probability))
        for source, probability in latest.items():
            source_errors.setdefault(source, []).append(_brier(probability, int(result)))

    ensemble_errors = [_brier(row["forecast"], row["result"]) for row in samples]
    market_errors = [_brier(row["market"], row["result"]) for row in samples]
    anchor_blends = []
    for model_share in (0.0, 0.25, 0.50, 0.75, 1.0):
        errors = [
            _brier(
                row["market"] + model_share * (row["forecast"] - row["market"]),
                row["result"],
            )
            for row in samples
        ]
        anchor_blends.append({
            "model_share": model_share,
            "market_share": 1.0 - model_share,
            "brier": round(sum(errors) / len(errors), 6) if errors else None,
            "n": len(errors),
        })

    order_rows = conn.execute(
        """
        SELECT d.decision_id,d.market_ticker,d.ev_cents,d.price_cents,d.created_at,
               s.settled_at,
               MAX(CASE WHEN o.kind IN ('FILLED','PARTIALLY_FILLED')
                         AND o.fill_count>0 THEN 1 ELSE 0 END) AS filled,
               MAX(CASE WHEN o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
                         AND EXISTS (SELECT 1 FROM outcomes f
                                     WHERE f.decision_id=o.decision_id AND f.id<o.id
                                       AND f.kind IN ('FILLED','PARTIALLY_FILLED')
                                       AND f.fill_count>0)
                        THEN o.pnl_cents END) AS pnl
        FROM decisions d JOIN outcomes o USING(decision_id)
        LEFT JOIN settlements s USING(market_ticker)
        WHERE o.decision_id IN (SELECT decision_id FROM outcomes WHERE kind='SHADOW')
          AND (d.market_ticker GLOB 'KXBTC*' OR d.market_ticker GLOB 'KXETH*')
        GROUP BY d.decision_id
        ORDER BY d.created_at,d.decision_id
        """
    ).fetchall()
    accepted_orders = []
    open_until: dict[str, str] = {}
    repeats_blocked = 0
    for decision_id, ticker, ev, price, created_at, settled_at, filled, pnl in order_rows:
        is_repeat = str(ticker) in open_until and str(created_at) < open_until[str(ticker)]
        passes = float(ev) >= 8.0 and int(price) <= 75 and not is_repeat
        if is_repeat:
            repeats_blocked += 1
        if passes:
            accepted_orders.append({
                "decision_id": str(decision_id), "filled": bool(filled),
                "pnl_cents": int(pnl) if pnl is not None else None,
            })
        if settled_at is not None:
            open_until[str(ticker)] = str(settled_at)
    guarded_fills = [row for row in accepted_orders if row["filled"]]
    guarded_settled = [row for row in guarded_fills if row["pnl_cents"] is not None]

    paired = conn.execute(
        """
        WITH first_signal AS (
            SELECT s.market_ticker,s.source,s.probability_yes,
                   ROW_NUMBER() OVER (
                       PARTITION BY s.market_ticker,s.source
                       ORDER BY s.created_at,s.id
                   ) AS rank
            FROM signals s JOIN settlements st USING(market_ticker)
            WHERE s.source IN ('crypto_spot_vol','crypto_ewma_t')
              AND (s.market_ticker GLOB 'KXBTC*' OR s.market_ticker GLOB 'KXETH*')
        )
        SELECT a.probability_yes,b.probability_yes
        FROM first_signal a JOIN first_signal b USING(market_ticker)
        WHERE a.source='crypto_spot_vol' AND b.source='crypto_ewma_t'
          AND a.rank=1 AND b.rank=1
        """
    ).fetchall()
    pairs = [(float(a), float(b)) for a, b in paired]
    uncertainty_rows = conn.execute(
        """
        SELECT COUNT(*),SUM(CASE WHEN uncertainty<0.08 THEN 1 ELSE 0 END)
        FROM signals WHERE source IN ('crypto_spot_vol','crypto_ewma_t')
        """
    ).fetchone()
    return {
        "selection": "witnessed_crypto_fills_with_settlement",
        "filled_settled_decisions": len(samples),
        "net_pnl_cents": sum(row["pnl_cents"] for row in samples),
        "wins": sum(row["pnl_cents"] > 0 for row in samples),
        "ensemble_brier": round(sum(ensemble_errors) / len(ensemble_errors), 6)
        if ensemble_errors else None,
        "market_brier": round(sum(market_errors) / len(market_errors), 6)
        if market_errors else None,
        "source_brier": {
            source: {"n": len(errors), "brier": round(sum(errors) / len(errors), 6)}
            for source, errors in sorted(source_errors.items())
        },
        "market_anchor_blends": anchor_blends,
        "source_family_overlap": {
            "family": "crypto_coinbase_distribution",
            "paired_markets": len(pairs),
            "pearson_probability_correlation": _pearson(pairs),
            "mean_absolute_probability_gap": (
                round(sum(abs(a - b) for a, b in pairs) / len(pairs), 6) if pairs else None
            ),
        },
        "uncertainty_semantics": {
            "source_rows": int(uncertainty_rows[0] or 0),
            "legacy_rows_below_probability_floor": int(uncertainty_rows[1] or 0),
            "probability_floor": 0.08,
        },
        "guard_counterfactual": {
            "rule": "ev>=8c; price<=75c; no repeat market before settlement",
            "historical_orders": len(order_rows),
            "orders_retained": len(accepted_orders),
            "repeated_market_orders_blocked": repeats_blocked,
            "witnessed_fills_retained": len(guarded_fills),
            "settled_fills_retained": len(guarded_settled),
            "settled_net_pnl_cents": sum(row["pnl_cents"] for row in guarded_settled),
            "caveat": "observed-order filter only; does not invent replacement fills",
        },
    }


def _crypto_challenger_gates(
    conn, source_summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Promotion evidence for quarantined crypto sources; never auto-apply."""
    from autonomy.correlation import group_key

    result: dict[str, Any] = {}
    for source in (
        "crypto_empirical_regime",
        "crypto_technical_composite",
        "crypto_dvol_implied",
    ):
        rows = conn.execute(
            """
            SELECT s.market_ticker,s.mode FROM signals s
            JOIN settlements st USING(market_ticker)
            WHERE s.source=?
            GROUP BY s.market_ticker,s.mode
            """,
            (source,),
        ).fetchall()
        live_tickers = {str(ticker) for ticker, mode in rows if str(mode) == "live"}
        live_clusters = {group_key(ticker) for ticker in live_tickers}
        summary = source_summaries.get(source) or {}
        interval = summary.get("contested_mean_brier_edge_ci95") or {}
        evidence = {
            "settled_markets": int(summary.get("n") or 0),
            "contested_markets": int(summary.get("contested_n") or 0),
            "contested_event_clusters": int(summary.get("contested_event_clusters") or 0),
            "contested_brier_advantage_lower95": interval.get("lower"),
            "live_settled_markets": len(live_tickers),
            "live_event_clusters": len(live_clusters),
            "retro_settled_markets": len({str(ticker) for ticker, mode in rows if str(mode) == "retro"}),
        }
        blockers = []
        for label, current, required in (
            ("settled markets", evidence["settled_markets"], 500),
            ("contested markets", evidence["contested_markets"], 100),
            ("contested event clusters", evidence["contested_event_clusters"], 20),
            ("live settled markets", evidence["live_settled_markets"], 100),
            ("live event clusters", evidence["live_event_clusters"], 10),
        ):
            if current < required:
                blockers.append(f"{label} {current}/{required}")
        if interval.get("lower") is None or float(interval["lower"]) <= 0:
            blockers.append("contested Brier advantage lower95 is not positive")
        result[source] = {
            "ready_for_explicit_fusion_review": not blockers,
            "auto_promote": False,
            "execution_authority": False,
            "evidence": evidence,
            "blockers": blockers,
        }
    return result


def roll_up_trust_surface(sources_by_scope: dict[str, Any]) -> dict[str, Any]:
    """Additive (specialist, market_type, phase) roll-up of ``sources_by_scope``.

    Spec section 3.3 wants contested-Brier viewable as a *surface* keyed on
    ``(specialist, market_type, phase)``. ``sources_by_scope`` is already
    keyed ``source|market_type|phase_or_horizon`` (WS-15, via
    ``autonomy.taxonomy.grading_scope``); this is a PURE post-processing
    roll-up of those already-computed per-source summaries -- it never
    re-runs ``grading_scope`` or a second scope tracker, it only groups the
    existing keys by ``specialist_for(source)``.

    Honest by construction:
      * Point metrics (``mean_brier``, ``expected_calibration_error``,
        ``contested_beat_rate``) are n-weighted across the constituent
        sources -- a plain mean-of-means would misweight.
      * NO confidence interval is emitted at this coarser grain: the
        per-source cluster-bootstrap CIs cannot be honestly recombined from
        their summaries alone (that needs the raw per-cluster edges). The
        honest CIs stay in ``sources_by_scope``, and the promotion gate keeps
        reading THOSE. This surface is a human-facing evidence view, never a
        gate input -- CLV and this roll-up are both evidence, contested Brier
        at source grain remains the gate.
      * ``source_family`` / ``source_family_size`` disclose how many sources
        back each bucket (family-size disclosure, per house statistical
        honesty rules). ``contested_event_clusters_summed`` is the SUM across
        sources (an upper bound -- one event priced by two sources in the
        same bucket is counted twice; deduping needs the raw cluster sets,
        which is exactly what the per-source grain preserves).
    """
    from autonomy.taxonomy import specialist_for

    buckets: dict[str, dict[str, Any]] = {}
    for scope_key, summary in sources_by_scope.items():
        parts = str(scope_key).split("|")
        if len(parts) != 3:
            continue  # defensive: only well-formed source|market_type|axis keys
        source, market_type, axis = parts
        specialist = specialist_for(source)
        rolled_key = f"{specialist}|{market_type}|{axis}"
        bucket = buckets.setdefault(rolled_key, {
            "specialist": specialist, "market_type": market_type, "phase": axis,
            "n": 0, "contested_n": 0, "contested_event_clusters_summed": 0,
            "_brier_weighted": 0.0, "_ece_weighted": 0.0, "_beat_weighted": 0.0,
            "sources": set(),
        })
        n = int(summary.get("n") or 0)
        contested_n = int(summary.get("contested_n") or 0)
        bucket["n"] += n
        bucket["contested_n"] += contested_n
        bucket["contested_event_clusters_summed"] += int(
            summary.get("contested_event_clusters") or 0)
        if summary.get("mean_brier") is not None:
            bucket["_brier_weighted"] += n * float(summary["mean_brier"])
        if summary.get("expected_calibration_error") is not None:
            bucket["_ece_weighted"] += n * float(summary["expected_calibration_error"])
        if summary.get("contested_beat_rate") is not None:
            bucket["_beat_weighted"] += contested_n * float(summary["contested_beat_rate"])
        bucket["sources"].add(source)

    surface: dict[str, Any] = {}
    for rolled_key, bucket in buckets.items():
        n, contested_n = bucket["n"], bucket["contested_n"]
        surface[rolled_key] = {
            "specialist": bucket["specialist"],
            "market_type": bucket["market_type"],
            "phase": bucket["phase"],
            "n": n,
            "mean_brier": round(bucket["_brier_weighted"] / n, 4) if n else None,
            "expected_calibration_error": (
                round(bucket["_ece_weighted"] / n, 6) if n else None),
            "contested_n": contested_n,
            "contested_beat_rate": (
                round(bucket["_beat_weighted"] / contested_n, 3) if contested_n else None),
            "contested_event_clusters_summed": bucket["contested_event_clusters_summed"],
            "source_family": sorted(bucket["sources"]),
            "source_family_size": len(bucket["sources"]),
        }
    return surface


def run_backtest(ledger: AutonomyLedger, bootstrap_weights: bool = False) -> dict[str, Any]:
    """Score all sources against settled markets; optionally persist weights."""
    conn = ledger._conn  # noqa: SLF001 - backtester is a trusted ledger consumer
    settlements = {row[0]: int(row[1]) for row in conn.execute("SELECT market_ticker, result_yes FROM settlements")}
    if not settlements:
        return {"report_name": "AUTONOMY_BACKTEST", "settled_markets": 0,
                "note": "no settlements to score", "created_at": datetime.now(timezone.utc).isoformat()}

    from autonomy.correlation import group_key
    from autonomy.scanner import classify_vertical
    from autonomy.taxonomy import grading_scope

    trackers: dict[str, SourceScoreTracker] = {}
    scoped_trackers: dict[str, SourceScoreTracker] = {}
    # Per-scope trust: (source, market_type, horizon|phase). A source's good
    # daily-crypto behaviour no longer averages away its bad 15-minute
    # behaviour, and pre/live sports records stay separate. Evidence only --
    # scope keys are NOT written to the weights table (the live forecaster
    # looks up bare source names); they feed the WS-14 readiness report.
    scope_trackers: dict[str, SourceScoreTracker] = {}
    for ticker, result in settlements.items():
        rows = ledger.calibration_signals_for_market(ticker)
        latest = {str(row["source"]): float(row["probability_yes"]) for row in rows}
        features = {str(row["source"]): (row.get("features") or {}) for row in rows}
        market_p = latest.get("market_prior", 0.5)
        market_brier = _brier(market_p, result)
        vertical = classify_vertical(ticker).value
        cluster = group_key(ticker)
        for source, prob in latest.items():
            trackers.setdefault(source, SourceScoreTracker(source)).observe(
                prob, result, market_brier, market_p=market_p, cluster_key=cluster,
            )
            scoped_key = f"{source}@{vertical}"
            scoped_trackers.setdefault(scoped_key, SourceScoreTracker(scoped_key)).observe(
                prob, result, market_brier, market_p=market_p, cluster_key=cluster,
            )
            scope_key = grading_scope(source, ticker, features.get(source) or {})
            scope_trackers.setdefault(scope_key, SourceScoreTracker(scope_key)).observe(
                prob, result, market_brier, market_p=market_p, cluster_key=cluster,
            )

    # Realized decision P&L (settled decisions only).
    pnl_rows = conn.execute(
        """
        SELECT COALESCE(SUM(o.pnl_cents),0), COUNT(*) FROM outcomes o
        WHERE o.pnl_cents IS NOT NULL AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          AND EXISTS (
              SELECT 1 FROM outcomes fill
              WHERE fill.decision_id = o.decision_id
                AND fill.id < o.id AND fill.fill_count > 0
          )
        """
    ).fetchone()
    realized_pnl = int(pnl_rows[0])
    graded = int(pnl_rows[1])
    unverified = int(conn.execute(
        """
        SELECT COUNT(*) FROM outcomes o
        WHERE o.pnl_cents IS NOT NULL AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          AND NOT EXISTS (
              SELECT 1 FROM outcomes fill
              WHERE fill.decision_id = o.decision_id
                AND fill.id < o.id AND fill.fill_count > 0
          )
        """
    ).fetchone()[0])

    source_summaries = {s: t.summary() for s, t in trackers.items()}
    derived = {s: round(t.derived_weight(), 3) for s, t in trackers.items()}
    derived_scoped = {s: round(t.derived_weight(), 3) for s, t in scoped_trackers.items()}

    if bootstrap_weights:
        for source, weight in derived.items():
            ledger.update_weight(source, weight)
        for scoped_key, weight in derived_scoped.items():
            ledger.update_weight(scoped_key, weight)

    sources_by_scope = {s: {k: t.summary()[k] for k in
                            ("n", "mean_brier", "contested_n",
                             "contested_beat_rate", "contested_event_clusters",
                             "contested_mean_brier_edge_ci95",
                             "expected_calibration_error")}
                        for s, t in scope_trackers.items()}
    return {
        "report_name": "AUTONOMY_BACKTEST",
        "settled_markets": len(settlements),
        "sources": source_summaries,
        "source_snapshot_policy": "earliest_decision_time_else_earliest_phantom_opinion",
        "sources_by_vertical": {s: {k: t.summary()[k] for k in
                                    ("n", "mean_brier", "contested_n",
                                     "contested_beat_rate", "contested_event_clusters",
                                     "contested_mean_brier_edge_ci95",
                                     "expected_calibration_error")}
                                for s, t in scoped_trackers.items()},
        "sources_by_scope": sources_by_scope,
        # WS-8 (spec section 3.3): the literal (specialist, market_type, phase)
        # trust surface, rolled up ADDITIVELY from the source-grain
        # sources_by_scope above -- no re-keying, no second scope tracker.
        "trust_surface_by_specialist": roll_up_trust_surface(sources_by_scope),
        "derived_weights": derived,
        "derived_weights_by_vertical": derived_scoped,
        "weights_written": bootstrap_weights,
        "realized_decision_pnl_cents": realized_pnl,
        "graded_decisions": graded,
        "unverified_settlement_outcomes": unverified,
        "execution_quality": ledger.execution_summary(),
        "execution_quality_by_book": {
            "shadow": ledger.execution_summary("shadow"),
            "live": ledger.execution_summary("live"),
        },
        "execution_drift_by_book": {
            "shadow": _execution_drift_report(conn, "shadow"),
            "live": _execution_drift_report(conn, "live"),
        },
        "signal_data_quality": ledger.signal_quality_summary(),
        "realized_trade_statistics": _realized_trade_report(conn),
        "fill_conditioned_decision_policy": _fill_conditioned_policy_report(conn),
        "shadow_ttl_sensitivity": _shadow_ttl_sensitivity_report(conn),
        "crypto_diagnostics": _crypto_fill_diagnostics(conn),
        "crypto_challenger_gates": _crypto_challenger_gates(conn, source_summaries),
        "decision_policy": _decision_policy_report(conn),
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
