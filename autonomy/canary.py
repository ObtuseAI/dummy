"""Live-canary evidence gate: refuse to risk money without earned calibration.

Going live is the one irreversible action in the system. This gate blocks a
LIVE session start until the shadow history proves the machine has learned
something real: a minimum number of settled markets, at least one source that
has beaten the market baseline, and bootstrapped trust weights on file. It is
fail-closed — every missing precondition is a hard block with an exact reason,
and the operator still supplies the typed acknowledgement separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autonomy.backtest import MIN_CONTESTED_N, run_backtest
from autonomy.ledger import AutonomyLedger

MIN_SETTLED_MARKETS = 20
MIN_BEATEN_MARKET_SOURCES = 1
# A source qualifies as a market-beater only on its CONTESTED record: markets
# where it disagreed with the market prior by >=5c — the population it would
# actually trade. Agreeing with the market and being right proves nothing.
MIN_CONTESTED_BEAT_RATE = 0.55
MIN_CONTESTED_MEAN_BRIER_EDGE = 0.0
MIN_SHADOW_CONFIRMED_FILLS = 5
MIN_CANARY_GRADED_TRADES = 5
MIN_DECISION_POLICY_SETTLED = 100
MIN_DECISION_EVENT_CLUSTERS = 20
MAX_ENSEMBLE_ECE = 0.08
MIN_WALK_FORWARD_TRADES = 100
MIN_SCALE_GRADED_TRADES = 20
MIN_KALSHI_BALANCE_CENTS = 100  # need at least $1 to place the smallest order


@dataclass
class CanaryReadiness:
    ready: bool
    blockers: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_name": "LIVE_CANARY_READINESS",
            "ready": self.ready,
            "blockers": self.blockers,
            "evidence": self.evidence,
        }


def evaluate_canary_readiness(
    ledger: AutonomyLedger,
    balance_cents: int | None = None,
    min_settled: int = MIN_SETTLED_MARKETS,
    min_policy_settled: int = MIN_DECISION_POLICY_SETTLED,
    min_canary_graded: int = MIN_CANARY_GRADED_TRADES,
    backtest_report: dict[str, Any] | None = None,
) -> CanaryReadiness:
    """Assess whether the shadow record justifies a first live canary."""
    blockers: list[str] = []
    backtest = backtest_report or run_backtest(ledger, bootstrap_weights=False)
    settled = int(backtest.get("settled_markets", 0))

    if settled < min_settled:
        blockers.append(f"insufficient settlements: {settled}/{min_settled}")

    sources = backtest.get("sources", {})
    beaters = []
    for source, values in sources.items():
        edge_ci = values.get("contested_mean_brier_edge_ci95") or {}
        if (
            source != "market_prior"
            and (values.get("contested_n") or 0) >= MIN_CONTESTED_N
            and (values.get("contested_beat_rate") or 0) > MIN_CONTESTED_BEAT_RATE
            and (values.get("contested_mean_brier_edge") or 0)
                > MIN_CONTESTED_MEAN_BRIER_EDGE
            and (edge_ci.get("lower") or 0) > 0
        ):
            beaters.append(source)
    if len(beaters) < MIN_BEATEN_MARKET_SOURCES:
        blockers.append(
            f"no source beats the market where it disagrees (need contested_n>="
            f"{MIN_CONTESTED_N}, contested_beat_rate>{MIN_CONTESTED_BEAT_RATE}, and "
            f"mean contested Brier edge>{MIN_CONTESTED_MEAN_BRIER_EDGE} with a positive "
            f"event-cluster 95% lower bound; "
            f"contested records: "
            + str({s: {"n": v.get("contested_n"), "beat": v.get("contested_beat_rate"),
                       "mean_brier_edge": v.get("contested_mean_brier_edge"),
                       "edge_ci95": v.get("contested_mean_brier_edge_ci95")}
                   for s, v in sources.items() if s != "market_prior"})
        )

    decision_policy = backtest.get("decision_policy", {})
    if min_policy_settled > 0:
        policy_settled = int(decision_policy.get("settled_markets") or 0)
        if policy_settled < min_policy_settled:
            blockers.append(
                f"insufficient settled decision-policy snapshots: "
                f"{policy_settled}/{min_policy_settled}"
            )
        event_clusters = int(decision_policy.get("event_clusters") or 0)
        if event_clusters < MIN_DECISION_EVENT_CLUSTERS:
            blockers.append(
                f"insufficient independent decision event clusters: "
                f"{event_clusters}/{MIN_DECISION_EVENT_CLUSTERS}"
            )
        cluster_brier = (
            (decision_policy.get("cluster_robust_advantage") or {}).get("brier") or {}
        )
        if (cluster_brier.get("lower") or 0) <= 0:
            blockers.append(
                "decision ensemble Brier advantage lacks a positive event-cluster 95% lower bound"
            )
        ensemble = decision_policy.get("ensemble_metrics") or {}
        ece = ensemble.get("expected_calibration_error")
        if ece is None or float(ece) > MAX_ENSEMBLE_ECE:
            blockers.append(
                f"ensemble calibration error {ece} exceeds maximum {MAX_ENSEMBLE_ECE}"
            )
        walk_forward = (
            decision_policy.get("walk_forward_threshold_selection") or {}
        ).get("aggregate_out_of_sample") or {}
        walk_forward_trades = int(walk_forward.get("trades") or 0)
        walk_forward_ci = walk_forward.get("mean_pnl_ci95") or {}
        if walk_forward_trades < MIN_WALK_FORWARD_TRADES:
            blockers.append(
                f"insufficient point-in-time walk-forward trades: "
                f"{walk_forward_trades}/{MIN_WALK_FORWARD_TRADES}"
            )
        elif (walk_forward_ci.get("lower") or 0) <= 0:
            blockers.append(
                "walk-forward mean PnL lacks a positive 95% lower bound"
            )

    signal_quality = backtest.get("signal_data_quality") or {}
    for issue in signal_quality.get("blocking_issues") or []:
        blockers.append(f"signal data quality: {issue}")

    execution = (
        (backtest.get("execution_quality_by_book") or {}).get("shadow")
        or backtest.get("execution_quality", {})
    )
    confirmed_fills = int(execution.get("orders_with_confirmed_fill") or 0)
    if confirmed_fills < MIN_SHADOW_CONFIRMED_FILLS:
        blockers.append(
            f"insufficient observed shadow fills: {confirmed_fills}/{MIN_SHADOW_CONFIRMED_FILLS}"
        )

    weights = ledger.all_weights()
    non_default = {s: w for s, w in weights.items() if abs(w - 1.0) > 1e-6}
    if not non_default:
        blockers.append("trust weights never bootstrapped (run backtest --bootstrap)")

    if balance_cents is not None and balance_cents < MIN_KALSHI_BALANCE_CENTS:
        blockers.append(f"kalshi balance {balance_cents}c below minimum {MIN_KALSHI_BALANCE_CENTS}c")

    realized = backtest.get("realized_trade_statistics") or {}
    fill_conditioned = backtest.get("fill_conditioned_decision_policy") or {}
    fill_by_vertical = fill_conditioned.get("by_vertical") or {}
    scale_blockers: list[str] = []
    graded_trades = int(realized.get("trades") or 0)
    verified_net_pnl = int(realized.get("net_pnl_cents") or 0)
    if min_canary_graded > 0:
        if graded_trades < min_canary_graded:
            blockers.append(
                f"insufficient verified settled fills for canary: "
                f"{graded_trades}/{min_canary_graded}"
            )
        elif verified_net_pnl <= 0:
            blockers.append(
                f"verified shadow PnL is not positive for canary: {verified_net_pnl}c"
            )
        fill_n = int(fill_conditioned.get("n") or 0)
        fill_skill = fill_conditioned.get("brier_skill_vs_market")
        if fill_n >= min_canary_graded and (
            fill_skill is None or float(fill_skill) <= 0
        ):
            blockers.append(
                "fill-conditioned forecast Brier skill is not positive for canary: "
                f"{fill_skill}"
            )
        # A strong vertical must not mask a weak one.  Only routed trading
        # verticals are gated; legacy/OTHER rows remain visible but cannot
        # strand readiness forever.
        for vertical in ("CRYPTO", "SPORTS"):
            cohort = fill_by_vertical.get(vertical) or {}
            cohort_n = int(cohort.get("n") or 0)
            if cohort_n == 0:
                continue
            if cohort_n < min_canary_graded:
                blockers.append(
                    f"insufficient {vertical.lower()} fill-conditioned evidence: "
                    f"{cohort_n}/{min_canary_graded}"
                )
            elif float(cohort.get("brier_skill_vs_market") or 0.0) <= 0.0:
                blockers.append(
                    f"{vertical.lower()} fill-conditioned Brier skill is not positive: "
                    f"{cohort.get('brier_skill_vs_market')}"
                )
    if graded_trades < MIN_SCALE_GRADED_TRADES:
        scale_blockers.append(
            f"verified settled fills {graded_trades}/{MIN_SCALE_GRADED_TRADES}"
        )
    if verified_net_pnl <= 0:
        scale_blockers.append(
            f"verified net PnL is not positive: {verified_net_pnl}c"
        )
    if graded_trades >= MIN_SCALE_GRADED_TRADES and (
        fill_conditioned.get("brier_skill_vs_market") is None
        or float(fill_conditioned.get("brier_skill_vs_market")) <= 0
    ):
        scale_blockers.append(
            "fill-conditioned forecast Brier skill is not positive: "
            f"{fill_conditioned.get('brier_skill_vs_market')}"
        )
    for vertical in ("CRYPTO", "SPORTS"):
        cohort = fill_by_vertical.get(vertical) or {}
        cohort_n = int(cohort.get("n") or 0)
        if cohort_n == 0:
            continue
        if cohort_n < MIN_SCALE_GRADED_TRADES:
            scale_blockers.append(
                f"{vertical.lower()} fill-conditioned settlements "
                f"{cohort_n}/{MIN_SCALE_GRADED_TRADES}"
            )
        elif float(cohort.get("brier_skill_vs_market") or 0.0) <= 0.0:
            scale_blockers.append(
                f"{vertical.lower()} fill-conditioned Brier skill is not positive: "
                f"{cohort.get('brier_skill_vs_market')}"
            )
    drift = decision_policy.get("online_forecast_drift") or {}
    if drift.get("negative_drift"):
        latest = drift.get("latest_detection") or {}
        scale_blockers.append(
            "statistically detected negative forecast drift: "
            f"local Brier-excess change={latest.get('change')}"
        )

    evidence = {
        "settled_markets": settled,
        # Provenance split: 'retro' evidence is point-in-time replay against
        # markets that settled before we traded them (autonomy/retro.py);
        # 'live' is shadow/live forecasts graded as they settled. Both are
        # real markets, real outcomes, no-lookahead inputs.
        "evidence_split": ledger.evidence_split(),
        "market_beating_sources": beaters,
        "decision_policy": {
            "settled_markets": decision_policy.get("settled_markets", 0),
            "event_clusters": decision_policy.get("event_clusters", 0),
            "ensemble_metrics": decision_policy.get("ensemble_metrics", {}),
            "cluster_robust_advantage": decision_policy.get("cluster_robust_advantage", {}),
            "walk_forward_threshold_selection": decision_policy.get(
                "walk_forward_threshold_selection", {}
            ),
            "online_forecast_drift": drift,
        },
        "signal_data_quality": signal_quality,
        "bootstrapped_weights": non_default,
        "realized_shadow_pnl_cents": backtest.get("realized_decision_pnl_cents"),
        "execution_quality": execution,
        "canary_operational_evidence": {
            "minimum_settled_fills": min_canary_graded,
            "realized_trade_statistics": realized,
            "fill_conditioned_decision_policy": fill_conditioned,
            "fill_conditioned_by_vertical": fill_by_vertical,
        },
        "scale_readiness": {
            "ready": not scale_blockers,
            "blockers": scale_blockers,
            "realized_trade_statistics": realized,
            "fill_conditioned_decision_policy": fill_conditioned,
            "fill_conditioned_by_vertical": fill_by_vertical,
        },
        "balance_cents": balance_cents,
    }
    return CanaryReadiness(ready=not blockers, blockers=blockers, evidence=evidence)
