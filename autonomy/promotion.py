"""Promotion protocol + readiness evidence — the challenger-to-execution pipe.

Council build-out WS-14, the ceiling remover. Every challenger accrues
contested-Brier and CLV evidence per scope (WS-15 taxonomy), but until now
nothing could ever move a challenger INTO the execution ensemble: the
forecaster hard-excludes ``challenger_only`` signals and there was no
mechanism to say "this scope has earned its place." This module is that
mechanism, built to a strict governance contract:

  * PROMOTION IS HUMAN-ONLY. ``promotions.json`` is edited by a person in a
    reviewed PR that cites the readiness report. The system never writes it.
  * DEMOTION IS AUTOMATIC AND ONE-WAY-SAFE. When a promoted scope's recent
    record turns negative, the nightly readiness pass writes it to
    ``auto_demotions.json`` and the registry immediately stops honoring the
    promotion. Reducing risk must never wait for a human; adding it always
    must.
  * FAIL-CLOSED. Missing/corrupt files => nobody promoted => the forecaster
    is byte-identical to a build without this module.

Enforcement point: ``EnsembleForecaster.fuse`` consults ``is_promoted_signal``
at its existing ``challenger_only`` filter. That keeps the LEDGER's persisted
``challenger_only`` flag pure (a challenger is a challenger by design, and the
contested evidence used to grade it is never contaminated by its own
promotion), while a promoted scope still flows into the live ensemble.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from autonomy.stats import mean_ci95
from autonomy.taxonomy import grading_scope

DEFAULT_PROMOTIONS_PATH = Path("runtime/autonomy/promotions.json")
DEFAULT_DEMOTIONS_PATH = Path("runtime/autonomy/auto_demotions.json")

# Eligibility thresholds (auditable; tuner may propose changes later).
MIN_CONTESTED_CLUSTERS = 300         # independent event-clusters required
DEGRADE_TRAIL_CLUSTERS = 100         # window for the eligibility degradation guard
DEGRADE_EDGE_FLOOR = -0.005          # trailing mean edge below this blocks/flags
DEMOTE_TRAIL_CLUSTERS = 200          # window for the auto-demotion CI
ACCRUAL_WINDOW_DAYS = 14.0           # trailing window for the accrual rate


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _scope_key(
    source: str,
    subject: str,
    market_type: str,
    horizon: str,
) -> str:
    return f"{source}|{subject}|{market_type}|{horizon}"


class PromotionRegistry:
    """Reads the human promotion list and the machine demotion list.

    A scope is live iff a human promoted it AND the machine has not since
    demoted it. Both files are read once at construction (small, read-only);
    construct a fresh registry per cycle to pick up edits.
    """

    def __init__(
        self,
        promotions_path: Path | None = None,
        demotions_path: Path | None = None,
    ) -> None:
        self.promotions_path = Path(promotions_path or DEFAULT_PROMOTIONS_PATH)
        self.demotions_path = Path(demotions_path or DEFAULT_DEMOTIONS_PATH)
        self._promoted: set[str] = set()
        self._demoted: set[str] = set()
        # Per-scope stage + fusion weight fraction (WS "autonomous thresholded
        # promotion"). A stage-1 (probation) scope fuses at a capped weight; a
        # stage-2 scope fuses at full weight. Entries written by a human before
        # the autonomous ladder (or any entry lacking these keys) default to
        # full weight so the file stays backward-compatible.
        self._stage: dict[str, int] = {}
        self._weight_fraction: dict[str, float] = {}
        self.reload()

    def reload(self) -> None:
        self._promoted = set()
        self._stage = {}
        self._weight_fraction = {}
        for entry in _load_json(self.promotions_path).get("promotions", []) or []:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            subject = entry.get("subject")
            market_type = entry.get("market_type")
            horizon = entry.get("horizon")
            if source and subject and market_type and horizon:
                key = _scope_key(
                    str(source),
                    str(subject),
                    str(market_type),
                    str(horizon),
                )
                self._promoted.add(key)
                try:
                    self._stage[key] = int(entry.get("stage", 2))
                except (TypeError, ValueError):
                    self._stage[key] = 2
                fraction = entry.get("weight_fraction")
                try:
                    # A promotion with no weight_fraction is a full-weight
                    # (legacy / human) promotion: never silently probation-cap it.
                    self._weight_fraction[key] = (
                        1.0 if fraction is None else float(fraction)
                    )
                except (TypeError, ValueError):
                    self._weight_fraction[key] = 1.0
        self._demoted = set()
        for entry in _load_json(self.demotions_path).get("demotions", []) or []:
            if isinstance(entry, dict) and entry.get("scope"):
                self._demoted.add(str(entry["scope"]))
            elif isinstance(entry, str):
                self._demoted.add(entry)

    def is_promoted(self, scope_key: str) -> bool:
        """A scope earns execution iff promoted and not since demoted."""
        return scope_key in self._promoted and scope_key not in self._demoted

    def is_promoted_signal(
        self, source: str, ticker: str, features: dict[str, Any] | None,
    ) -> bool:
        return self.is_promoted(grading_scope(source, ticker, features or {}))

    def stage_for(self, scope_key: str) -> int | None:
        """Ladder stage of an active promoted scope, else None."""
        if not self.is_promoted(scope_key):
            return None
        return self._stage.get(scope_key, 2)

    def weight_multiplier(self, scope_key: str) -> float:
        """Fusion weight multiplier for an active promoted scope.

        Stage 1 (probation) returns its capped fraction; stage 2 / legacy
        full-weight promotions return 1.0. A scope that is not actively
        promoted returns 1.0 as well, so callers can multiply unconditionally
        (the forecaster only reaches this for a signal already admitted by
        ``is_promoted_signal``, and a non-promoted signal is never scaled).
        """
        if not self.is_promoted(scope_key):
            return 1.0
        return self._weight_fraction.get(scope_key, 1.0)

    def weight_multiplier_for_signal(
        self, source: str, ticker: str, features: dict[str, Any] | None,
    ) -> float:
        return self.weight_multiplier(grading_scope(source, ticker, features or {}))

    def snapshot(self) -> dict[str, Any]:
        active = sorted(self._promoted - self._demoted)
        return {
            "promoted": sorted(self._promoted),
            "auto_demoted": sorted(self._demoted),
            "active": active,
            "stages": {key: self._stage.get(key, 2) for key in active},
            "weight_fractions": {
                key: self._weight_fraction.get(key, 1.0) for key in active
            },
        }


# --------------------------------------------------------------------------
# Readiness evidence (pure functions over cluster-mean edges).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScopeReadiness:
    scope: str
    n_clusters: int
    mean_edge: float | None
    edge_ci95_low: float | None
    edge_ci95_high: float | None
    trailing_degrade_mean: float | None
    demote_ci95_high: float | None
    accrual_per_day: float
    days_to_eligibility: float | None
    degrading: bool
    eligible: bool
    demote: bool
    criteria: dict[str, bool]
    # Whether this scope's source is actually challenger-gated. A non-gated
    # (champion-tier) source already fuses, so "promoting" it is a no-op AND a
    # later auto-demotion could not remove it -- such scopes must never be
    # recommended as promotion candidates.
    challenger_gated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "n_clusters": self.n_clusters,
            "mean_edge": self.mean_edge,
            "edge_ci95": [self.edge_ci95_low, self.edge_ci95_high],
            "trailing_degrade_mean": self.trailing_degrade_mean,
            "demote_ci95_high": self.demote_ci95_high,
            "accrual_per_day": round(self.accrual_per_day, 4),
            "days_to_eligibility": self.days_to_eligibility,
            "degrading": self.degrading,
            "eligible": self.eligible,
            "demote": self.demote,
            "challenger_gated": self.challenger_gated,
            "criteria": dict(self.criteria),
        }


def cluster_series(rows: Iterable[tuple[float, str, float]]) -> list[tuple[float, float]]:
    """Collapse per-row edges to one mean edge per event-cluster, chronological.

    ``rows`` are ``(created_ts_epoch, event_cluster, brier_edge)``. Correlated
    emissions inside one cluster (many strikes / re-emissions of one event)
    must count once, so the cluster mean is the unit; the cluster is stamped
    with its EARLIEST timestamp so ordering reflects when the evidence first
    landed.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for ts, cluster, edge in rows:
        bucket = grouped.setdefault(cluster, {"ts": ts, "edges": []})
        bucket["ts"] = min(bucket["ts"], ts)
        bucket["edges"].append(edge)
    series = [
        (bucket["ts"], sum(bucket["edges"]) / len(bucket["edges"]))
        for bucket in grouped.values()
    ]
    series.sort(key=lambda item: item[0])
    return series


def scope_readiness(
    scope: str,
    series: list[tuple[float, float]],
    now_ts: float,
    *,
    is_currently_promoted: bool = False,
    clv_mean: float | None = None,
    challenger_gated: bool = True,
) -> ScopeReadiness:
    """Eligibility + demotion + days-to-eligibility for one scope."""
    parts = scope.split("|")
    if len(parts) != 4 or any(not part.strip() for part in parts):
        raise ValueError(
            "promotion readiness requires "
            "source|subject|market_type|horizon_or_phase"
        )
    edges = [edge for _ts, edge in series]
    n = len(edges)
    all_ci = mean_ci95(edges) or {}
    mean_edge = all_ci.get("mean")
    low = all_ci.get("lower")
    high = all_ci.get("upper")

    trail_degrade = [edge for _ts, edge in series[-DEGRADE_TRAIL_CLUSTERS:]]
    degrade_mean = (sum(trail_degrade) / len(trail_degrade)) if trail_degrade else None
    degrading = degrade_mean is not None and degrade_mean < DEGRADE_EDGE_FLOOR

    trail_demote = [edge for _ts, edge in series[-DEMOTE_TRAIL_CLUSTERS:]]
    demote_ci = mean_ci95(trail_demote) or {}
    demote_high = demote_ci.get("upper")
    demote = (
        is_currently_promoted
        and demote_high is not None
        and float(demote_high) < 0.0
    )

    cutoff = now_ts - ACCRUAL_WINDOW_DAYS * 86400.0
    recent_clusters = sum(1 for ts, _edge in series if ts >= cutoff)
    accrual = recent_clusters / ACCRUAL_WINDOW_DAYS
    remaining = max(0, MIN_CONTESTED_CLUSTERS - n)
    if remaining == 0:
        days_to_eligibility: float | None = 0.0
    elif accrual > 0:
        days_to_eligibility = round(remaining / accrual, 1)
    else:
        days_to_eligibility = None  # no recent accrual -> unknown, not zero

    clv_ok = clv_mean is None or float(clv_mean) >= 0.0
    criteria = {
        "clusters_ge_min": n >= MIN_CONTESTED_CLUSTERS,
        "edge_ci95_lower_positive": low is not None and float(low) > 0.0,
        "clv_nonneg_or_absent": clv_ok,
        "not_degrading": not degrading,
    }
    eligible = all(criteria.values())
    return ScopeReadiness(
        scope=scope,
        n_clusters=n,
        mean_edge=None if mean_edge is None else round(float(mean_edge), 6),
        edge_ci95_low=None if low is None else round(float(low), 6),
        edge_ci95_high=None if high is None else round(float(high), 6),
        trailing_degrade_mean=None if degrade_mean is None else round(degrade_mean, 6),
        demote_ci95_high=None if demote_high is None else round(float(demote_high), 6),
        accrual_per_day=accrual,
        days_to_eligibility=days_to_eligibility,
        degrading=degrading,
        eligible=eligible,
        demote=demote,
        criteria=criteria,
        challenger_gated=challenger_gated,
    )


def _is_candidate(r: ScopeReadiness, promoted_scopes: set[str]) -> bool:
    """A promotion candidate is eligible, not already promoted, and genuinely
    challenger-gated (recommending a non-gated champion would be a no-op)."""
    return r.eligible and r.challenger_gated and r.scope not in promoted_scopes


def build_readiness(
    scope_rows: dict[str, list[tuple[float, str, float]]],
    promoted_scopes: set[str],
    now_ts: float,
    now_iso: str,
    *,
    clv_by_scope: dict[str, float] | None = None,
    challenger_gated_scopes: set[str] | None = None,
) -> dict[str, Any]:
    """Full readiness report + the machine demotion list.

    ``scope_rows`` maps a grading scope to its ``(ts, cluster, edge)`` rows.
    ``challenger_gated_scopes`` (when given) is the set of scopes whose source
    is actually excluded from execution by ``challenger_only``; only those can
    be promotion candidates. ``None`` treats every scope as gated (test
    convenience). Returns ``{"report": {...}, "demotions": {...}}``.
    """
    clv_by_scope = clv_by_scope or {}
    readinesses: list[ScopeReadiness] = []
    for scope, rows in scope_rows.items():
        series = cluster_series(rows)
        readinesses.append(scope_readiness(
            scope, series, now_ts,
            is_currently_promoted=scope in promoted_scopes,
            clv_mean=clv_by_scope.get(scope),
            challenger_gated=(challenger_gated_scopes is None
                              or scope in challenger_gated_scopes),
        ))
    # Promotion candidates first, then by how close the rest are to eligibility.
    readinesses.sort(key=lambda r: (
        not _is_candidate(r, promoted_scopes),
        r.days_to_eligibility if r.days_to_eligibility is not None else float("inf"),
    ))
    demotions = [
        {"scope": r.scope, "detected_at": now_iso,
         "reason": "trailing-200-cluster contested-edge CI95 upper < 0"}
        for r in readinesses if r.demote
    ]
    return {
        "report": {
            "report_name": "AUTONOMY_READINESS",
            "generated_at": now_iso,
            "scopes_evaluated": len(readinesses),
            "promotion_candidates": sorted(
                r.scope for r in readinesses if _is_candidate(r, promoted_scopes)
            ),
            "auto_demotions": [d["scope"] for d in demotions],
            "scopes": [r.to_dict() for r in readinesses],
            "thresholds": {
                "min_contested_clusters": MIN_CONTESTED_CLUSTERS,
                "degrade_trail_clusters": DEGRADE_TRAIL_CLUSTERS,
                "degrade_edge_floor": DEGRADE_EDGE_FLOOR,
                "demote_trail_clusters": DEMOTE_TRAIL_CLUSTERS,
            },
            "note": (
                "Gate evaluation and evidence accrual are autonomous per exact "
                "source|subject|market_type|horizon_or_phase cohort. Promotion "
                "activation is AUTONOMOUS + THRESHOLDED (owner directive "
                "2026-07-16): the AutoPromotionEngine promotes a scope with "
                "statistical proof of profit into the fused ensemble, rail- "
                "guarded and rate-limited; this report is the human-readable "
                "evidence surface. Demotion is automatic and instant. Live "
                "trading authorization (live_submit / second-proof / session "
                "live auth) remains OPERATOR-ONLY and is not touched."
            ),
            "autonomous_gate_evaluation": True,
            "promotion_activation": "AUTONOMOUS_THRESHOLDED",
            "cross_cohort_evidence_transfer": False,
        },
        "demotions": {"demotions": demotions, "generated_at": now_iso},
    }


def utc_now() -> tuple[float, str]:
    now = datetime.now(timezone.utc)
    return now.timestamp(), now.isoformat()
