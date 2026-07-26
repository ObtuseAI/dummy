"""First-class adverse-selection instrumentation (Wave-1 WS-A1).

Dummy quotes maker-first: resting LIMIT orders that fill only when the book
crosses them. The operational blocker is that those fills arrive precisely
when the model is wrong -- classic maker adverse selection. Full-surface
calibration looks healthy while the *filled* subset bleeds. This module makes
adverse selection a measured, first-class quantity instead of an anecdote.

Read-only and deterministic. It reconstructs, from the ledger the reconciler
already writes, the population of actionable (non-abstain, submitted) settled
decisions and partitions it into the maker-filled subset (the adversely
selected fills) versus the unfilled subset, then reports side by side:

  * fill-conditioned skill (Brier / ECE / P&L net of fees / win rate) for the
    full actionable surface, the maker-filled subset, and the unfilled subset,
    plus a taker-execution counterfactual (cross at the recorded market
    midpoint, taker fee) so a maker-only vs taker-only vs hybrid tournament
    has an honest baseline;
  * the direct adverse-selection number -- forecast accuracy on filled vs
    unfilled emissions (fill-vs-no-fill outcome delta);
  * per-fill slippage (signal_price - fill_price, and market_price -
    fill_price);
  * the time-to-fill distribution against the subsequent realized move (did
    the market move through us before filling).

Every interval is cluster-level (per event-cluster mean, then a bootstrap /
t-interval over cluster means) -- never a per-emission CI, which would be
dishonestly tight because sibling strikes on one event share a settlement.

This module never mutates execution state: it opens nothing but the read-only
ledger and returns / writes JSON. Its fresh-evidence loader may supply a
non-negative information-cost measurement to the allocator, but it cannot
select an execution cohort, authorize an order, or turn missing evidence into
an estimate. Policy changes belong to the separate execution-policy tournament.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents

CALIBRATION_BINS = 10
BOOTSTRAP_SAMPLES = 1000
# Time-to-fill buckets (seconds). A fast cross means our quote was already
# stale/mispriced at submit; a slow cross means the market had to travel to
# reach us -- both are adverse-selection channels, measured separately.
_TTF_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("fast_le_60s", 0.0, 60.0),
    ("mid_60_300s", 60.0, 300.0),
    ("slow_gt_300s", 300.0, math.inf),
)


def _brier(p: float, outcome: int) -> float:
    return (p - outcome) ** 2


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _cluster_ci(values_by_cluster: dict[str, list[float]], *, seed: str) -> dict[str, Any] | None:
    """Cluster-robust mean CI: bootstrap over per-cluster mean values.

    Emissions inside one event cluster share a settlement print, so the honest
    unit of evidence is the cluster mean, never the raw row. With a single
    cluster the interval collapses to a point (reported, not hidden).
    """
    cluster_means = [
        sum(values) / len(values) for values in values_by_cluster.values() if values
    ]
    if not cluster_means:
        return None
    observed = sum(cluster_means) / len(cluster_means)
    if len(cluster_means) == 1:
        lower = upper = observed
        resamples = 0
    else:
        rng = random.Random(seed)
        samples: list[float] = []
        for _ in range(BOOTSTRAP_SAMPLES):
            draw = [cluster_means[rng.randrange(len(cluster_means))] for _ in cluster_means]
            samples.append(sum(draw) / len(draw))
        lower = float(_percentile(samples, 0.025) or observed)
        upper = float(_percentile(samples, 0.975) or observed)
        resamples = BOOTSTRAP_SAMPLES
    return {
        "mean": round(observed, 6),
        "lower": round(lower, 6),
        "upper": round(upper, 6),
        "method": "event_cluster_bootstrap_95",
        "clusters": len(cluster_means),
        "resamples": resamples,
    }


# --------------------------------------------------------------------------- #
# Ledger reconstruction
# --------------------------------------------------------------------------- #


def _parse_dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def load_execution_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """One row per actionable, submitted, settled decision.

    Actionable = a real order (``action != 'ABSTAIN'``) that was submitted
    (a SHADOW/ACCEPTED outcome exists) into a market that later settled and
    carried a point-in-time market prior (``market_implied_yes``). This is
    exactly the population a taker policy would have executed immediately; the
    maker policy only fills the crossed subset of it.
    """
    from autonomy.correlation import group_key

    rows = conn.execute(
        """
        WITH per AS (
            SELECT decision_id,
                   MAX(CASE WHEN kind IN ('SHADOW','ACCEPTED') THEN 1 ELSE 0 END) AS submitted,
                   MAX(fill_count) AS filled_count,
                   MIN(CASE WHEN kind IN ('SHADOW','ACCEPTED') THEN created_at END) AS submitted_at,
                   MAX(CASE WHEN kind='SHADOW' THEN 1 ELSE 0 END) AS is_shadow,
                   MAX(broker_contacted) AS is_live
            FROM outcomes GROUP BY decision_id
        ), first_fill AS (
            SELECT o.decision_id, o.created_at AS fill_recorded_at,
                   o.fill_price_cents, o.detail
            FROM outcomes o
            WHERE o.id = (SELECT MIN(o2.id) FROM outcomes o2
                          WHERE o2.decision_id = o.decision_id AND o2.fill_count > 0)
        ), settled AS (
            SELECT o.decision_id, o.pnl_cents, o.fill_count AS settled_fill_count
            FROM outcomes o
            WHERE o.kind IN ('SETTLED_WIN','SETTLED_LOSS') AND o.pnl_cents IS NOT NULL
              AND EXISTS (SELECT 1 FROM outcomes f
                          WHERE f.decision_id = o.decision_id AND f.id < o.id
                            AND f.fill_count > 0)
        )
        SELECT d.decision_id, d.market_ticker, d.side, d.price_cents, d.count,
               d.probability_yes, d.market_implied_yes, s.result_yes,
               per.filled_count, per.submitted_at, per.is_shadow, per.is_live,
               ff.fill_recorded_at, ff.fill_price_cents, ff.detail,
               settled.pnl_cents, settled.settled_fill_count
        FROM decisions d
        JOIN per ON per.decision_id = d.decision_id
        JOIN settlements s ON s.market_ticker = d.market_ticker
        LEFT JOIN first_fill ff ON ff.decision_id = d.decision_id
        LEFT JOIN settled ON settled.decision_id = d.decision_id
        WHERE d.action != 'ABSTAIN' AND per.submitted = 1
          AND d.market_implied_yes IS NOT NULL
        ORDER BY per.submitted_at, d.decision_id
        """
    ).fetchall()

    out: list[dict[str, Any]] = []
    for record in rows:
        (decision_id, ticker, side, price_cents, count, forecast, market, result,
         filled_count, submitted_at, is_shadow, is_live, fill_recorded_at,
         fill_price_cents, detail_raw, pnl_cents, settled_fill_count) = record
        if not (0.0 < float(forecast) < 1.0 and 0.0 < float(market) < 1.0):
            continue
        filled = int(filled_count or 0) > 0
        try:
            detail = json.loads(detail_raw or "{}")
        except (TypeError, ValueError):
            detail = {}
        witness_at = (
            detail.get("fill_witness_at")
            or detail.get("trade_created_time")
        )
        if witness_at is None and detail.get("candle_end_ts") is not None:
            try:
                witness_at = datetime.fromtimestamp(
                    float(detail["candle_end_ts"]), timezone.utc,
                ).isoformat()
            except (TypeError, ValueError, OSError):
                witness_at = None
        submitted_dt = _parse_dt(submitted_at)
        witness_dt = _parse_dt(witness_at) or _parse_dt(fill_recorded_at)
        delay_seconds = None
        if filled and submitted_dt is not None and witness_dt is not None:
            delay_seconds = max(0.0, (witness_dt - submitted_dt).total_seconds())
        side = str(side)
        # Observed print through our resting quote, when the fill witness
        # captured it: how far the book travelled past our price (adverse
        # depth). Recorded as a YES-frame ask in cents.
        observed_cross = None
        if detail.get("observed_ask_cents") is not None:
            observed_cross = float(detail["observed_ask_cents"])
        elif detail.get("observed_ask_dollars") is not None:
            observed_cross = float(detail["observed_ask_dollars"]) * 100.0
        elif detail.get("trade_price_cents") is not None:
            observed_cross = float(detail["trade_price_cents"])
        out.append({
            "decision_id": str(decision_id),
            "ticker": str(ticker),
            "cluster": group_key(str(ticker)),
            "side": side,
            "price_cents": int(price_cents),
            "count": max(1, int(count or 1)),
            "forecast": float(forecast),
            "market": float(market),
            "result": int(result),
            "filled": filled,
            "submitted_at": str(submitted_at) if submitted_at is not None else None,
            "fill_price_cents": int(fill_price_cents) if fill_price_cents is not None else None,
            "delay_seconds": delay_seconds,
            "observed_cross_cents": observed_cross,
            "realized_pnl_cents": int(pnl_cents) if pnl_cents is not None else None,
            "settled_fill_count": int(settled_fill_count) if settled_fill_count is not None else None,
            "book": "shadow" if int(is_shadow or 0) else ("live" if int(is_live or 0) else "unknown"),
        })
    return out


# --------------------------------------------------------------------------- #
# Forecast skill (Brier / ECE) with cluster-robust edge CI
# --------------------------------------------------------------------------- #


def _forecast_metrics(rows: list[dict[str, Any]], *, seed: str) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "event_clusters": 0}
    forecast_briers = [_brier(r["forecast"], r["result"]) for r in rows]
    market_briers = [_brier(r["market"], r["result"]) for r in rows]
    forecast_brier = sum(forecast_briers) / len(rows)
    market_brier = sum(market_briers) / len(rows)
    bins = [[0.0, 0.0, 0.0] for _ in range(CALIBRATION_BINS)]
    for r in rows:
        p = r["forecast"]
        b = min(CALIBRATION_BINS - 1, int(p * CALIBRATION_BINS))
        bins[b][0] += 1
        bins[b][1] += p
        bins[b][2] += r["result"]
    ece_sum = 0.0
    max_ce = 0.0
    for cnt, sum_p, sum_o in bins:
        if cnt:
            gap = abs(sum_p / cnt - sum_o / cnt)
            ece_sum += cnt * gap
            max_ce = max(max_ce, gap)
    edge_by_cluster: dict[str, list[float]] = {}
    for r, mb, fb in zip(rows, market_briers, forecast_briers):
        edge_by_cluster.setdefault(r["cluster"], []).append(mb - fb)
    return {
        "n": len(rows),
        "event_clusters": len({r["cluster"] for r in rows}),
        "outcome_prevalence": round(sum(r["result"] for r in rows) / len(rows), 6),
        "forecast_brier": round(forecast_brier, 6),
        "market_brier": round(market_brier, 6),
        "brier_skill_vs_market": (
            round(1.0 - forecast_brier / market_brier, 6) if market_brier > 0 else None
        ),
        "expected_calibration_error": round(ece_sum / len(rows), 6),
        "maximum_calibration_error": round(max_ce, 6),
        "cluster_robust_brier_edge_vs_market": _cluster_ci(edge_by_cluster, seed=seed),
    }


# --------------------------------------------------------------------------- #
# P&L accounting (maker realized truth + per-contract counterfactuals)
# --------------------------------------------------------------------------- #


def _pnl_summary(trades: list[dict[str, Any]], *, seed: str) -> dict[str, Any]:
    if not trades:
        return {"trades": 0, "net_pnl_cents": 0, "win_rate": None}
    pnl_by_cluster: dict[str, list[float]] = {}
    for t in trades:
        pnl_by_cluster.setdefault(t["cluster"], []).append(float(t["pnl_cents"]))
    net = sum(int(t["pnl_cents"]) for t in trades)
    cost = sum(int(t["cost_cents"]) for t in trades)
    wins = sum(1 for t in trades if t["won"])
    return {
        "trades": len(trades),
        "contracts": sum(int(t.get("contracts", 1)) for t in trades),
        "event_clusters": len(pnl_by_cluster),
        "net_pnl_cents": net,
        "entry_cost_cents": cost,
        "win_rate": round(wins / len(trades), 6),
        "average_pnl_cents": round(net / len(trades), 4),
        "roi_on_entry_cost": round(net / cost, 6) if cost else None,
        "cluster_robust_mean_pnl_ci95": _cluster_ci(pnl_by_cluster, seed=seed),
    }


def _maker_realized_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ground-truth realized maker P&L for settled fills (multi-contract)."""
    trades = []
    for r in rows:
        if r["realized_pnl_cents"] is None:
            continue
        contracts = r["settled_fill_count"] or r["count"]
        trades.append({
            "cluster": r["cluster"],
            "pnl_cents": int(r["realized_pnl_cents"]),
            "cost_cents": int(r["price_cents"]) * max(1, int(contracts)),
            "won": int(r["realized_pnl_cents"]) > 0,
            "contracts": max(1, int(contracts)),
        })
    return trades


def _maker_sim_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-contract maker sim at the recorded fill price, maker fee.

    Normalized to one contract so it is directly comparable to the taker
    counterfactual (which cannot know the size a taker policy would have run).
    """
    trades = []
    for r in rows:
        if not r["filled"]:
            continue
        price = r["fill_price_cents"] if r["fill_price_cents"] is not None else r["price_cents"]
        price = max(1, min(99, int(price)))
        won = bool(r["result"]) if r["side"] == "yes" else (not bool(r["result"]))
        fee = kalshi_maker_fee_cents(price, 1, r["ticker"])
        trades.append({
            "cluster": r["cluster"],
            "pnl_cents": (100 - price if won else -price) - fee,
            "cost_cents": price + fee,
            "won": won,
            "contracts": 1,
        })
    return trades


def _taker_sim_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-contract taker counterfactual: cross at the recorded market mid.

    A taker fills immediately at decision time, so it executes the WHOLE
    actionable set (no maker fill selection) but pays the taker fee and the
    half-spread implicit in crossing to the midpoint. This is the same
    conservative mid-taker convention the backtest's threshold simulation
    uses; it never assumes a resting maker quote would have filled.
    """
    trades = []
    for r in rows:
        price = round(r["market"] * 100.0) if r["side"] == "yes" else round((1.0 - r["market"]) * 100.0)
        price = max(1, min(99, int(price)))
        won = bool(r["result"]) if r["side"] == "yes" else (not bool(r["result"]))
        fee = kalshi_taker_fee_cents(price, 1, r["ticker"])
        trades.append({
            "cluster": r["cluster"],
            "pnl_cents": (100 - price if won else -price) - fee,
            "cost_cents": price + fee,
            "won": won,
            "contracts": 1,
        })
    return trades


# --------------------------------------------------------------------------- #
# Adverse-selection metrics
# --------------------------------------------------------------------------- #


def _slippage_stats(filled: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-fill slippage: signal_price - fill_price and market_price - fill_price.

    ``signal_price`` is the model's fair value for the traded side in cents;
    ``market_price`` is the contemporaneous market prior for that side. A large
    positive model slippage next to a near-zero market slippage is the tell:
    the model believes it is buying a bargain while the market prices the fill
    fairly -- the maker "edge" is informational adverse selection, not value.
    """
    model_slip: list[float] = []
    market_slip: list[float] = []
    model_by_cluster: dict[str, list[float]] = {}
    market_by_cluster: dict[str, list[float]] = {}
    slip_won: list[float] = []
    slip_lost: list[float] = []
    for r in filled:
        fill_price = r["fill_price_cents"] if r["fill_price_cents"] is not None else r["price_cents"]
        if r["side"] == "yes":
            signal_price = r["forecast"] * 100.0
            market_price = r["market"] * 100.0
        else:
            signal_price = (1.0 - r["forecast"]) * 100.0
            market_price = (1.0 - r["market"]) * 100.0
        ms = signal_price - fill_price
        ks = market_price - fill_price
        model_slip.append(ms)
        market_slip.append(ks)
        model_by_cluster.setdefault(r["cluster"], []).append(ms)
        market_by_cluster.setdefault(r["cluster"], []).append(ks)
        if r["realized_pnl_cents"] is not None:
            (slip_won if int(r["realized_pnl_cents"]) > 0 else slip_lost).append(ms)
    if not model_slip:
        return {"fills": 0}
    return {
        "fills": len(model_slip),
        "model_slippage_cents": {
            "mean": round(sum(model_slip) / len(model_slip), 4),
            "median": round(float(_percentile(model_slip, 0.5) or 0.0), 4),
            "p10": round(float(_percentile(model_slip, 0.10) or 0.0), 4),
            "p90": round(float(_percentile(model_slip, 0.90) or 0.0), 4),
            "cluster_robust_mean_ci95": _cluster_ci(model_by_cluster, seed="slip-model"),
        },
        "market_slippage_cents": {
            "mean": round(sum(market_slip) / len(market_slip), 4),
            "median": round(float(_percentile(market_slip, 0.5) or 0.0), 4),
            "p10": round(float(_percentile(market_slip, 0.10) or 0.0), 4),
            "p90": round(float(_percentile(market_slip, 0.90) or 0.0), 4),
            "cluster_robust_mean_ci95": _cluster_ci(market_by_cluster, seed="slip-market"),
        },
        "mean_model_slippage_on_winning_fills": (
            round(sum(slip_won) / len(slip_won), 4) if slip_won else None
        ),
        "mean_model_slippage_on_losing_fills": (
            round(sum(slip_lost) / len(slip_lost), 4) if slip_lost else None
        ),
        "definition": (
            "signal_price = model fair value for the traded side (cents); "
            "market_price = contemporaneous market prior for the side; "
            "slippage = price - fill_price (positive = filled below fair)."
        ),
    }


def _fill_vs_nofill_delta(
    filled: list[dict[str, Any]], unfilled: list[dict[str, Any]],
) -> dict[str, Any]:
    """The direct adverse-selection number: skill on filled vs unfilled.

    If the model is systematically worse on the emissions that FILL than on
    the emissions that do not, the fill mechanism is selecting the model's
    errors -- adverse selection, quantified.
    """
    def cluster_brier(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
        by_cluster: dict[str, list[float]] = {}
        for r in rows:
            by_cluster.setdefault(r["cluster"], []).append(_brier(r["forecast"], r["result"]))
        return by_cluster

    def cluster_edge(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
        by_cluster: dict[str, list[float]] = {}
        for r in rows:
            by_cluster.setdefault(r["cluster"], []).append(
                _brier(r["market"], r["result"]) - _brier(r["forecast"], r["result"])
            )
        return by_cluster

    filled_brier = (
        sum(_brier(r["forecast"], r["result"]) for r in filled) / len(filled)
        if filled else None
    )
    unfilled_brier = (
        sum(_brier(r["forecast"], r["result"]) for r in unfilled) / len(unfilled)
        if unfilled else None
    )
    return {
        "filled_n": len(filled),
        "unfilled_n": len(unfilled),
        "filled_forecast_brier": round(filled_brier, 6) if filled_brier is not None else None,
        "unfilled_forecast_brier": round(unfilled_brier, 6) if unfilled_brier is not None else None,
        "filled_minus_unfilled_brier": (
            round(filled_brier - unfilled_brier, 6)
            if filled_brier is not None and unfilled_brier is not None else None
        ),
        "filled_cluster_robust_brier_edge_vs_market": _cluster_ci(
            cluster_edge(filled), seed="delta-filled-edge",
        ),
        "unfilled_cluster_robust_brier_edge_vs_market": _cluster_ci(
            cluster_edge(unfilled), seed="delta-unfilled-edge",
        ),
        "interpretation": (
            "A higher filled_forecast_brier than unfilled, and a filled edge "
            "vs market whose CI sits below the unfilled edge, is direct "
            "evidence the fill mechanism selects the model's errors."
        ),
    }


def _time_to_fill_vs_move(settled_fills: list[dict[str, Any]]) -> dict[str, Any]:
    """Time-to-fill distribution against the subsequent realized move.

    ``market_cross_depth_cents`` measures how far the book printed through our
    resting quote at the witnessed fill (limit - observed print, YES-frame):
    a deeper cross means the market had already moved further against us by the
    time we filled. Bucketed P&L / win-rate by fill latency shows whether the
    fills we wait longest for (the market travelling to us) settle worst.
    """
    delays = [r["delay_seconds"] for r in settled_fills if r["delay_seconds"] is not None]
    cross_depths: list[float] = []
    for r in settled_fills:
        if r["observed_cross_cents"] is None or r["fill_price_cents"] is None:
            continue
        limit = r["fill_price_cents"]
        observed = r["observed_cross_cents"]
        # YES-frame: a buy-yes fills when the yes ask drops to/under our limit,
        # so depth = limit - observed. Buy-no fills on a yes-bid rise; the
        # detail already stores the crossing print in the traded frame where
        # available, so limit - observed is the adverse depth in both frames.
        cross_depths.append(float(limit) - float(observed))
    buckets = []
    for label, low, high in _TTF_BUCKETS:
        members = [
            r for r in settled_fills
            if r["delay_seconds"] is not None and low <= r["delay_seconds"] < high
        ]
        # Unknown-latency settled fills fall into the slow bucket (they are the
        # oldest, candle-witnessed fills) rather than being silently dropped.
        if label == _TTF_BUCKETS[-1][0]:
            members += [r for r in settled_fills if r["delay_seconds"] is None]
        pnl_by_cluster: dict[str, list[float]] = {}
        for r in members:
            if r["realized_pnl_cents"] is not None:
                pnl_by_cluster.setdefault(r["cluster"], []).append(float(r["realized_pnl_cents"]))
        settled = [r for r in members if r["realized_pnl_cents"] is not None]
        member_delays = [r["delay_seconds"] for r in members if r["delay_seconds"] is not None]
        buckets.append({
            "bucket": label,
            "fills": len(members),
            "settled_fills": len(settled),
            "net_pnl_cents": sum(int(r["realized_pnl_cents"]) for r in settled),
            "win_rate": (
                round(sum(1 for r in settled if int(r["realized_pnl_cents"]) > 0) / len(settled), 6)
                if settled else None
            ),
            "median_delay_seconds": (
                round(float(_percentile(member_delays, 0.5)), 2) if member_delays else None
            ),
            "cluster_robust_mean_pnl_ci95": _cluster_ci(pnl_by_cluster, seed=f"ttf-{label}"),
        })
    return {
        "delay_seconds": {
            "n": len(delays),
            "mean": round(sum(delays) / len(delays), 2) if delays else None,
            "median": round(float(_percentile(delays, 0.5)), 2) if delays else None,
            "p90": round(float(_percentile(delays, 0.9)), 2) if delays else None,
        },
        "market_cross_depth_cents": {
            "n": len(cross_depths),
            "mean": round(sum(cross_depths) / len(cross_depths), 4) if cross_depths else None,
            "median": round(float(_percentile(cross_depths, 0.5)), 4) if cross_depths else None,
            "note": (
                "limit - observed crossing print (YES-frame cents); larger = the "
                "book travelled further through our quote before we filled."
            ),
        },
        "by_latency_bucket": buckets,
    }


# --------------------------------------------------------------------------- #
# Top-level report
# --------------------------------------------------------------------------- #

REPORT_NAME = "EXECUTION_ADVERSE_SELECTION"
DEFAULT_ADVERSE_SELECTION_PATH = Path("runtime/autonomy/adverse_selection.json")
ADVERSE_SELECTION_EVIDENCE_MAX_AGE_HOURS = 24.0


@dataclass(frozen=True)
class MakerAdverseSelectionEvidence:
    """Fresh, cluster-based fill-information cost for maker EV.

    ``haircut_cents`` is the observed unfilled-minus-filled Brier edge, placed
    on the contract-cent scale.  It is never negative: evidence that does not
    show adverse selection cannot manufacture maker alpha.
    """

    haircut_cents: float
    generated_at: str
    source_report_sha256: str
    filled_clusters: int
    unfilled_clusters: int

    def __post_init__(self) -> None:
        digest = str(self.source_report_sha256)
        if (
            not math.isfinite(float(self.haircut_cents))
            or not 0.0 <= float(self.haircut_cents) <= 100.0
            or self.filled_clusters < 1
            or self.unfilled_clusters < 1
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("invalid maker adverse-selection evidence")


def load_maker_adverse_selection_evidence(
    path: Path = DEFAULT_ADVERSE_SELECTION_PATH,
    *,
    now: datetime | None = None,
    max_age_hours: float = ADVERSE_SELECTION_EVIDENCE_MAX_AGE_HOURS,
) -> MakerAdverseSelectionEvidence | None:
    """Load a fresh measured maker haircut, or ``None`` on any evidence gap.

    The report is measurement, not execution authority.  This loader only
    converts its already-defined cluster means into a non-negative EV cost;
    the allocator decides whether missing evidence must abstain.  No point
    estimate is inferred when the report, timestamps, or cluster diagnostics
    are absent or malformed.
    """

    try:
        raw_bytes = Path(path).read_bytes()
        payload = json.loads(raw_bytes)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("report_name") != REPORT_NAME:
        return None
    try:
        generated = datetime.fromisoformat(
            str(payload["generated_at"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError):
        return None
    if generated.tzinfo is None:
        return None
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        return None
    observed_now = observed_now.astimezone(timezone.utc)
    generated = generated.astimezone(timezone.utc)
    try:
        resolved_max_age = float(max_age_hours)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(resolved_max_age) or resolved_max_age < 0.0:
        return None
    if (
        generated > observed_now + timedelta(minutes=5)
        or observed_now - generated
        > timedelta(hours=resolved_max_age)
    ):
        return None
    try:
        delta = payload["adverse_selection_metrics"][
            "fill_vs_nofill_outcome_delta"
        ]
        filled = delta["filled_cluster_robust_brier_edge_vs_market"]
        unfilled = delta["unfilled_cluster_robust_brier_edge_vs_market"]
        filled_mean = float(filled["mean"])
        unfilled_mean = float(unfilled["mean"])
        filled_clusters = int(filled["clusters"])
        unfilled_clusters = int(unfilled["clusters"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not math.isfinite(filled_mean)
        or not math.isfinite(unfilled_mean)
        or not -1.0 <= filled_mean <= 1.0
        or not -1.0 <= unfilled_mean <= 1.0
        or filled_clusters < 1
        or unfilled_clusters < 1
        or filled.get("method") != "event_cluster_bootstrap_95"
        or unfilled.get("method") != "event_cluster_bootstrap_95"
    ):
        return None
    haircut_cents = min(
        100.0,
        max(0.0, (unfilled_mean - filled_mean) * 100.0),
    )
    return MakerAdverseSelectionEvidence(
        haircut_cents=round(haircut_cents, 6),
        generated_at=generated.isoformat(),
        source_report_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        filled_clusters=filled_clusters,
        unfilled_clusters=unfilled_clusters,
    )


def adverse_selection_report(conn: sqlite3.Connection) -> dict[str, Any]:
    """First-class adverse-selection diagnostic over the ledger (read-only)."""
    rows = load_execution_rows(conn)
    if not rows:
        return {
            "report_name": REPORT_NAME,
            "actionable_settled_decisions": 0,
            "note": "no submitted, settled, non-abstain decisions with a market prior",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    filled = [r for r in rows if r["filled"]]
    unfilled = [r for r in rows if not r["filled"]]
    settled_fills = [r for r in filled if r["realized_pnl_cents"] is not None]

    full_metrics = _forecast_metrics(rows, seed="surface-full")
    maker_metrics = _forecast_metrics(filled, seed="surface-maker")
    unfilled_metrics = _forecast_metrics(unfilled, seed="surface-unfilled")

    maker_realized = _pnl_summary(_maker_realized_trades(settled_fills), seed="pnl-maker-realized")
    maker_sim = _pnl_summary(_maker_sim_trades(filled), seed="pnl-maker-sim")
    taker_filled = _pnl_summary(_taker_sim_trades(filled), seed="pnl-taker-filled")
    taker_all = _pnl_summary(_taker_sim_trades(rows), seed="pnl-taker-all")

    fill_delta = _fill_vs_nofill_delta(filled, unfilled)

    report = {
        "report_name": REPORT_NAME,
        "selection": "actionable_submitted_settled_decisions",
        "actionable_settled_decisions": len(rows),
        "maker_filled_decisions": len(filled),
        "unfilled_decisions": len(unfilled),
        "settled_fills": len(settled_fills),
        "event_clusters": len({r["cluster"] for r in rows}),
        "fill_conditioned_slice": {
            "full_surface_actionable": {
                **full_metrics,
                "taker_execution_per_contract": taker_all,
            },
            "maker_filled": {
                **maker_metrics,
                "maker_execution_realized": maker_realized,
                "maker_execution_per_contract_sim": maker_sim,
                "taker_execution_per_contract_same_subset": taker_filled,
            },
            "unfilled": unfilled_metrics,
            "note": (
                "maker_filled is the crossed subset the maker policy actually "
                "fills; taker_execution_per_contract on full_surface_actionable "
                "is what a cross-immediately policy would realize over the whole "
                "actionable set. Realized maker P&L is multi-contract ground "
                "truth; the *_per_contract_* rows normalize to one contract for a "
                "like-for-like maker-vs-taker comparison."
            ),
        },
        "adverse_selection_metrics": {
            "fill_vs_nofill_outcome_delta": fill_delta,
            "per_fill_slippage": _slippage_stats(filled),
            "time_to_fill_vs_market_move": _time_to_fill_vs_move(settled_fills),
            "all_intervals_are_cluster_level": True,
        },
        "headline": {
            "maker_fill_conditioned_brier_skill_vs_market": maker_metrics.get("brier_skill_vs_market"),
            "maker_fill_conditioned_ece": maker_metrics.get("expected_calibration_error"),
            "taker_full_surface_brier_skill_vs_market": full_metrics.get("brier_skill_vs_market"),
            "maker_realized_net_pnl_cents": maker_realized.get("net_pnl_cents"),
            "maker_realized_win_rate": maker_realized.get("win_rate"),
            "taker_full_surface_net_pnl_cents": taker_all.get("net_pnl_cents"),
            "taker_full_surface_mean_pnl_cents_per_contract": taker_all.get(
                "average_pnl_cents"
            ),
            "taker_full_surface_win_rate": taker_all.get("win_rate"),
            "fill_vs_nofill_brier_gap": fill_delta.get("filled_minus_unfilled_brier"),
        },
        "caveat": (
            "Read-only measurement, not a policy authorization. The maker-filled "
            "population is selection-biased by construction; that selection IS the "
            "quantity under study. Sample is small -- read the cluster-level "
            "intervals, not the point estimates, and never a per-emission CI."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return report


def write_report(report: dict[str, Any], path: Path) -> None:
    """Atomic JSON write, matching the loss-engine / miner artifact pattern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
