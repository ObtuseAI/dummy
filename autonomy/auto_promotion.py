"""Autonomous thresholded promotion — the ladder that earns fusion membership.

Automatic promotion is permitted only after predictive gates and independently
verified forward witnessed-fill evidence clear. Counterfactual diagnostics can
never create fusion authority. This module is that fail-closed decision engine.

Scope of authority (read this before anything else):

  * This engine changes FUSION MEMBERSHIP ONLY — which challenger scopes the
    ``EnsembleForecaster`` blends, and at what weight. It has NO live-trading
    authority. ``configs/live_submit.json``, the second-proof sequence, and
    session live auth remain operator-gated and are never touched here.
  * DEMOTION always beats promotion: de-risking is instant and uncapped;
    adding risk is rate-limited, rail-guarded, and must clear every gate.
  * FAIL-CLOSED everywhere: missing evidence, a stale artifact, a broken ledger
    chain, or any rail trip aborts the whole run and promotes nobody.

The ladder (per exact ``source|subject|market_type|horizon`` scope):

  STAGE 1 (probation, capped fusion weight = ``STAGE1_WEIGHT_FRACTION`` of the
  scope's earned trust). ALL of:
    (a) contested clusters >= MIN_CLUSTERS and evidence span >= MIN_SPAN_DAYS;
    (b) cluster-robust contested Brier-edge-vs-market CI95 lower > 0 AND
        contested beat_rate >= MIN_BEAT_RATE;
    (c) a positive fee-adjusted midpoint/maker counterfactual, retained only as
        a diagnostic filter and never treated as fill or profit proof;
    (d) not degrading (trailing-window edge floor);
    (e) CLV mean CI lower > 0 where CLV records exist; a scope with no CLV
        instrumentation may pass without it but needs MIN_CLUSTERS_NO_CLV;
    (f) receipt-bounded, post-registration, isolated witnessed-fill net P&L
        over enough independent event clusters, with cluster-bootstrap CI95
        lower > 0. This is the only automatic-promotion profit evidence;
    (g) correlation guard: emission correlation vs every already-fused source on
        overlapping markets <= CORRELATION_CAP. Exceeded => NOT added, flagged
        as a replacement candidate only (report, no action).
    A scope originating from a strategy-miner family applies a Bonferroni
    multiple-testing widening to the Brier-edge CI before the (b) comparison.

  STAGE 2 (full weight). A promoted scope accrues realized paper/shadow trade
  attribution; it escalates when it has >= STAGE2_MIN_TRADES settled scope-
  attributed trades whose realized-P&L cluster CI95 lower > 0.

  DEMOTION applies at both stages, instantly, on the looser trailing breach
  (CI95 UPPER < 0). The promote>0 / demote<0 asymmetry is deliberate hysteresis
  so a scope on the boundary does not churn.

Determinism: the same inputs always yield the same decisions. Bootstraps are
seeded by scope; nothing consults a wall clock except through the injected
``now_ts`` / ``now_iso``.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from autonomy.fees import kalshi_maker_fee_cents
from autonomy.promotion import (
    DEGRADE_EDGE_FLOOR,
    DEGRADE_TRAIL_CLUSTERS,
    DEMOTE_TRAIL_CLUSTERS,
    cluster_series,
)
from autonomy.stats import mean_ci95
from autonomy.strategy_miner import _brier_edge

# --------------------------------------------------------------------------
# Thresholds (auditable; a single ``PromotionConfig`` renders them for docs and
# lets tests exercise the ladder without giant fixtures).
# --------------------------------------------------------------------------

CONTESTED_DISAGREEMENT = 0.05      # matches autonomy/backtest.py
STAGE1_WEIGHT_FRACTION = 0.25      # probation cap: 25% of the scope's trust
STAGE2_WEIGHT_FRACTION = 1.0       # full weight
MIN_CLUSTERS = 300                 # contested event-clusters for stage 1
MIN_CLUSTERS_NO_CLV = 450          # required instead when no CLV instrumentation
MIN_SPAN_DAYS = 7.0                # evidence span (owner-set 2026-07-16; was 14)
MIN_BEAT_RATE = 0.55               # contested beat-rate floor
CORRELATION_CAP = 0.8              # vs any already-fused source on shared markets
MIN_CORR_OVERLAP = 5               # shared markets needed to trust a correlation
MAX_PROMOTIONS_PER_DAY = 2         # combined promotions + escalations per UTC day
STAGE2_MIN_TRADES = 50             # realized scope-attributed trades to escalate
STAGE1_MIN_FORWARD_TRADES = 50     # witnessed isolated fills after registration
STAGE1_MIN_FORWARD_CLUSTERS = 30   # independent event clusters, not emissions
STAGE1_MIN_FORWARD_SPAN_DAYS = 7.0 # forward evidence cannot be one burst
ARTIFACT_STALE_HOURS = 24.0        # evidence artifacts older than this abort a run
BOOTSTRAP_SAMPLES = 1000           # matches autonomy/backtest.py
FORWARD_EVIDENCE_VERSION = "promotion_forward_fill_v1"


@dataclass(frozen=True)
class PromotionConfig:
    stage1_weight_fraction: float = STAGE1_WEIGHT_FRACTION
    stage2_weight_fraction: float = STAGE2_WEIGHT_FRACTION
    min_clusters: int = MIN_CLUSTERS
    min_clusters_no_clv: int = MIN_CLUSTERS_NO_CLV
    min_span_days: float = MIN_SPAN_DAYS
    min_beat_rate: float = MIN_BEAT_RATE
    correlation_cap: float = CORRELATION_CAP
    min_corr_overlap: int = MIN_CORR_OVERLAP
    max_promotions_per_day: int = MAX_PROMOTIONS_PER_DAY
    stage2_min_trades: int = STAGE2_MIN_TRADES
    stage1_min_forward_trades: int = STAGE1_MIN_FORWARD_TRADES
    stage1_min_forward_clusters: int = STAGE1_MIN_FORWARD_CLUSTERS
    stage1_min_forward_span_days: float = STAGE1_MIN_FORWARD_SPAN_DAYS
    contested_disagreement: float = CONTESTED_DISAGREEMENT
    # Counterfactual ROI is retained as a research diagnostic only. It can
    # nominate a human-review candidate, but can never add fusion authority.
    roi_path_min_roi: float = 0.05
    roi_path_min_clusters: int = 200
    roi_path_min_span_days: float = 7.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage1_weight_fraction": self.stage1_weight_fraction,
            "stage2_weight_fraction": self.stage2_weight_fraction,
            "min_clusters": self.min_clusters,
            "min_clusters_no_clv": self.min_clusters_no_clv,
            "min_span_days": self.min_span_days,
            "min_beat_rate": self.min_beat_rate,
            "correlation_cap": self.correlation_cap,
            "min_corr_overlap": self.min_corr_overlap,
            "max_promotions_per_day": self.max_promotions_per_day,
            "stage2_min_trades": self.stage2_min_trades,
            "stage1_min_forward_trades": self.stage1_min_forward_trades,
            "stage1_min_forward_clusters": self.stage1_min_forward_clusters,
            "stage1_min_forward_span_days": self.stage1_min_forward_span_days,
            "contested_disagreement": self.contested_disagreement,
            "roi_path_min_roi": self.roi_path_min_roi,
            "roi_path_min_clusters": self.roi_path_min_clusters,
            "roi_path_min_span_days": self.roi_path_min_span_days,
        }


DEFAULT_CONFIG = PromotionConfig()


# --------------------------------------------------------------------------
# Counterfactual P&L (fee-adjusted) — diagnostic only, never fill evidence.
# --------------------------------------------------------------------------

def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def counterfactual_pnl(row: Any) -> float:
    """Diagnostic fee-adjusted counterfactual in dollars for one emission.

    A unit (1-contract) counterfactual: enter the side the model favors versus
    the market at the recorded market price at emission time
    (``market_probability``), pay the Kalshi maker fee, hold to settlement.

      * side = YES when the model prices above the market, else NO;
      * entry cost = market price of that side (YES: p; NO: 1-p);
      * payoff = 1 if the side wins at settlement, else 0;
      * net = payoff - entry_cost - maker_fee.

    This assumes a maker fill at a recorded market probability. It is not a
    witnessed fill, executable quote, or realized-profit claim and therefore
    has no automatic-promotion authority. The formula is retained for research
    comparison and as a conservative additional filter once real forward fill
    evidence independently passes.
    """
    market_p = _clamp01(row.market_probability)
    model_p = float(row.probability_yes)
    side_yes = model_p >= market_p
    entry_cost = market_p if side_yes else (1.0 - market_p)
    result = 1.0 if bool(row.result_yes) else 0.0
    payoff = result if side_yes else (1.0 - result)
    price_cents = min(99, max(1, round(market_p * 100)))
    fee = kalshi_maker_fee_cents(price_cents, 1, getattr(row, "ticker", None)) / 100.0
    return (payoff - entry_cost) - fee


def _is_contested(row: Any, disagreement: float) -> bool:
    return abs(float(row.probability_yes) - _clamp01(row.market_probability)) >= disagreement


# --------------------------------------------------------------------------
# Deterministic cluster bootstrap with an optional Bonferroni family widening.
# --------------------------------------------------------------------------

def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def cluster_bootstrap_ci(
    values_by_cluster: Mapping[str, list[float]],
    *,
    seed: str,
    family_size: int = 1,
) -> dict[str, Any] | None:
    """Cluster-resampled mean with a two-sided CI, family-size adjustable.

    Correlated emissions inside one event cluster share a settlement print, so
    the CLUSTER is the resampling unit (never the per-emission value). With
    ``family_size > 1`` the interval widens by a Bonferroni correction: the
    lower/upper tails are taken at ``0.025 / family_size`` so a scope mined from
    a family of N tested rules is not credited for a lucky member. Deterministic:
    the resample stream is seeded only by ``seed``.
    """
    aggregates = [
        (sum(values), len(values)) for values in values_by_cluster.values() if values
    ]
    if not aggregates:
        return None
    total_sum = sum(total for total, _n in aggregates)
    total_n = sum(n for _total, n in aggregates)
    observed = total_sum / total_n
    family = max(1, int(family_size))
    if len(aggregates) == 1:
        lower = upper = observed
    else:
        rng = random.Random(seed)
        samples: list[float] = []
        k = len(aggregates)
        for _ in range(BOOTSTRAP_SAMPLES):
            acc = 0.0
            n = 0
            for _ in range(k):
                sampled_total, sampled_n = aggregates[rng.randrange(k)]
                acc += sampled_total
                n += sampled_n
            samples.append(acc / n)
        alpha = 0.025 / family
        lower = _percentile(samples, alpha)
        upper = _percentile(samples, 1.0 - alpha)
    return {
        "mean": round(observed, 6),
        "lower": round(lower, 6),
        "upper": round(upper, 6),
        "clusters": len(aggregates),
        "family_size": family,
        "resamples": BOOTSTRAP_SAMPLES if len(aggregates) > 1 else 0,
        "method": "event_cluster_bootstrap_95",
    }


# --------------------------------------------------------------------------
# Correlation guard.
# --------------------------------------------------------------------------

def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return None  # a constant series has no linear correlation
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return sxy / (sxx ** 0.5 * syy ** 0.5)


def correlation_guard(
    source_probs: Mapping[str, float],
    fused_probs_by_source: Mapping[str, Mapping[str, float]],
    *,
    cap: float = CORRELATION_CAP,
    min_overlap: int = MIN_CORR_OVERLAP,
) -> dict[str, Any]:
    """Max emission correlation of a candidate vs each already-fused source.

    ``source_probs`` and each fused source map ticker -> representative
    probability. Correlation is computed only on OVERLAPPING tickers and only
    when the overlap is large enough to be meaningful (< ``min_overlap`` shared
    markets -> that pair is skipped, not treated as correlated). Returns the
    worst correlation, the source that produced it, and whether the cap held.
    """
    worst = 0.0
    worst_source: str | None = None
    for fused_source, fused in fused_probs_by_source.items():
        shared = [t for t in source_probs if t in fused]
        if len(shared) < min_overlap:
            continue
        r = _pearson([source_probs[t] for t in shared], [fused[t] for t in shared])
        if r is None:
            continue
        if abs(r) > abs(worst):
            worst = r
            worst_source = fused_source
    return {
        "max_correlation": round(worst, 4),
        "with_source": worst_source,
        "cap": cap,
        "ok": abs(worst) <= cap,
    }


# --------------------------------------------------------------------------
# Per-scope evidence dossier.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScopeEvidence:
    scope: str
    n_clusters: int
    n_contested_emissions: int
    span_days: float
    beat_rate: float | None
    brier_ci: dict[str, Any] | None
    pnl_ci: dict[str, Any] | None
    clv_ci: dict[str, Any] | None
    has_clv: bool
    trailing_degrade_mean: float | None
    degrading: bool
    correlation: dict[str, Any]
    family_size: int
    promotion_eligible: bool
    required_clusters: int
    # Thresholds captured at build time from the active PromotionConfig so the
    # dossier always reports the values that were actually compared.
    min_span_days: float = MIN_SPAN_DAYS
    min_beat_rate: float = MIN_BEAT_RATE

    def dossier(self) -> dict[str, Any]:
        """Full snapshot: every threshold beside the measured value.

        This is the audit record persisted verbatim to the hash-chained
        promotion ledger, so an auditor never has to re-derive why a scope
        cleared (or missed) any single criterion.
        """
        return {
            "scope": self.scope,
            "clusters": {
                "measured": self.n_clusters,
                "threshold": self.required_clusters,
                "pass": self.n_clusters >= self.required_clusters,
                "note": ("no CLV instrumentation -> higher cluster bar"
                         if not self.has_clv else "CLV present"),
            },
            "evidence_span_days": {
                "measured": round(self.span_days, 3),
                "threshold": self.min_span_days,
                "pass": self.span_days >= self.min_span_days,
            },
            "contested_brier_edge_ci95_lower": {
                "measured": (self.brier_ci or {}).get("lower"),
                "threshold": 0.0,
                "pass": bool(self.brier_ci and self.brier_ci["lower"] > 0.0),
                "family_size": self.family_size,
                "bonferroni_applied": self.family_size > 1,
            },
            "contested_beat_rate": {
                "measured": self.beat_rate,
                "threshold": self.min_beat_rate,
                "pass": (self.beat_rate is not None
                         and self.beat_rate >= self.min_beat_rate),
            },
            "counterfactual_pnl_ci95_lower": {
                "measured": (self.pnl_ci or {}).get("lower"),
                "threshold": 0.0,
                "pass": bool(self.pnl_ci and self.pnl_ci["lower"] > 0.0),
                "unit": "dollars_per_contract",
                "evidence_role": "diagnostic_midpoint_maker_counterfactual",
                "witnessed_fill_evidence": False,
                "automatic_promotion_authority": False,
            },
            "not_degrading": {
                "measured": self.trailing_degrade_mean,
                "threshold": DEGRADE_EDGE_FLOOR,
                "pass": not self.degrading,
            },
            "clv_ci95_lower": {
                "measured": (self.clv_ci or {}).get("lower") if self.has_clv else None,
                "requirement": ("clv_positive" if self.has_clv
                                else "clusters_ge_%d_no_clv" % self.required_clusters),
                "pass": self._clv_pass(),
            },
            "correlation_guard": {
                "measured": self.correlation.get("max_correlation"),
                "with_source": self.correlation.get("with_source"),
                "threshold": self.correlation.get("cap", CORRELATION_CAP),
                "pass": bool(self.correlation.get("ok")),
            },
            "promotion_eligible": {
                "measured": self.promotion_eligible,
                "pass": self.promotion_eligible,
            },
        }

    def _clv_pass(self) -> bool:
        if self.has_clv:
            return bool(self.clv_ci and self.clv_ci.get("lower") is not None
                        and self.clv_ci["lower"] > 0.0)
        # No CLV instrumentation: allowed, but the higher cluster bar (already
        # folded into required_clusters) stands in for the missing evidence.
        return True

    def evidence_pass(self) -> bool:
        """Every gate EXCEPT the correlation guard (which routes to replacement)."""
        d = self.dossier()
        keys = (
            "clusters", "evidence_span_days", "contested_brier_edge_ci95_lower",
            "contested_beat_rate", "counterfactual_pnl_ci95_lower",
            "not_degrading", "clv_ci95_lower", "promotion_eligible",
        )
        return all(d[k]["pass"] for k in keys)

    def failing_criteria(self) -> list[str]:
        d = self.dossier()
        return [k for k, v in d.items() if isinstance(v, dict) and v.get("pass") is False]


def roi_door_evidence(
    scope: str,
    rows: list[Any],
    *,
    config: PromotionConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Research-only ROI diagnostic; never an automatic-promotion route.

    Contested counterfactual record only (same disagreement bar as every
    other gate): per cluster, sum fee-adjusted net dollars and entry cost;
    scope ROI is the ratio of sums. The CI is a deterministic cluster-
    resampled RATIO bootstrap (resample clusters with replacement, ratio of
    the resampled sums), so correlated emissions inside one settlement never
    manufacture confidence. Pass requires volume, span, point ROI at the
    bar, and the CI floor strictly above zero.
    """
    import random

    contested = [
        r for r in rows if _is_contested(r, config.contested_disagreement)
    ]
    net_by_cluster: dict[str, float] = {}
    cost_by_cluster: dict[str, float] = {}
    timestamps: list[float] = []
    for r in contested:
        cluster = str(r.event_cluster)
        market_p = _clamp01(r.market_probability)
        side_yes = float(r.probability_yes) >= market_p
        entry_cost = market_p if side_yes else (1.0 - market_p)
        net_by_cluster[cluster] = net_by_cluster.get(cluster, 0.0) + counterfactual_pnl(r)
        cost_by_cluster[cluster] = cost_by_cluster.get(cluster, 0.0) + entry_cost
        ts = _row_ts(r)
        if ts is not None:
            timestamps.append(ts)

    clusters = sorted(net_by_cluster)
    n_clusters = len(clusters)
    span_days = ((max(timestamps) - min(timestamps)) / 86400.0) if timestamps else 0.0
    total_cost = sum(cost_by_cluster.values())
    roi = (sum(net_by_cluster.values()) / total_cost) if total_cost > 0 else None

    roi_ci: dict[str, Any] | None = None
    if roi is not None and n_clusters >= 2:
        rng = random.Random(f"roi_door:{scope}")
        ratios: list[float] = []
        for _ in range(1000):
            sample = [clusters[rng.randrange(n_clusters)] for _ in range(n_clusters)]
            cost = sum(cost_by_cluster[c] for c in sample)
            if cost <= 0:
                continue
            ratios.append(sum(net_by_cluster[c] for c in sample) / cost)
        if ratios:
            roi_ci = {
                "lower": round(_percentile(ratios, 0.025), 6),
                "upper": round(_percentile(ratios, 0.975), 6),
            }

    passed = (
        roi is not None
        and n_clusters >= config.roi_path_min_clusters
        and span_days >= config.roi_path_min_span_days
        and roi >= config.roi_path_min_roi
        and roi_ci is not None and (roi_ci.get("lower") or 0.0) > 0.0
    )
    return {
        "pass": bool(passed),
        "research_only": True,
        "witnessed_fill_evidence": False,
        "automatic_promotion_authority": False,
        "roi_on_entry_cost": round(roi, 6) if roi is not None else None,
        "roi_ci95": roi_ci,
        "threshold_roi": config.roi_path_min_roi,
        "n_clusters": n_clusters,
        "threshold_clusters": config.roi_path_min_clusters,
        "span_days": round(span_days, 3),
        "threshold_span_days": config.roi_path_min_span_days,
        "n_contested": len(contested),
    }


def _aware_timestamp(value: Any) -> float | None:
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    try:
        return parsed.timestamp()
    except (OSError, OverflowError, ValueError):
        return None


def forward_witnessed_fill_evidence(
    scope: str,
    realized: Mapping[str, Any] | None,
    *,
    config: PromotionConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Validate the only realized-P&L evidence allowed to auto-promote.

    The runner derives this payload from ledger rows with all of the following:
    a prior positive fill witness, one terminal net-P&L outcome, a signal whose
    claimed and receipt timestamps precede the decision, an isolated candidate
    decision, and an immutable candidate fingerprint registered before every
    scored decision. Self-attested or malformed payloads fail closed here too.
    """
    raw = (realized or {}).get("forward_evidence")
    base: dict[str, Any] = {
        "scope": scope,
        "evidence_version": FORWARD_EVIDENCE_VERSION,
        "pass": False,
        "automatic_promotion_authority": False,
        "n_trades": 0,
        "event_clusters": 0,
        "span_days": 0.0,
        "pnl_ci95": None,
        "failures": [],
    }
    if not isinstance(raw, Mapping):
        base["failures"] = ["missing_forward_witnessed_fill_evidence"]
        return base

    failures: list[str] = []
    required_truth = {
        "receipt_bounded": raw.get("receipt_bounded") is True,
        "witnessed_fill_net_pnl": raw.get("witnessed_fill_net_pnl") is True,
        "out_of_sample_after_registration": (
            raw.get("out_of_sample_after_registration") is True
        ),
        "isolated_candidate_decisions": raw.get("isolated_candidate_decisions") is True,
        "ledger_verified": raw.get("evidence_origin") == "ledger_verified",
        "version": raw.get("evidence_version") == FORWARD_EVIDENCE_VERSION,
    }
    failures.extend(name for name, passed in required_truth.items() if not passed)

    fingerprint = str(raw.get("candidate_fingerprint") or "").lower()
    if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        failures.append("invalid_candidate_fingerprint")
    registered_at = raw.get("registered_at")
    registered_ts = _aware_timestamp(registered_at)
    if registered_ts is None:
        failures.append("invalid_registration_timestamp")

    clean_clusters: dict[str, list[float]] = {}
    payload_clusters = raw.get("pnl_by_cluster")
    if isinstance(payload_clusters, Mapping):
        for cluster, values in payload_clusters.items():
            if not str(cluster).strip() or not isinstance(values, (list, tuple)):
                continue
            clean: list[float] = []
            for value in values:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(number):
                    clean.append(number)
            if clean:
                clean_clusters[str(cluster)] = clean
    counted_trades = sum(len(values) for values in clean_clusters.values())
    try:
        declared_trades = int(raw.get("n_trades", 0))
    except (TypeError, ValueError):
        declared_trades = 0
    if declared_trades != counted_trades:
        failures.append("trade_count_mismatch")

    raw_timestamps = raw.get("trade_timestamps")
    timestamps = (
        [_aware_timestamp(value) for value in raw_timestamps]
        if isinstance(raw_timestamps, (list, tuple))
        else []
    )
    if len(timestamps) != counted_trades or any(value is None for value in timestamps):
        failures.append("invalid_trade_timestamps")
        valid_timestamps: list[float] = []
    else:
        valid_timestamps = [float(value) for value in timestamps if value is not None]
    if registered_ts is not None and valid_timestamps and any(
        value <= registered_ts for value in valid_timestamps
    ):
        failures.append("not_strictly_forward_of_registration")

    span_days = (
        (max(valid_timestamps) - min(valid_timestamps)) / 86400.0
        if len(valid_timestamps) >= 2 else 0.0
    )
    ci = cluster_bootstrap_ci(clean_clusters, seed=f"forward-fill:{scope}")
    lower = (ci or {}).get("lower")
    clusters = len(clean_clusters)
    gates = {
        "minimum_trades": counted_trades >= config.stage1_min_forward_trades,
        "minimum_event_clusters": clusters >= config.stage1_min_forward_clusters,
        "minimum_span_days": span_days >= config.stage1_min_forward_span_days,
        "positive_cluster_ci95_lower": lower is not None and float(lower) > 0.0,
    }
    failures.extend(name for name, passed in gates.items() if not passed)
    passed = not failures
    return {
        **base,
        "pass": passed,
        "automatic_promotion_authority": passed,
        "candidate_fingerprint": fingerprint or None,
        "registered_at": registered_at,
        "n_trades": counted_trades,
        "minimum_trades": config.stage1_min_forward_trades,
        "event_clusters": clusters,
        "minimum_event_clusters": config.stage1_min_forward_clusters,
        "span_days": round(span_days, 6),
        "minimum_span_days": config.stage1_min_forward_span_days,
        "pnl_ci95": ci,
        "gates": gates,
        "failures": sorted(set(failures)),
        "evidence_origin": raw.get("evidence_origin"),
        "receipt_bounded": raw.get("receipt_bounded") is True,
        "witnessed_fill_net_pnl": raw.get("witnessed_fill_net_pnl") is True,
        "out_of_sample_after_registration": (
            raw.get("out_of_sample_after_registration") is True
        ),
        "isolated_candidate_decisions": raw.get("isolated_candidate_decisions") is True,
    }


def build_scope_evidence(
    scope: str,
    rows: Iterable[Any],
    now_ts: float,
    *,
    clv: Mapping[str, Any] | None = None,
    family_size: int = 1,
    promotion_eligible: bool = True,
    fused_probs_by_source: Mapping[str, Mapping[str, float]] | None = None,
    config: PromotionConfig = DEFAULT_CONFIG,
) -> ScopeEvidence:
    """Compute the full evidence dossier for one exact scope over its rows."""
    rows = list(rows)
    contested = [r for r in rows if _is_contested(r, config.contested_disagreement)]

    edges_by_cluster: dict[str, list[float]] = {}
    pnl_by_cluster: dict[str, list[float]] = {}
    beats = 0
    timestamps: list[float] = []
    for r in contested:
        cluster = str(r.event_cluster)
        edge = _brier_edge(r)
        edges_by_cluster.setdefault(cluster, []).append(edge)
        pnl_by_cluster.setdefault(cluster, []).append(counterfactual_pnl(r))
        if edge > 0.0:
            beats += 1
        ts = _row_ts(r)
        if ts is not None:
            timestamps.append(ts)

    n_clusters = len(edges_by_cluster)
    n_contested = len(contested)
    span_days = ((max(timestamps) - min(timestamps)) / 86400.0) if timestamps else 0.0
    beat_rate = (beats / n_contested) if n_contested else None

    brier_ci = cluster_bootstrap_ci(
        edges_by_cluster, seed=f"brier:{scope}", family_size=family_size,
    )
    pnl_ci = cluster_bootstrap_ci(pnl_by_cluster, seed=f"pnl:{scope}")

    has_clv = clv is not None and clv.get("lower") is not None
    clv_ci = dict(clv) if clv is not None else None

    # Degradation: trailing-window mean edge over chronological cluster means.
    series = cluster_series(
        (ts, str(r.event_cluster), _brier_edge(r))
        for r, ts in ((r, _row_ts(r)) for r in contested) if ts is not None
    )
    trail = [edge for _ts, edge in series[-DEGRADE_TRAIL_CLUSTERS:]]
    trailing_degrade_mean = (sum(trail) / len(trail)) if trail else None
    degrading = trailing_degrade_mean is not None and trailing_degrade_mean < DEGRADE_EDGE_FLOOR

    required_clusters = config.min_clusters if has_clv else config.min_clusters_no_clv

    source = scope.split("|", 1)[0]
    source_probs = _representative_probs(contested)
    fused = {
        s: p for s, p in (fused_probs_by_source or {}).items() if s != source
    }
    correlation = correlation_guard(
        source_probs, fused, cap=config.correlation_cap, min_overlap=config.min_corr_overlap,
    )

    return ScopeEvidence(
        scope=scope,
        n_clusters=n_clusters,
        n_contested_emissions=n_contested,
        span_days=span_days,
        beat_rate=beat_rate,
        brier_ci=brier_ci,
        pnl_ci=pnl_ci,
        clv_ci=clv_ci,
        has_clv=has_clv,
        trailing_degrade_mean=trailing_degrade_mean,
        degrading=degrading,
        correlation=correlation,
        family_size=max(1, int(family_size)),
        promotion_eligible=bool(promotion_eligible),
        required_clusters=required_clusters,
        min_span_days=config.min_span_days,
        min_beat_rate=config.min_beat_rate,
    )


def _row_ts(row: Any) -> float | None:
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(row.created_at).replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def _representative_probs(rows: Iterable[Any]) -> dict[str, float]:
    """One representative probability per ticker (mean of its emissions)."""
    sums: dict[str, list[float]] = {}
    for r in rows:
        sums.setdefault(str(r.ticker), []).append(float(r.probability_yes))
    return {ticker: sum(v) / len(v) for ticker, v in sums.items()}


# --------------------------------------------------------------------------
# Demotion breach (looser than promotion — hysteresis).
# --------------------------------------------------------------------------

def demotion_breach(scope: str, rows: Iterable[Any], *,
                    config: PromotionConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """A promoted scope breaches when its trailing contested Brier-edge CI95
    UPPER < 0 — i.e. the recent record is confidently NEGATIVE. Promotion needs
    the LOWER bound > 0, so the band between keeps a boundary scope stable."""
    contested = [r for r in rows if _is_contested(r, config.contested_disagreement)]
    series = cluster_series(
        (ts, str(r.event_cluster), _brier_edge(r))
        for r, ts in ((r, _row_ts(r)) for r in contested) if ts is not None
    )
    trail = [edge for _ts, edge in series[-DEMOTE_TRAIL_CLUSTERS:]]
    ci = mean_ci95(trail) or {}
    upper = ci.get("upper")
    breach = upper is not None and float(upper) < 0.0
    return {"scope": scope, "breach": bool(breach), "trailing_ci95_upper": upper,
            "trailing_clusters": len(trail)}


# --------------------------------------------------------------------------
# Rails.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RailsInputs:
    kill_file_present: bool = False
    heartbeat_status: str | None = None
    heartbeat_alive: bool = True
    health_error: bool = False
    weight_saturation_flagged: bool = False
    exchange_anomaly: bool = False
    artifact_age_hours: float | None = None


@dataclass(frozen=True)
class RailsVerdict:
    abort: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"abort": self.abort, "reasons": list(self.reasons)}


def evaluate_rails(inputs: RailsInputs, *,
                   stale_hours: float = ARTIFACT_STALE_HOURS) -> RailsVerdict:
    """A promotion run aborts ENTIRELY if any mandatory rail trips."""
    reasons: list[str] = []
    if inputs.kill_file_present:
        reasons.append("kill_file_present")
    status = str(inputs.heartbeat_status or "")
    if status.startswith("CYCLE_ERROR"):
        reasons.append("heartbeat_cycle_error")
    if not inputs.heartbeat_alive:
        reasons.append("heartbeat_not_alive")
    if inputs.health_error:
        reasons.append("health_error")
    if inputs.weight_saturation_flagged:
        reasons.append("weight_saturation_anomaly")
    if inputs.exchange_anomaly:
        reasons.append("exchange_anomaly")
    if inputs.artifact_age_hours is not None and inputs.artifact_age_hours > stale_hours:
        reasons.append("evidence_artifacts_stale")
    return RailsVerdict(abort=bool(reasons), reasons=reasons)


# --------------------------------------------------------------------------
# Decisions.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScopeDecision:
    scope: str
    action: str            # PROMOTE | ESCALATE | DEMOTE | REPLACEMENT_CANDIDATE
    stage: int
    weight_fraction: float
    dossier: dict[str, Any]
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "action": self.action,
            "stage": self.stage,
            "weight_fraction": self.weight_fraction,
            "reason": self.reason,
            "dossier": self.dossier,
        }


@dataclass
class EngineResult:
    aborted: bool
    rails: RailsVerdict
    promotions: list[ScopeDecision] = field(default_factory=list)
    escalations: list[ScopeDecision] = field(default_factory=list)
    demotions: list[ScopeDecision] = field(default_factory=list)
    replacement_candidates: list[ScopeDecision] = field(default_factory=list)
    human_review_candidates: list[ScopeDecision] = field(default_factory=list)
    deferred: list[ScopeDecision] = field(default_factory=list)
    # Wave-19: eligible scopes that FAILED the dossier gates, full dossier
    # retained. Previously these vanished silently and diagnosing a
    # non-promotion meant re-deriving every criterion by hand.
    declined: list[ScopeDecision] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "aborted": self.aborted,
            "rails": self.rails.to_dict(),
            "generated_at": self.generated_at,
            "promotions": [d.to_dict() for d in self.promotions],
            "escalations": [d.to_dict() for d in self.escalations],
            "demotions": [d.to_dict() for d in self.demotions],
            "replacement_candidates": [d.to_dict() for d in self.replacement_candidates],
            "human_review_candidates": [d.to_dict() for d in self.human_review_candidates],
            "deferred": [d.to_dict() for d in self.deferred],
            "declined": [d.to_dict() for d in self.declined],
        }


class AutoPromotionEngine:
    """Evaluates every exact scope against the two-stage ladder + rails.

    Pure with respect to I/O: ``decide`` takes every input explicitly and
    returns an ``EngineResult``. The daily runner
    (``scripts/run_dummy_readiness_report.py``) supplies the inputs (settled
    rows, current registry state, CLV, realized attribution, rails artifacts)
    and applies the result (registry files, hash-chained ledger, alerts,
    dashboard state).
    """

    def __init__(self, config: PromotionConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def decide(
        self,
        *,
        scope_rows: Mapping[str, list[Any]],
        promoted: Mapping[str, Mapping[str, Any]],
        now_ts: float,
        now_iso: str,
        rails: RailsVerdict,
        promotions_used_today: int = 0,
        clv_by_scope: Mapping[str, Mapping[str, Any]] | None = None,
        realized_by_scope: Mapping[str, Mapping[str, Any]] | None = None,
        eligible_scopes: set[str] | None = None,
        mined_family_sizes: Mapping[str, int] | None = None,
        fused_probs_by_source: Mapping[str, Mapping[str, float]] | None = None,
    ) -> EngineResult:
        if rails.abort:
            return EngineResult(aborted=True, rails=rails, generated_at=now_iso)

        clv_by_scope = clv_by_scope or {}
        realized_by_scope = realized_by_scope or {}
        mined_family_sizes = mined_family_sizes or {}
        fused_probs_by_source = fused_probs_by_source or {}
        cfg = self.config

        result = EngineResult(aborted=False, rails=rails, generated_at=now_iso)

        # 1) DEMOTIONS first — de-risking is instant, uncapped, at both stages.
        demoted_now: set[str] = set()
        for scope, meta in promoted.items():
            rows = scope_rows.get(scope, [])
            breach = demotion_breach(scope, rows, config=cfg)
            if breach["breach"]:
                demoted_now.add(scope)
                result.demotions.append(ScopeDecision(
                    scope=scope, action="DEMOTE",
                    stage=int(meta.get("stage", 1)), weight_fraction=0.0,
                    dossier={"demotion": breach, "prior_stage": int(meta.get("stage", 1))},
                    reason="trailing contested Brier-edge CI95 upper < 0",
                ))

        # 2) Candidate ADD-RISK actions (promotions + escalations), gathered then
        #    ranked and rate-limited by the daily cap.
        add_candidates: list[tuple[float, ScopeDecision]] = []

        # 2a) Escalations for stage-1 promoted scopes not being demoted.
        for scope, meta in promoted.items():
            if scope in demoted_now or int(meta.get("stage", 1)) >= 2:
                continue
            realized = realized_by_scope.get(scope)
            escalation = self._escalation_evidence(scope, realized)
            if escalation["pass"]:
                decision = ScopeDecision(
                    scope=scope, action="ESCALATE", stage=2,
                    weight_fraction=cfg.stage2_weight_fraction,
                    dossier={"escalation": escalation},
                    reason=">= %d realized trades, P&L CI95 lower > 0" % cfg.stage2_min_trades,
                )
                rank = float(escalation.get("pnl_ci95_lower") or 0.0)
                add_candidates.append((rank, decision))

        # 2b) New stage-1 promotions for eligible, not-yet-promoted scopes.
        for scope, rows in scope_rows.items():
            if scope in promoted:
                continue
            if eligible_scopes is not None and scope not in eligible_scopes:
                continue
            evidence = build_scope_evidence(
                scope, rows, now_ts,
                clv=clv_by_scope.get(scope),
                family_size=mined_family_sizes.get(scope, 1),
                promotion_eligible=(eligible_scopes is None or scope in eligible_scopes),
                fused_probs_by_source=fused_probs_by_source,
                config=cfg,
            )
            core_pass = evidence.evidence_pass()
            roi_diagnostic = roi_door_evidence(scope, rows, config=cfg)
            forward_fill = forward_witnessed_fill_evidence(
                scope, realized_by_scope.get(scope), config=cfg,
            )
            dossier = {
                **evidence.dossier(),
                "counterfactual_roi_diagnostic": roi_diagnostic,
                "forward_witnessed_fill_evidence": forward_fill,
            }
            if not core_pass or not forward_fill["pass"]:
                if core_pass or roi_diagnostic["pass"] or forward_fill["pass"]:
                    result.human_review_candidates.append(ScopeDecision(
                        scope=scope, action="HUMAN_REVIEW_CANDIDATE", stage=0,
                        weight_fraction=0.0, dossier=dossier,
                        reason=(
                            "automatic promotion withheld: requires predictive gates plus "
                            "receipt-bounded post-registration isolated witnessed-fill net "
                            "P&L over independent forward event clusters"
                        ),
                    ))
                else:
                    failing = sorted(
                        key for key, value in evidence.dossier().items()
                        if isinstance(value, dict) and value.get("pass") is False
                    )
                    result.declined.append(ScopeDecision(
                        scope=scope, action="DECLINED", stage=0,
                        weight_fraction=0.0, dossier=dossier,
                        reason="failed: " + (", ".join(failing) or "unknown"),
                    ))
                continue
            if not evidence.correlation.get("ok"):
                result.replacement_candidates.append(ScopeDecision(
                    scope=scope, action="REPLACEMENT_CANDIDATE", stage=1,
                    weight_fraction=0.0, dossier=dossier,
                    reason="correlated > %.2f with already-fused %s" % (
                        cfg.correlation_cap, evidence.correlation.get("with_source")),
                ))
                continue
            decision = ScopeDecision(
                scope=scope, action="PROMOTE", stage=1,
                weight_fraction=cfg.stage1_weight_fraction,
                dossier={**dossier, "promotion_path": "forward_witnessed_fill_v1"},
                reason=(
                    "cleared predictive gates and receipt-bounded post-registration "
                    "isolated witnessed-fill net-P&L gate"
                ),
            )
            rank = float((forward_fill.get("pnl_ci95") or {}).get("lower") or 0.0)
            add_candidates.append((rank, decision))

        # 3) Daily cap on combined add-risk actions. Strongest evidence first,
        #    then scope name for a fully deterministic tie-break.
        add_candidates.sort(key=lambda item: (-item[0], item[1].scope))
        budget = max(0, cfg.max_promotions_per_day - int(promotions_used_today))
        for index, (_rank, decision) in enumerate(add_candidates):
            if index < budget:
                if decision.action == "ESCALATE":
                    result.escalations.append(decision)
                else:
                    result.promotions.append(decision)
            else:
                result.deferred.append(ScopeDecision(
                    scope=decision.scope, action=decision.action, stage=decision.stage,
                    weight_fraction=decision.weight_fraction, dossier=decision.dossier,
                    reason="daily promotion cap reached (%d/day)" % cfg.max_promotions_per_day,
                ))
        return result

    def _escalation_evidence(
        self, scope: str, realized: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        cfg = self.config
        if not realized:
            return {"pass": False, "n_trades": 0, "reason": "no realized attribution"}
        n_trades = int(realized.get("n_trades", 0))
        pnl_by_cluster = realized.get("pnl_by_cluster") or {}
        ci = cluster_bootstrap_ci(pnl_by_cluster, seed=f"escalate:{scope}")
        lower = (ci or {}).get("lower")
        passed = (
            n_trades >= cfg.stage2_min_trades
            and lower is not None and lower > 0.0
        )
        return {
            "pass": bool(passed),
            "n_trades": n_trades,
            "threshold_trades": cfg.stage2_min_trades,
            "pnl_ci95_lower": lower,
            "pnl_ci": ci,
        }


__all__ = [
    "PromotionConfig",
    "DEFAULT_CONFIG",
    "counterfactual_pnl",
    "cluster_bootstrap_ci",
    "correlation_guard",
    "ScopeEvidence",
    "build_scope_evidence",
    "roi_door_evidence",
    "forward_witnessed_fill_evidence",
    "demotion_breach",
    "RailsInputs",
    "RailsVerdict",
    "evaluate_rails",
    "ScopeDecision",
    "EngineResult",
    "AutoPromotionEngine",
    "STAGE1_WEIGHT_FRACTION",
    "MIN_CLUSTERS",
    "MIN_CLUSTERS_NO_CLV",
    "MIN_SPAN_DAYS",
    "MIN_BEAT_RATE",
    "CORRELATION_CAP",
    "MAX_PROMOTIONS_PER_DAY",
    "STAGE2_MIN_TRADES",
    "STAGE1_MIN_FORWARD_TRADES",
    "STAGE1_MIN_FORWARD_CLUSTERS",
    "STAGE1_MIN_FORWARD_SPAN_DAYS",
    "FORWARD_EVIDENCE_VERSION",
]
