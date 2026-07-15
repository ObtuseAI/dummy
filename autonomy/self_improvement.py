"""Contraction-safe recursive performance repair.

Dummy may automatically learn narrower trust weights and quarantine a cohort
whose cluster-robust record is decisively negative.  It may never use this
path to promote a challenger, add execution authority, or increase capital.
Positive findings are proposals for human review only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.ontology import Forecast, MarketView, Vertical

DEFAULT_GUARD_PATH = Path("runtime/autonomy/performance_quarantines.json")
DEFAULT_REPORT_PATH = Path("runtime/autonomy/self_improvement_report.json")

_LEAGUE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("KXNCAAMB", "ncaamb"),
    ("KXNCAAF", "ncaaf"),
    ("KXWNBA", "wnba"),
    ("KXNBA", "nba"),
    ("KXNFL", "nfl"),
    ("KXNHL", "nhl"),
    ("KXMLB", "mlb"),
)


def _atomic_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return path


def _market_dimensions(market: MarketView, forecast: Forecast) -> dict[str, str] | None:
    if market.vertical is not Vertical.SPORTS:
        return None
    ticker = market.ticker.upper()
    league = next(
        (label for prefix, label in _LEAGUE_PREFIXES if ticker.startswith(prefix)),
        None,
    )
    if league is None:
        return None
    series = ticker.split("-", 1)[0]
    if "SPREAD" in series:
        market_type = "spread"
    elif "TOTAL" in series:
        market_type = "total"
    elif "RFI" in series:
        market_type = "yrfi"
    else:
        market_type = "winner"
    phase = "live" if any("live" in source for source in forecast.sources_used) else "pre"
    implied = forecast.market_implied_yes
    if implied is None:
        if market.yes_bid is None or market.yes_ask is None:
            return None
        implied = (float(market.yes_bid) + float(market.yes_ask)) / 200.0
    if implied is None:
        return None
    if implied < 0.40:
        regime = "underdog_lt_40"
    elif implied > 0.60:
        regime = "favorite_gt_60"
    else:
        regime = "balanced_40_60"
    return {
        "league": league,
        "market_type": market_type,
        "phase": phase,
        "market_regime": regime,
    }


def build_performance_quarantines(backtest: dict[str, Any]) -> dict[str, Any]:
    """Extract only decisive negative joint sports cohorts.

    Joint league/market/phase/regime keys avoid transferring an MLB weakness
    to another league.  The backtest already enforces row/cluster floors and a
    cluster-bootstrap interval; only ``QUARANTINE_NEGATIVE_EDGE`` contracts.
    """
    sports = (
        (backtest.get("decision_policy") or {})
        .get("sports_performance_cohorts") or {}
    )
    quarantines: list[dict[str, Any]] = []
    for scope, metrics in sorted((sports.get("by_joint_scope") or {}).items()):
        disposition = metrics.get("evidence_disposition") or {}
        if disposition.get("status") != "QUARANTINE_NEGATIVE_EDGE":
            continue
        parts = str(scope).split("|")
        if len(parts) != 4:
            continue
        interval = disposition.get("cluster_robust_brier_advantage") or {}
        quarantines.append({
            "scope": scope,
            "league": parts[0],
            "market_type": parts[1],
            "phase": parts[2],
            "market_regime": parts[3],
            "n": int(metrics.get("n") or 0),
            "event_clusters": int(metrics.get("event_clusters") or 0),
            "mean_brier_advantage_vs_market": metrics.get(
                "mean_brier_advantage_vs_market"
            ),
            "cluster_robust_brier_advantage": interval,
            "action": "AUTONOMOUS_ABSTAIN_AND_KEEP_GRADING",
            "reason": "cluster-robust Brier advantage upper bound is below zero",
        })
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_backtest_created_at": backtest.get("created_at"),
        "quarantines": quarantines,
        "authority": {
            "contraction_only": True,
            "can_abstain": True,
            "can_keep_grading": True,
            "can_release_quarantine": False,
            "can_promote": False,
            "can_enable_execution": False,
            "can_increase_capital": False,
        },
    }


def build_self_improvement_report(
    backtest: dict[str, Any], guard: dict[str, Any],
) -> dict[str, Any]:
    challengers = backtest.get("crypto_challenger_gates") or {}
    review_proposals = sorted(
        source for source, evidence in challengers.items()
        if evidence.get("ready_for_explicit_fusion_review")
    )
    scope_weights = len(backtest.get("sources_by_scope") or {})
    return {
        "schema_version": 1,
        "generated_at": guard["generated_at"],
        "source_backtest_created_at": backtest.get("created_at"),
        "recursive_cycle": [
            "observe point-in-time signals, fills, and settlements",
            "diagnose by source, league, market, phase, horizon, and regime",
            "contract decisively negative cohorts while continuing shadow grading",
            "relearn exact-scope trust from settled outcomes",
            "send candidate repairs through purged walk-forward and cluster intervals",
            "retain contraction automatically; require human review for expansion",
            "repeat from new forward evidence",
        ],
        "automatic_actions": {
            "exact_scope_trust_surfaces_recomputed": scope_weights,
            "exact_scope_weights_written": bool(backtest.get("weights_written")),
            "performance_quarantines": guard.get("quarantines") or [],
        },
        "human_review_only_proposals": {
            "crypto_challenger_fusion_reviews": review_proposals,
            "performance_quarantine_release_reviews": guard.get(
                "human_release_review_candidates"
            ) or [],
            "auto_promote": False,
        },
        "authority": guard["authority"],
    }


def write_self_improvement_artifacts(
    backtest: dict[str, Any],
    *,
    guard_path: Path = DEFAULT_GUARD_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    guard = build_performance_quarantines(backtest)
    # Risk contractions are sticky.  Fresh evidence may support a human
    # release review, but a transient recovery cannot silently restore an
    # execution path any more than it can auto-promote a challenger.
    try:
        prior = json.loads(guard_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        prior = {}
    fresh_by_scope = {
        str(entry["scope"]): entry for entry in guard["quarantines"]
    }
    current_negative_scopes = set(fresh_by_scope)
    prior_scopes: set[str] = set()
    for entry in prior.get("quarantines") or []:
        if isinstance(entry, dict) and entry.get("scope"):
            scope = str(entry["scope"])
            prior_scopes.add(scope)
            fresh_by_scope.setdefault(scope, entry)
    guard["quarantines"] = [fresh_by_scope[key] for key in sorted(fresh_by_scope)]
    guard["human_release_review_candidates"] = sorted(
        prior_scopes - current_negative_scopes
    )
    report = build_self_improvement_report(backtest, guard)
    _atomic_json(guard_path, guard)
    _atomic_json(report_path, report)
    return guard, report


class PerformanceGuard:
    """Read the latest frozen contraction artifact without widening authority."""

    def __init__(self, path: Path | str = DEFAULT_GUARD_PATH) -> None:
        self.path = Path(path)
        self.quarantines: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        """Refresh between cycles so a long session sees new contractions."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raw = {}
        self.quarantines = [
            entry for entry in (raw.get("quarantines") or [])
            if isinstance(entry, dict) and entry.get("scope")
        ]

    def reason_for(self, market: MarketView, forecast: Forecast) -> str | None:
        dimensions = _market_dimensions(market, forecast)
        if dimensions is None:
            return None
        for entry in self.quarantines:
            if all(entry.get(key) == value for key, value in dimensions.items()):
                return (
                    "performance quarantine: "
                    f"{entry['scope']} ({entry.get('event_clusters')} clusters; "
                    f"edge={entry.get('mean_brier_advantage_vs_market')})"
                )
        return None
