"""Autonomous thresholded promotion — the ladder that earns fusion membership.

Owner directive 2026-07-16: promotion gates become autonomous. A scope with
statistical PROOF OF PROFIT auto-promotes into the fused ensemble, replacing the
previous human-only positive promotion. This module is that decision engine.

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
    (c) PROOF OF PROFIT: fee-adjusted counterfactual P&L over the scope's
        contested emissions (entry at the recorded market price at emission
        time, exit at settlement, Kalshi maker fee model), cluster-level
        bootstrap CI95 lower > 0. Cluster-level, never per-emission;
    (d) not degrading (trailing-window edge floor);
    (e) CLV mean CI lower > 0 where CLV records exist; a scope with no CLV
        instrumentation may pass without it but needs MIN_CLUSTERS_NO_CLV;
    (f) correlation guard: emission correlation vs every already-fused source on
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
ARTIFACT_STALE_HOURS = 24.0        # evidence artifacts older than this abort a run
BOOTSTRAP_SAMPLES = 1000           # matches autonomy/backtest.py


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
    contested_disagreement: float = CONTESTED_DISAGREEMENT

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
            "contested_disagreement": self.contested_disagreement,
        }


DEFAULT_CONFIG = PromotionConfig()


# --------------------------------------------------------------------------
# Counterfactual P&L (fee-adjusted) — the proof-of-profit primitive.
# --------------------------------------------------------------------------

def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def counterfactual_pnl(row: Any) -> float:
    """Fee-adjusted P&L in DOLLARS for one settled, market-benchmarked emission.

    A unit (1-contract) counterfactual: enter the side the model favors versus
    the market at the recorded market price at emission time
    (``market_probability``), pay the Kalshi maker fee, hold to settlement.

      * side = YES when the model prices above the market, else NO;
      * entry cost = market price of that side (YES: p; NO: 1-p);
      * payoff = 1 if the side wins at settlement, else 0;
      * net = payoff - entry_cost - maker_fee.

    Maker fee (not taker): Dummy submits edge-preserving resting LIMIT orders,
    so a taker fee would overstate cost and understate proven profit. The fee
    formula is symmetric in p and (1-p), so the entry price in cents is the
    same magnitude for either side.
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
            if not evidence.evidence_pass():
                dossier = evidence.dossier()
                failing = sorted(
                    key for key, value in dossier.items()
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
                    weight_fraction=0.0, dossier=evidence.dossier(),
                    reason="correlated > %.2f with already-fused %s" % (
                        cfg.correlation_cap, evidence.correlation.get("with_source")),
                ))
                continue
            decision = ScopeDecision(
                scope=scope, action="PROMOTE", stage=1,
                weight_fraction=cfg.stage1_weight_fraction,
                dossier=evidence.dossier(),
                reason="cleared all stage-1 gates incl. proof-of-profit",
            )
            rank = float((evidence.brier_ci or {}).get("lower") or 0.0)
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
]
