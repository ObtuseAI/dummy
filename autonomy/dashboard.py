"""Operator dashboard for the autonomy predator.

A query-only evidence view plus narrowly scoped local controls for the public
paper scheduler. The control path cannot reach the broker, live executor,
weights, risk settings, or capital authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from starlette.requests import Request

from autonomy.dashboard_ui import DASHBOARD_HTML

RUNTIME_DIR = Path("runtime/autonomy")
# Indirection so tests can drive the cache clock without patching the global
# time module (which the test event loop also uses).
_monotonic = time.monotonic
SHADOW_TASK_NAME = "DummyShadowPredator"
TRAINER_TASK_NAME = "DummySimulationTrainer"
DASHBOARD_TASK_NAME = "DummyDashboard"
MISPRICING_TASK_NAME = "DummyMispricingMonitor"
SPORTS_MODEL_SEED_TASK_NAME = "DummySportsModelSeed"
SPORTS_BOARD_REFRESH_TASK_NAME = "DummySportsBoardRefresh"
SPORTS_MODEL_SEED_STATUS_FILE = "sports_model_seed_authoritative_status.json"
WATCHDOG_STATUS_MAX_AGE_SECONDS = 600.0

MISPRICING_MONITOR_AUTHORITY = {
    "status": "LEGACY_RESEARCH_NON_AUTHORITATIVE",
    "execution_authority": False,
    "can_gate_sports_grades": False,
    "can_gate_live": False,
}


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _to_epoch(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def _age_seconds(value: Any, now_epoch: float) -> float | None:
    """Age in seconds of an ISO/epoch timestamp, or None if unparseable."""
    epoch = _to_epoch(value)
    return None if epoch is None else round(now_epoch - epoch, 1)


def _first_timestamp(data: Any, fields: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        for name in fields:
            if data.get(name) is not None:
                return data.get(name)
    return None


# Panel artifact -> the timestamp field that stamps its freshness. Used to
# annotate every data panel with an explicit age so stale data reads as stale.
_FRESHNESS_FIELDS: dict[str, tuple[str, ...]] = {
    "heartbeat": ("last_cycle_at",),
    "live_account": ("generated_at",),
    "sports_model_seed": ("last_success_at",),
    "mispricing_monitor": ("generated_at",),
    "crypto_paper_twin": ("completed_at", "started_at"),
    "sports_simulation": ("completed_at", "started_at"),
    "simulation_training": ("created_at",),
    "readiness_report": ("generated_at",),
    "council_snapshot": ("generated_at",),
    "clv_report": ("generated_at",),
    "execution_tournament": ("generated_at",),
}

# Cadence-derived staleness threshold (seconds) per panel, mirroring
# autonomy/watchdog.py (2x the task cadence). A panel older than this is stale.
_FRESHNESS_THRESHOLDS: dict[str, float] = {
    "heartbeat": 1200,
    "live_account": 600,
    "sports_model_seed": 600,
    "mispricing_monitor": 600,
    "crypto_paper_twin": 600,
    "sports_simulation": 1200,
    "simulation_training": 7200,
    "readiness_report": 172800,
    "council_snapshot": 600,
    "clv_report": 172800,
    # Tournament refreshes with the backtest cycle; 2x a generous daily cadence.
    "execution_tournament": 172800,
}


def _dashboard_watchdog_status(runtime_dir: Path, now_epoch: float) -> dict[str, Any]:
    """Return fresh persisted watchdog health or recompute it read-only.

    A recently written status is useful only while its own ``generated_at``
    remains fresh.  Once that supervisory artifact is missing, unreadable,
    future-dated, or older than ten minutes, recompute from runtime artifacts
    rather than letting a dead watchdog make the dashboard look healthy.
    """
    persisted = _load_json(runtime_dir / "watchdog_status.json")
    generated_at = (
        persisted.get("generated_at") if isinstance(persisted, dict) else None
    )
    persisted_epoch = _to_epoch(generated_at)
    persisted_age_exact = (
        None if persisted_epoch is None else now_epoch - persisted_epoch
    )
    persisted_age = (
        None if persisted_age_exact is None else round(persisted_age_exact, 1)
    )
    persisted_task_names = {
        str(row.get("task_name"))
        for row in (persisted.get("tasks") or [])
        if isinstance(row, dict) and row.get("task_name")
    } if isinstance(persisted, dict) else set()
    required_authoritative_tasks = {
        SPORTS_MODEL_SEED_TASK_NAME,
        SPORTS_BOARD_REFRESH_TASK_NAME,
    }
    if (
        isinstance(persisted, dict)
        and persisted_age_exact is not None
        and 0.0 <= persisted_age_exact <= WATCHDOG_STATUS_MAX_AGE_SECONDS
        and isinstance(persisted.get("healthy"), bool)
        and isinstance(persisted.get("tasks"), list)
        and isinstance(persisted.get("stale_tasks"), list)
        and required_authoritative_tasks.issubset(persisted_task_names)
        and not (
            persisted.get("healthy") is True and bool(persisted.get("stale_tasks"))
        )
    ):
        result = dict(persisted)
        result["source"] = "persisted_watchdog_status"
        result["status_age_seconds"] = persisted_age
        result["status_max_age_seconds"] = WATCHDOG_STATUS_MAX_AGE_SECONDS
        result["persisted_status_stale"] = False
        return result

    try:
        from autonomy.watchdog import evaluate_watchdog

        evaluated = evaluate_watchdog(runtime_dir=runtime_dir, now_epoch=now_epoch)
        if not isinstance(evaluated, dict) or not isinstance(
            evaluated.get("healthy"), bool
        ):
            raise ValueError("watchdog evaluation returned an invalid status")
        result = dict(evaluated)
        result["source"] = "live_read_only_recompute"
        result["read_only_recompute"] = True
        result["persisted_status_age_seconds"] = persisted_age
        result["status_max_age_seconds"] = WATCHDOG_STATUS_MAX_AGE_SECONDS
        result["persisted_status_stale"] = True
        return result
    except Exception as exc:
        # Dashboard health is observational only.  If even its read-only
        # recomputation fails, report an unhealthy state without touching the
        # scheduler, ledger, broker, or any runtime artifact.
        return {
            "generated_at": datetime.fromtimestamp(
                now_epoch, tz=timezone.utc
            ).isoformat(),
            "source": "live_read_only_recompute",
            "status": "RECOMPUTE_FAILED_CLOSED",
            "healthy": False,
            "tasks": [],
            "stale_tasks": ["WATCHDOG_HEALTH_UNAVAILABLE"],
            "read_only_recompute": True,
            "persisted_status_age_seconds": persisted_age,
            "status_max_age_seconds": WATCHDOG_STATUS_MAX_AGE_SECONDS,
            "persisted_status_stale": True,
            "error_type": type(exc).__name__,
        }


def _panel_data_age(name: str, payload: Any, now_epoch: float) -> dict[str, Any]:
    """Build one exact, fail-closed artifact freshness row."""
    stamp = _first_timestamp(payload, _FRESHNESS_FIELDS.get(name, ()))
    epoch = _to_epoch(stamp)
    exact_age = None if epoch is None else now_epoch - epoch
    age = None if exact_age is None else round(exact_age, 1)
    threshold = _FRESHNESS_THRESHOLDS.get(name)
    return {
        "at": stamp,
        "age_seconds": age,
        "threshold_seconds": threshold,
        # Future-dated evidence is not fresh evidence.  Bound checks use the
        # unrounded age so an artifact just over its limit cannot round down.
        "stale": (
            exact_age is None
            or exact_age < 0.0
            or (threshold is not None and exact_age > threshold)
        ),
    }


# Tier evidence is generated by the comparatively slow backtest cycle.  Keep
# its clock contract separate from the fast dashboard snapshot timestamp: a
# light snapshot refresh must not make old tier evidence look new.
_TIER_EVIDENCE_MAX_AGE_SECONDS = 48 * 60 * 60
_TIER_EVIDENCE_MAX_FUTURE_SKEW_SECONDS = 5 * 60
_TIER_EVIDENCE_STATUSES = {
    "COLLECTING_FORWARD_EVIDENCE",
    "INSUFFICIENT_SAMPLE",
    "FORWARD_SAMPLE_AVAILABLE",
}
_TIER_EVIDENCE_GROUP_FIELDS = (
    "by_tier",
    "by_tier_scope",
    "by_scope_horizon",
    "by_tier_scope_horizon",
    "by_tier_scope_market_horizon",
)
_TIER_FORECAST_METRIC_FIELDS = {
    "n",
    "event_clusters",
    "value_side_n",
    "value_side_wins",
    "value_side_hit_rate",
    "value_side_hit_rate_descriptive_wilson_ci95",
    "value_side_hit_rate_cluster_ci95",
    "mean_brier",
    "mean_log_loss",
    "expected_calibration_error",
    "maximum_calibration_error",
    "calibration_bins",
    "mean_assigned_after_fee_edge",
    "evidence_status",
}
_TIER_FORECAST_MARKET_FIELDS = {
    "market_comparison_n",
    "mean_market_brier",
    "brier_advantage_vs_market",
}
_TIER_REALIZED_METRIC_FIELDS = {
    "n",
    "event_clusters",
    "wins",
    "losses",
    "win_rate",
    "win_rate_descriptive_wilson_ci95",
    "win_rate_cluster_ci95",
    "net_pnl_cents",
    "entry_cost_plus_fees_cents",
    "roi",
    "roi_cluster_ci95",
    "profit_factor",
    "max_drawdown_cents",
    "exact_witnessed_cost_n",
    "evidence_status",
}
_TIER_EMPTY_METRIC_FIELDS = {"n", "evidence_status"}
_TIER_NAMES = {"A", "B", "C", "WATCH"}
_TIER_FORECAST_ADDITIVE_FIELDS = (
    "n",
    "value_side_n",
    "value_side_wins",
    "market_comparison_n",
)
_TIER_REALIZED_ADDITIVE_FIELDS = (
    "n",
    "wins",
    "losses",
    "net_pnl_cents",
    "entry_cost_plus_fees_cents",
    "exact_witnessed_cost_n",
)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _bounded_number(value: Any, low: float, high: float) -> bool:
    parsed = _finite_number(value)
    return parsed is not None and low <= parsed <= high


def _rate_ci_is_valid(
    value: Any,
    *,
    max_clusters: int | None = None,
    bounded: bool = True,
) -> bool:
    if value is None:
        return True
    required = {"low", "high"}
    if max_clusters is not None:
        required.add("event_clusters")
    if not isinstance(value, dict) or set(value) != required:
        return False
    low = _finite_number(value.get("low"))
    high = _finite_number(value.get("high"))
    if low is None or high is None or low > high:
        return False
    if bounded and not (0.0 <= low <= high <= 1.0):
        return False
    if max_clusters is not None:
        clusters = value.get("event_clusters")
        if (
            isinstance(clusters, bool)
            or not isinstance(clusters, int)
            or not 2 <= clusters <= max_clusters
        ):
            return False
    return True


def _tier_evidence_freshness(value: Any, *, now_epoch: float) -> dict[str, Any]:
    """Return fail-closed clock labels for one persisted evidence artifact."""
    epoch: float | None = None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                epoch = parsed.timestamp()
        except (OverflowError, TypeError, ValueError):
            epoch = None
    if epoch is None:
        return {
            "evidence_generated_at": value,
            "evidence_age_seconds": None,
            "evidence_max_age_seconds": _TIER_EVIDENCE_MAX_AGE_SECONDS,
            "evidence_max_future_skew_seconds": (
                _TIER_EVIDENCE_MAX_FUTURE_SKEW_SECONDS
            ),
            "evidence_future_skew_seconds": None,
            "evidence_stale": True,
            "evidence_time_status": "TIME_UNKNOWN",
        }
    age = now_epoch - epoch
    future_skew = max(0.0, -age)
    if future_skew > _TIER_EVIDENCE_MAX_FUTURE_SKEW_SECONDS:
        status = "FUTURE_SKEW"
    elif age > _TIER_EVIDENCE_MAX_AGE_SECONDS:
        status = "STALE"
    else:
        status = "FRESH"
    return {
        "evidence_generated_at": value,
        "evidence_age_seconds": round(age, 1),
        "evidence_max_age_seconds": _TIER_EVIDENCE_MAX_AGE_SECONDS,
        "evidence_max_future_skew_seconds": _TIER_EVIDENCE_MAX_FUTURE_SKEW_SECONDS,
        "evidence_future_skew_seconds": round(future_skew, 1),
        "evidence_stale": status != "FRESH",
        "evidence_time_status": status,
    }


def _tier_metric_validation_error(
    metric: Any,
    *,
    path: str,
    lane_name: str,
    min_forward_n: int,
    min_forward_event_clusters: int,
) -> str | None:
    """Validate one overall or grouped forward-performance metric block."""
    if not isinstance(metric, dict):
        return f"Tier-performance {path} is invalid."
    n = metric.get("n")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return f"Tier-performance {path}.n is invalid."
    evidence_status = metric.get("evidence_status")
    if evidence_status not in _TIER_EVIDENCE_STATUSES:
        return f"Tier-performance {path} evidence status is invalid."
    if n == 0:
        if set(metric) != _TIER_EMPTY_METRIC_FIELDS:
            return f"Tier-performance {path} empty metric schema is invalid."
        if evidence_status != "COLLECTING_FORWARD_EVIDENCE":
            return f"Tier-performance {path} empty evidence is mislabeled."
        return None
    if evidence_status == "COLLECTING_FORWARD_EVIDENCE":
        return f"Tier-performance {path} populated evidence is mislabeled."
    clusters = metric.get("event_clusters")
    if (
        isinstance(clusters, bool)
        or not isinstance(clusters, int)
        or clusters < 1
        or clusters > n
    ):
        return f"Tier-performance {path} event-cluster count is invalid."
    expected_status = (
        "FORWARD_SAMPLE_AVAILABLE"
        if n >= min_forward_n and clusters >= min_forward_event_clusters
        else "INSUFFICIENT_SAMPLE"
    )
    if evidence_status != expected_status:
        return f"Tier-performance {path} sufficiency label is inconsistent."

    if lane_name == "forecast":
        fields = set(metric)
        if frozenset(fields) not in {
            frozenset(_TIER_FORECAST_METRIC_FIELDS),
            frozenset(_TIER_FORECAST_METRIC_FIELDS | _TIER_FORECAST_MARKET_FIELDS),
        }:
            return f"Tier-performance {path} forecast metric schema is invalid."
        value_n = metric.get("value_side_n")
        value_wins = metric.get("value_side_wins")
        if (
            isinstance(value_n, bool)
            or not isinstance(value_n, int)
            or not 0 <= value_n <= n
            or isinstance(value_wins, bool)
            or not isinstance(value_wins, int)
            or not 0 <= value_wins <= value_n
        ):
            return f"Tier-performance {path} value-side counts are invalid."
        expected_rate = round(value_wins / value_n, 4) if value_n else None
        if metric.get("value_side_hit_rate") != expected_rate:
            return f"Tier-performance {path} value-side hit rate is inconsistent."
        wilson = metric.get("value_side_hit_rate_descriptive_wilson_ci95")
        if (value_n == 0 and wilson is not None) or (
            value_n > 0 and (wilson is None or not _rate_ci_is_valid(wilson))
        ):
            return f"Tier-performance {path} descriptive interval is invalid."
        if not _rate_ci_is_valid(
            metric.get("value_side_hit_rate_cluster_ci95"),
            max_clusters=clusters,
        ):
            return f"Tier-performance {path} cluster interval is invalid."
        if not _bounded_number(metric.get("mean_brier"), 0.0, 1.0):
            return f"Tier-performance {path} mean Brier score is invalid."
        mean_log_loss = _finite_number(metric.get("mean_log_loss"))
        if mean_log_loss is None or mean_log_loss < 0.0:
            return f"Tier-performance {path} mean log loss is invalid."
        ece = _finite_number(metric.get("expected_calibration_error"))
        mce = _finite_number(metric.get("maximum_calibration_error"))
        if (
            ece is None
            or mce is None
            or not 0.0 <= ece <= mce <= 1.0
        ):
            return f"Tier-performance {path} calibration error is invalid."
        bins = metric.get("calibration_bins")
        if not isinstance(bins, list) or not bins or len(bins) > 10:
            return f"Tier-performance {path} calibration bins are invalid."
        bin_total = 0
        weighted_gap = 0.0
        maximum_gap = 0.0
        for bin_row in bins:
            if not isinstance(bin_row, dict) or set(bin_row) != {
                "range", "n", "predicted_mean", "observed_rate",
            }:
                return f"Tier-performance {path} calibration bin schema is invalid."
            bin_n = bin_row.get("n")
            if isinstance(bin_n, bool) or not isinstance(bin_n, int) or bin_n < 1:
                return f"Tier-performance {path} calibration bin count is invalid."
            predicted = _finite_number(bin_row.get("predicted_mean"))
            observed = _finite_number(bin_row.get("observed_rate"))
            if (
                not isinstance(bin_row.get("range"), str)
                or not bin_row["range"]
                or predicted is None
                or observed is None
                or not 0.0 <= predicted <= 1.0
                or not 0.0 <= observed <= 1.0
            ):
                return f"Tier-performance {path} calibration bin values are invalid."
            gap = abs(predicted - observed)
            bin_total += bin_n
            weighted_gap += bin_n * gap
            maximum_gap = max(maximum_gap, gap)
        if (
            bin_total != n
            or abs(ece - round(weighted_gap / n, 6)) > 1e-6
            or abs(mce - round(maximum_gap, 6)) > 1e-6
        ):
            return f"Tier-performance {path} calibration summary is inconsistent."
        mean_edge = metric.get("mean_assigned_after_fee_edge")
        if not _bounded_number(mean_edge, -1.0, 1.0):
            return f"Tier-performance {path} assigned edge is invalid."
        if _TIER_FORECAST_MARKET_FIELDS.issubset(fields):
            comparison_n = metric.get("market_comparison_n")
            if (
                isinstance(comparison_n, bool)
                or not isinstance(comparison_n, int)
                or not 1 <= comparison_n <= n
                or not _bounded_number(metric.get("mean_market_brier"), 0.0, 1.0)
                or not _bounded_number(
                    metric.get("brier_advantage_vs_market"), -1.0, 1.0
                )
            ):
                return f"Tier-performance {path} market comparison is invalid."
    elif lane_name == "realized":
        if set(metric) != _TIER_REALIZED_METRIC_FIELDS:
            return f"Tier-performance {path} realized metric schema is invalid."
        wins = metric.get("wins")
        losses = metric.get("losses")
        if (
            isinstance(wins, bool)
            or not isinstance(wins, int)
            or wins < 0
            or isinstance(losses, bool)
            or not isinstance(losses, int)
            or losses < 0
            or wins + losses != n
            or metric.get("win_rate") != round(wins / n, 4)
        ):
            return f"Tier-performance {path} win/loss summary is inconsistent."
        win_wilson = metric.get("win_rate_descriptive_wilson_ci95")
        if win_wilson is None or not _rate_ci_is_valid(win_wilson):
            return f"Tier-performance {path} descriptive interval is invalid."
        if not _rate_ci_is_valid(
            metric.get("win_rate_cluster_ci95"), max_clusters=clusters
        ):
            return f"Tier-performance {path} cluster interval is invalid."
        pnl = metric.get("net_pnl_cents")
        cost = metric.get("entry_cost_plus_fees_cents")
        drawdown = metric.get("max_drawdown_cents")
        exact_cost_n = metric.get("exact_witnessed_cost_n")
        if (
            isinstance(pnl, bool)
            or not isinstance(pnl, int)
            or isinstance(cost, bool)
            or not isinstance(cost, int)
            or cost < 1
            or isinstance(drawdown, bool)
            or not isinstance(drawdown, int)
            or drawdown < 0
            or isinstance(exact_cost_n, bool)
            or not isinstance(exact_cost_n, int)
            or not 0 <= exact_cost_n <= n
        ):
            return f"Tier-performance {path} realized totals are invalid."
        roi = _finite_number(metric.get("roi"))
        if roi is None or abs(roi - round(pnl / cost, 6)) > 1e-6:
            return f"Tier-performance {path} ROI is inconsistent."
        if not _rate_ci_is_valid(
            metric.get("roi_cluster_ci95"),
            max_clusters=clusters,
            bounded=False,
        ):
            return f"Tier-performance {path} ROI interval is invalid."
        profit_factor = metric.get("profit_factor")
        parsed_profit_factor = _finite_number(profit_factor)
        if profit_factor is not None and (
            parsed_profit_factor is None or parsed_profit_factor < 0.0
        ):
            return f"Tier-performance {path} profit factor is invalid."
    else:
        return f"Tier-performance {path} has an unknown evidence lane."
    return None


def _tier_cross_tab_validation_error(
    lane: dict[str, Any], *, lane_name: str,
) -> str | None:
    """Bind every coarser grouping to the fine-grained evidence partition."""
    fine = lane["by_tier_scope_market_horizon"]
    fine_rows: list[tuple[tuple[str, str, str, str], dict[str, Any]]] = []
    for key, metric in fine.items():
        parts = tuple(str(key).split("|"))
        if (
            not isinstance(key, str)
            or len(parts) != 4
            or parts[0] not in _TIER_NAMES
            or any(not part for part in parts)
            or int(metric["n"]) < 1
        ):
            return f"Tier-performance {lane_name} fine-grained key is invalid."
        fine_rows.append((parts, metric))

    field_names = (
        _TIER_FORECAST_ADDITIVE_FIELDS
        if lane_name == "forecast"
        else _TIER_REALIZED_ADDITIVE_FIELDS
    )

    def totals(metrics: list[dict[str, Any]]) -> dict[str, int]:
        return {
            field: sum(int(metric.get(field) or 0) for metric in metrics)
            for field in field_names
        }

    def projection(indices: tuple[int, ...]) -> dict[str, list[dict[str, Any]]]:
        projected: dict[str, list[dict[str, Any]]] = {}
        for parts, metric in fine_rows:
            key = "|".join(parts[index] for index in indices)
            projected.setdefault(key, []).append(metric)
        return projected

    specifications = {
        "by_tier": (0,),
        "by_tier_scope": (0, 1),
        "by_scope_horizon": (1, 3),
        "by_tier_scope_horizon": (0, 1, 3),
        "by_tier_scope_market_horizon": (0, 1, 2, 3),
    }
    for field, indices in specifications.items():
        expected = projection(indices)
        if field == "by_tier":
            expected_keys = _TIER_NAMES
        else:
            expected_keys = set(expected)
        actual = lane[field]
        if set(actual) != expected_keys:
            return f"Tier-performance {lane_name}.{field} keys are inconsistent."
        for key in expected_keys:
            component_metrics = expected.get(key, [])
            actual_metric = actual[key]
            if totals([actual_metric]) != totals(component_metrics):
                return f"Tier-performance {lane_name}.{field}[{key}] is inconsistent."
            if component_metrics and lane_name == "forecast":
                n = sum(int(metric["n"]) for metric in component_metrics)
                for metric_field in (
                    "mean_brier",
                    "mean_log_loss",
                    "mean_assigned_after_fee_edge",
                ):
                    weighted = round(sum(
                        float(metric[metric_field]) * int(metric["n"])
                        for metric in component_metrics
                    ) / n, 6)
                    if abs(float(actual_metric[metric_field]) - weighted) > 2e-6:
                        return (
                            f"Tier-performance {lane_name}.{field}[{key}] "
                            f"{metric_field} is inconsistent."
                        )
                comparison_n = sum(
                    int(metric.get("market_comparison_n") or 0)
                    for metric in component_metrics
                )
                if comparison_n:
                    for metric_field in (
                        "mean_market_brier", "brier_advantage_vs_market",
                    ):
                        weighted = round(sum(
                            float(metric[metric_field])
                            * int(metric["market_comparison_n"])
                            for metric in component_metrics
                            if metric.get("market_comparison_n")
                        ) / comparison_n, 6)
                        if abs(float(actual_metric[metric_field]) - weighted) > 2e-6:
                            return (
                                f"Tier-performance {lane_name}.{field}[{key}] "
                                f"{metric_field} is inconsistent."
                            )

    fine_metrics = [metric for _parts, metric in fine_rows]
    if totals([lane["overall"]]) != totals(fine_metrics):
        return f"Tier-performance {lane_name}.overall totals are inconsistent."
    if fine_metrics and lane_name == "forecast":
        total_n = sum(int(metric["n"]) for metric in fine_metrics)
        for metric_field in (
            "mean_brier", "mean_log_loss", "mean_assigned_after_fee_edge",
        ):
            weighted = round(sum(
                float(metric[metric_field]) * int(metric["n"])
                for metric in fine_metrics
            ) / total_n, 6)
            if abs(float(lane["overall"][metric_field]) - weighted) > 2e-6:
                return (
                    f"Tier-performance {lane_name}.overall "
                    f"{metric_field} is inconsistent."
                )
        comparison_n = sum(
            int(metric.get("market_comparison_n") or 0) for metric in fine_metrics
        )
        if comparison_n:
            for metric_field in (
                "mean_market_brier", "brier_advantage_vs_market",
            ):
                weighted = round(sum(
                    float(metric[metric_field]) * int(metric["market_comparison_n"])
                    for metric in fine_metrics
                    if metric.get("market_comparison_n")
                ) / comparison_n, 6)
                if abs(float(lane["overall"][metric_field]) - weighted) > 2e-6:
                    return (
                        f"Tier-performance {lane_name}.overall "
                        f"{metric_field} is inconsistent."
                    )
    return None


def _tier_performance_validation_error(
    report: Any,
    *,
    expected_policy_version: str,
    expected_policy_sha256: str,
    expected_policy_spec: dict[str, Any],
    min_forward_n: int,
    min_forward_event_clusters: int,
) -> str | None:
    """Validate persisted tier evidence before the API gives it authority."""
    if not isinstance(report, dict) or not report:
        return "Tier-performance evidence is missing from the dashboard snapshot."
    if set(report) != {
        "schema_version",
        "policy_version",
        "policy_sha256",
        "policy_spec",
        "legacy_backfill",
        "status",
        "forecast",
        "realized",
        "caveat",
    }:
        return "Tier-performance evidence has an invalid top-level schema."
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        return "Tier-performance evidence has an unsupported schema version."
    if report.get("policy_version") != expected_policy_version:
        return "Tier-performance evidence does not use the current policy version."
    if report.get("policy_sha256") != expected_policy_sha256:
        return "Tier-performance evidence does not match the current policy hash."
    try:
        supplied_policy = json.dumps(
            report.get("policy_spec"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        current_policy = json.dumps(
            expected_policy_spec,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return "Tier-performance evidence contains an invalid policy spec."
    if supplied_policy != current_policy:
        return "Tier-performance evidence does not contain the exact current policy spec."
    if hashlib.sha256(supplied_policy.encode("utf-8")).hexdigest() != expected_policy_sha256:
        return "Tier-performance evidence policy spec fails hash verification."
    if report.get("legacy_backfill") is not False:
        return "Tier-performance evidence does not prove forward-only attribution."
    if not isinstance(report.get("caveat"), str) or not report["caveat"].strip():
        return "Tier-performance evidence caveat is missing."

    lane_states: list[tuple[int, str]] = []
    for lane_name in ("forecast", "realized"):
        lane = report.get(lane_name)
        if not isinstance(lane, dict):
            return f"Tier-performance {lane_name} evidence is missing."
        expected_lane_fields = {
            "population", "overall", *_TIER_EVIDENCE_GROUP_FIELDS,
        }
        if lane_name == "realized":
            expected_lane_fields.add("by_book")
        if set(lane) != expected_lane_fields:
            return f"Tier-performance {lane_name} schema is invalid."
        if not isinstance(lane.get("population"), str) or not lane["population"].strip():
            return f"Tier-performance {lane_name} population is missing."
        for field in _TIER_EVIDENCE_GROUP_FIELDS:
            if not isinstance(lane.get(field), dict):
                return f"Tier-performance {lane_name}.{field} is invalid."
        if lane_name == "realized" and not isinstance(lane.get("by_book"), dict):
            return "Tier-performance realized.by_book is invalid."
        if set(lane["by_tier"]) != {"A", "B", "C", "WATCH"}:
            return f"Tier-performance {lane_name}.by_tier roster is invalid."

        overall = lane.get("overall")
        metric_error = _tier_metric_validation_error(
            overall,
            path=f"{lane_name}.overall",
            lane_name=lane_name,
            min_forward_n=min_forward_n,
            min_forward_event_clusters=min_forward_event_clusters,
        )
        if metric_error:
            return metric_error
        n = int(overall["n"])
        evidence_status = str(overall["evidence_status"])
        for field in _TIER_EVIDENCE_GROUP_FIELDS:
            group_total = 0
            for key, metric in lane[field].items():
                metric_error = _tier_metric_validation_error(
                    metric,
                    path=f"{lane_name}.{field}[{key}]",
                    lane_name=lane_name,
                    min_forward_n=min_forward_n,
                    min_forward_event_clusters=min_forward_event_clusters,
                )
                if metric_error:
                    return metric_error
                group_total += int(metric["n"])
            if group_total != n:
                return f"Tier-performance {lane_name}.{field} total is inconsistent."

        cross_tab_error = _tier_cross_tab_validation_error(
            lane, lane_name=lane_name,
        )
        if cross_tab_error:
            return cross_tab_error

        if lane_name == "realized":
            by_book = lane["by_book"]
            if set(by_book) != {"shadow", "live"}:
                return "Tier-performance realized.by_book roster is invalid."
            book_total = 0
            for book, book_block in by_book.items():
                if not isinstance(book_block, dict):
                    return f"Tier-performance realized.by_book[{book}] is invalid."
                book_overall = book_block.get("overall")
                metric_error = _tier_metric_validation_error(
                    book_overall,
                    path=f"realized.by_book[{book}].overall",
                    lane_name="realized",
                    min_forward_n=min_forward_n,
                    min_forward_event_clusters=min_forward_event_clusters,
                )
                if metric_error:
                    return metric_error
                by_tier = book_block.get("by_tier")
                if not isinstance(by_tier, dict):
                    return f"Tier-performance realized.by_book[{book}].by_tier is invalid."
                if set(by_tier) != {"A", "B", "C", "WATCH"}:
                    return (
                        f"Tier-performance realized.by_book[{book}].by_tier "
                        "roster is invalid."
                    )
                by_tier_total = 0
                for tier, metric in by_tier.items():
                    metric_error = _tier_metric_validation_error(
                        metric,
                        path=f"realized.by_book[{book}].by_tier[{tier}]",
                        lane_name="realized",
                        min_forward_n=min_forward_n,
                        min_forward_event_clusters=min_forward_event_clusters,
                    )
                    if metric_error:
                        return metric_error
                    by_tier_total += int(metric["n"])
                if by_tier_total != int(book_overall["n"]):
                    return (
                        f"Tier-performance realized.by_book[{book}].by_tier "
                        "total is inconsistent."
                    )
                book_total += int(book_overall["n"])
            if book_total != n:
                return "Tier-performance realized.by_book total is inconsistent."
        lane_states.append((n, str(evidence_status)))

    if any(status == "FORWARD_SAMPLE_AVAILABLE" for _n, status in lane_states):
        expected_status = "FORWARD_SAMPLE_AVAILABLE"
    elif any(n > 0 for n, _status in lane_states):
        expected_status = "INSUFFICIENT_SAMPLE"
    else:
        expected_status = "COLLECTING_FORWARD_EVIDENCE"
    if report.get("status") != expected_status:
        return "Tier-performance report status is inconsistent with its evidence lanes."
    return None


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def session_authorization_state(runtime_dir: Path) -> dict[str, Any]:
    """Summarize the operator session authorization with explicit expiry truth.

    A LIVE session file whose ``expires_at`` has passed is the daemon's cue to
    fall back to SHADOW; surface that state loudly instead of leaving the
    operator to infer it from the heartbeat mode.
    """
    session = _load_json(runtime_dir / "session.json")
    if not isinstance(session, dict) or not session:
        return {"present": False, "mode": None, "status": "NO_SESSION_FILE"}
    expires_raw = session.get("expires_at")
    expired: bool | None = None
    seconds_remaining: float | None = None
    try:
        expires = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
        if expires.tzinfo is not None:
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            seconds_remaining = round(remaining, 1)
            expired = remaining <= 0
    except (TypeError, ValueError):
        pass
    mode = str(session.get("mode") or "").upper() or None
    if mode == "LIVE" and expired:
        status = "LIVE_AUTHORIZATION_EXPIRED"
    elif mode == "LIVE" and expired is False:
        status = "LIVE_AUTHORIZED"
    elif mode:
        status = mode
    else:
        status = "UNKNOWN"
    return {
        "present": True,
        "mode": mode,
        "operator": session.get("operator"),
        "started_at": session.get("started_at"),
        "expires_at": expires_raw,
        "expired": expired,
        "seconds_remaining": seconds_remaining,
        "limit_orders_only": bool(session.get("limit_orders_only")),
        "status": status,
    }


def _bleeding_by_specialist(loss_attribution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """WS-B: the single worst bleeding grading scope per specialist, from
    ``runtime/autonomy/loss_attribution.json``. Fail-closed: absent/malformed
    artifact or no bleeding scopes -> {} (the council panel then shows no
    "where we bleed" line for anyone, never a fabricated one)."""
    worst: dict[str, dict[str, Any]] = {}
    for entry in (loss_attribution or {}).get("scopes") or []:
        if not isinstance(entry, dict) or entry.get("verdict") != "bleeding":
            continue
        scope = str(entry.get("scope") or "")
        specialist = scope.split("|", 1)[0]
        if not specialist:
            continue
        edge = entry.get("cluster_edge")
        if edge is None:
            continue
        current = worst.get(specialist)
        if current is None or float(edge) < float(current.get("cluster_edge") or 0.0):
            worst[specialist] = entry
    return worst


def _council_panel(
    council_snapshot: dict[str, Any],
    season_state: dict[str, Any],
    backtest: dict[str, Any],
    clv_report: dict[str, Any],
    loss_attribution: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Roll up one dashboard row per specialist (WS-13, read-only view).

    ``council_snapshot`` (runtime/autonomy/council_snapshot.json) supplies
    the live-registry fields the dashboard process can't compute itself
    (status, in_season from a team-league specialist's own health(), games
    seen, open opportunities this pass) -- see autonomy/council_snapshot.py
    for the writer contract. Everything else comes from artifacts the
    dashboard already loads: ``season_state`` (runtime/autonomy/
    season_state.json, the SAME persisted file SeasonMonitor.snapshot()
    would return, read directly since this process holds no live monitor)
    fills in in_season for specialists whose health() doesn't stamp it
    (e.g. MLB); ``backtest["trust_surface_by_specialist"]`` (WS-8's
    taxonomy-keyed contested-Brier surface, already computed in
    assemble_dashboard_state) is summed across its market_type/phase buckets
    per specialist; ``clv_report["scopes"]`` (WS-8 CLV, already loaded) is
    entries-weighted across market types per specialist.

    Fail-closed: no council_snapshot -> no rows (empty panel, never a
    crash); any datum this function can't resolve for a row is left None,
    rendered as "-" by the UI, never fabricated.
    """
    specialists = (council_snapshot or {}).get("specialists") or []
    if not specialists:
        return []

    trust_by_specialist: dict[str, dict[str, Any]] = {}
    for bucket in (backtest.get("trust_surface_by_specialist") or {}).values():
        name = (bucket or {}).get("specialist")
        if not name:
            continue
        agg = trust_by_specialist.setdefault(name, {"n": 0, "contested_n": 0, "brier_weighted": 0.0})
        n = int(bucket.get("n") or 0)
        contested_n = int(bucket.get("contested_n") or 0)
        agg["n"] += n
        agg["contested_n"] += contested_n
        if bucket.get("mean_brier") is not None and contested_n:
            agg["brier_weighted"] += contested_n * float(bucket["mean_brier"])

    clv_by_specialist: dict[str, dict[str, Any]] = {}
    for scope in (clv_report.get("scopes") or {}).values():
        name = (scope or {}).get("specialist")
        if not name or scope.get("clv_bps_mean") is None:
            continue
        agg = clv_by_specialist.setdefault(name, {"n_entries": 0, "bps_weighted": 0.0})
        n_entries = int(scope.get("n_entries") or 0)
        agg["n_entries"] += n_entries
        agg["bps_weighted"] += n_entries * float(scope["clv_bps_mean"])

    # WS-B: worst bleeding grading scope per specialist, from the loss
    # engine's read-only artifact. Fail-closed to {} -> no line for anyone.
    bleeding = _bleeding_by_specialist(loss_attribution or {})

    rows: list[dict[str, Any]] = []
    for entry in specialists:
        name = entry.get("name")
        details = entry.get("details") or {}
        in_season = details.get("in_season")
        if in_season is None:
            season_entry = season_state.get(name) if isinstance(season_state, dict) else None
            if isinstance(season_entry, dict):
                in_season = season_entry.get("active")
        games_seen = details.get("games_seen")
        if games_seen is None:
            games_seen = details.get("score_games_seen")
        trust = trust_by_specialist.get(name) or {}
        contested_n = int(trust.get("contested_n") or 0)
        contested_brier = (
            round(trust["brier_weighted"] / contested_n, 4)
            if contested_n and trust.get("brier_weighted") is not None else None
        )
        clv = clv_by_specialist.get(name) or {}
        clv_entries = int(clv.get("n_entries") or 0)
        clv_bps = round(clv["bps_weighted"] / clv_entries, 1) if clv_entries else None
        bleed = bleeding.get(name)
        where_we_bleed = (
            f"{bleed['scope']} edge {bleed['cluster_edge']} ({bleed['n_clusters']} clusters)"
            if bleed else None
        )
        rows.append({
            "name": name,
            "status": entry.get("status"),
            "in_season": in_season,
            "games_seen": games_seen,
            "settled_n": trust.get("n") or 0,
            "contested_n": contested_n,
            "contested_brier": contested_brier,
            "clv_bps": clv_bps,
            "where_we_bleed": where_we_bleed,
            "open_opportunities": entry.get("open_opportunities", 0),
        })
    return rows


def _sports_clv_summary(clv_report: dict[str, Any]) -> dict[str, Any]:
    """Compact sports-CLV rollup for the status payload (Wave-2 D1).

    Surfaces, per sports specialist, the graded ``market_type`` scopes and
    their CI-lower sign -- the exact evidence that lowers a sports scope's
    auto-promotion cluster bar from 450 (no CLV) to 300 (CLV present) and
    that the ladder's ``clv_ci95_lower > 0`` criterion consumes. Read-only,
    fail-closed to an empty rollup when the report has no sports scopes.
    """
    from autonomy.sports_clv import SPORTS_SPECIALISTS

    by_specialist: dict[str, list[dict[str, Any]]] = {}
    positive = 0
    for key, scope in (clv_report.get("scopes") or {}).items():
        if not isinstance(scope, dict):
            continue
        name = scope.get("specialist")
        if name not in SPORTS_SPECIALISTS:
            continue
        lower = scope.get("clv_bps_ci95_lower")
        if lower is not None and float(lower) > 0.0:
            positive += 1
        by_specialist.setdefault(name, []).append({
            "scope": key,
            "market_type": scope.get("market_type"),
            "clv_bps_mean": scope.get("clv_bps_mean"),
            "clv_bps_ci95_lower": lower,
            "n_entries": scope.get("n_entries"),
            "n_event_clusters": scope.get("n_event_clusters"),
        })
    scope_count = sum(len(v) for v in by_specialist.values())
    return {
        "instrumented": scope_count > 0,
        "n_scopes": scope_count,
        "n_scopes_ci_lower_positive": positive,
        "specialists": sorted(by_specialist),
        "by_specialist": by_specialist,
    }


def assemble_dashboard_state(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Assemble the full read-only dashboard state (pure)."""
    rd = runtime_dir or RUNTIME_DIR
    heartbeat = _load_json(rd / "heartbeat.json") or {"alive": False}
    cycles = _tail_jsonl(rd / "cycles.jsonl", 30)
    alerts = _tail_jsonl(rd / "alerts.jsonl", 20)
    risk_state = _load_json(rd / "risk_state_live.json")
    live_account = _live_account_status(rd)
    simulation_training = _load_json(rd / "simulation_training_latest.json") or {}
    crypto_paper_twin = _load_json(rd / "crypto_paper_twin_latest.json") or {}
    mispricing_monitor = _load_json(rd / "mispricing_monitor_latest.json") or {}
    clv_report = _load_json(rd / "clv_report.json") or {}
    # WS-13: council panel inputs. council_snapshot.json is written by the
    # mispricing monitor's live SpecialistRegistry each pass (autonomy/
    # council_snapshot.py); season_state.json is the SAME file
    # SeasonMonitor.snapshot() would return, read directly since this
    # process holds no live monitor. Both fail-closed to {} when absent.
    council_snapshot = _load_json(rd / "council_snapshot.json") or {}
    season_state = _load_json(rd / "season_state.json") or {}
    # WS-B: loss-deconstruction evolution engine artifact (read-only,
    # fail-closed to {} when absent -- see autonomy/loss_engine.py).
    loss_attribution = _load_json(rd / "loss_attribution.json") or {}
    # Autonomous thresholded promotion (owner directive 2026-07-16): the daily
    # engine's state artifact -- promotions/escalations/demotions/aborts with
    # hash-chain refs. Read-only, fail-closed to {} when absent.
    auto_promotion = _load_json(rd / "auto_promotion_state.json") or {}
    from autonomy.paper_dashboard import assemble_paper_dashboard, scheduled_task_status
    from autonomy.sports.dashboard import SPORTS_TASK_NAME, assemble_sports_dashboard

    paper_operation = assemble_paper_dashboard(rd)
    sports_operation = assemble_sports_dashboard(rd)

    def _task_status(task_name: str) -> dict[str, Any]:
        if runtime_dir is None:
            return scheduled_task_status(task_name)
        return {
            "task_name": task_name,
            "supported": False,
            "enabled": False,
            "state": "ALTERNATE_RUNTIME",
            "healthy": False,
        }

    paper_scheduler = _task_status("DummyCryptoPaperTwin")
    sports_scheduler = _task_status(SPORTS_TASK_NAME)
    scheduler_fleet = [
        {
            "role": "retired shadow research (non-authoritative)",
            "execution_authority": False,
            "can_gate_sports_grades": False,
            "can_gate_live": False,
            **_task_status(SHADOW_TASK_NAME),
        },
        {
            "role": "retired crypto paper research (non-authoritative)",
            "execution_authority": False,
            "can_gate_sports_grades": False,
            "can_gate_live": False,
            **paper_scheduler,
        },
        {
            "role": "sports research simulation (non-authoritative)",
            "execution_authority": False,
            "can_gate_sports_grades": False,
            "can_gate_live": False,
            **sports_scheduler,
        },
        {
            "role": "authoritative sports model seed",
            "authority_scope": "sports_grade_freshness_only",
            "execution_authority": False,
            "can_gate_sports_grades": True,
            "can_gate_live": False,
            **_task_status(SPORTS_MODEL_SEED_TASK_NAME),
        },
        {
            "role": "authoritative sports quote board",
            "authority_scope": "sports_quote_display_freshness_only",
            "execution_authority": False,
            "can_gate_sports_grades": False,
            "can_gate_live": False,
            **_task_status(SPORTS_BOARD_REFRESH_TASK_NAME),
        },
        {"role": "simulation trainer", **_task_status(TRAINER_TASK_NAME)},
        {
            "role": "legacy mispricing research (non-authoritative)",
            "execution_authority": False,
            "can_gate_sports_grades": False,
            "can_gate_live": False,
            **_task_status(MISPRICING_TASK_NAME),
        },
        {"role": "dashboard", **_task_status(DASHBOARD_TASK_NAME)},
    ]
    session = session_authorization_state(rd)

    ledger_summary: dict[str, Any] = {}
    statistics_intake: dict[str, Any] = {}
    canary: dict[str, Any] = {}
    backtest: dict[str, Any] = {}
    if os.environ.get("DUMMY_DASHBOARD_LIVE_LEDGER", "0") == "1":
        # Opt-in only. The full backtest holds a SHARED lock over ~10M rows for
        # minutes, which blocks the shadow brain's commit ("database is locked").
        # Default reads the persisted snapshot instead — see dashboard_snapshot.py.
        try:
            from autonomy.backtest import run_backtest
            from autonomy.canary import evaluate_canary_readiness
            from autonomy.ledger import AutonomyLedger

            ledger = AutonomyLedger(db_path=rd / "ledger.db")
            try:
                ledger_summary = ledger.performance_summary()
                statistics_intake = ledger.external_observation_summary()
                backtest = run_backtest(ledger, bootstrap_weights=False)
                historical_canary = evaluate_canary_readiness(
                    ledger, backtest_report=backtest,
                ).to_dict()
                canary = _retired_paper_canary_status(historical_canary)
            finally:
                ledger.close()
        except Exception as exc:
            ledger_summary = {"error": f"{type(exc).__name__}"}
    else:
        from autonomy.dashboard_snapshot import read_dashboard_snapshot

        snap = read_dashboard_snapshot(rd / "latest_dashboard_snapshot.json")
        if snap:
            ledger_summary = snap.get("ledger_summary") or {}
            statistics_intake = snap.get("statistics_intake") or {}
            backtest = snap.get("backtest") or {}
            canary = _retired_paper_canary_status(snap.get("canary") or {})
        else:
            ledger_summary = {"note": "dashboard snapshot pending (written by daemon recalibration)"}

    canary = _retired_paper_canary_status(canary)

    # Compress the backtest to a per-source scoreboard for the UI.
    scoreboard = []
    for source, s in (backtest.get("sources") or {}).items():
        scoreboard.append({
            "source": source,
            "n": s.get("n"),
            "mean_brier": s.get("mean_brier"),
            "beat_market_rate": s.get("beat_market_rate"),
            "contested_n": s.get("contested_n"),
            "contested_beat_rate": s.get("contested_beat_rate"),
            "contested_edge_lower": (
                (s.get("contested_mean_brier_edge_ci95") or {}).get("lower")
            ),
            "calibration_error": s.get("expected_calibration_error"),
            "weight": (backtest.get("derived_weights") or {}).get(source),
        })
    scoreboard.sort(key=lambda r: (r["beat_market_rate"] or 0), reverse=True)

    try:
        council = _council_panel(
            council_snapshot, season_state, backtest, clv_report, loss_attribution,
        )
    except Exception:
        council = []  # fail-closed: a malformed snapshot must never break the dashboard

    now_epoch = datetime.now(timezone.utc).timestamp()
    sports_simulation = _load_json(rd / "sports_simulation_latest.json") or {}
    sports_model_seed = _load_json(rd / SPORTS_MODEL_SEED_STATUS_FILE) or {}
    watchdog_status = _dashboard_watchdog_status(rd, now_epoch)
    panel_sources = {
        "heartbeat": heartbeat,
        "live_account": live_account,
        "sports_model_seed": sports_model_seed,
        "mispricing_monitor": mispricing_monitor,
        "crypto_paper_twin": crypto_paper_twin,
        "sports_simulation": sports_simulation,
        "simulation_training": simulation_training,
        "readiness_report": _load_json(rd / "readiness_report.json") or {},
        "council_snapshot": council_snapshot,
        "clv_report": clv_report,
    }
    data_ages: dict[str, Any] = {}
    for name, payload in panel_sources.items():
        data_ages[name] = _panel_data_age(name, payload, now_epoch)

    return {
        "generated_at": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
        "data_ages": data_ages,
        "watchdog": watchdog_status,
        "heartbeat": heartbeat,
        "session": session,
        "live_controls": _live_controls_status(),
        "live_account": live_account,
        "paper_results": {
            "status": "RETIRED_NON_AUTHORITATIVE",
            "execution_authority": False,
            "can_enable_live": False,
            "can_block_live": False,
            "raw_history_preserved": True,
        },
        "scheduler_fleet": scheduler_fleet,
        "risk_state": risk_state,
        "ledger": ledger_summary,
        "canary": canary,
        "scoreboard": scoreboard,
        "settled_markets": backtest.get("settled_markets", 0),
        "realized_shadow_pnl_cents": backtest.get("realized_decision_pnl_cents", 0),
        "decision_policy": backtest.get("decision_policy", {}),
        "fill_conditioned_policy": backtest.get("fill_conditioned_decision_policy", {}),
        "shadow_ttl_sensitivity": backtest.get("shadow_ttl_sensitivity", {}),
        "crypto_diagnostics": backtest.get("crypto_diagnostics", {}),
        "crypto_challenger_gates": backtest.get("crypto_challenger_gates", {}),
        "signal_data_quality": backtest.get("signal_data_quality", {}),
        "tier_performance": backtest.get("tier_performance", {}),
        "statistics_intake": statistics_intake,
        "simulation_training": simulation_training,
        "crypto_paper_twin": crypto_paper_twin,
        "sports_model_seed": sports_model_seed,
        "mispricing_monitor": mispricing_monitor,
        "mispricing_monitor_authority": dict(MISPRICING_MONITOR_AUTHORITY),
        "clv_report": clv_report,
        "sports_clv": _sports_clv_summary(clv_report),
        "loss_attribution": loss_attribution,
        "auto_promotion": auto_promotion,
        "council": council,
        "paper_operation": paper_operation,
        "paper_scheduler": paper_scheduler,
        "sports_operation": sports_operation,
        "sports_scheduler": sports_scheduler,
        "execution_quality": (
            (backtest.get("execution_quality_by_book") or {}).get("shadow", {})
        ),
        "execution_drift": (
            (backtest.get("execution_drift_by_book") or {}).get("shadow", {})
        ),
        "scale_readiness": (canary.get("evidence") or {}).get("scale_readiness", {}),
        "recent_cycles": cycles[-10:],
        "bankroll_curve": [
            {"at": c.get("at"), "bankroll": c.get("bankroll_cents"), "stage": c.get("stage")}
            for c in cycles if c.get("bankroll_cents") is not None
        ][-30:],
        "alerts": alerts,
        # Wave-16: the mounted live-game poller's session summary.
        "live_poller": _load_json(rd / "live_poller_status.json") or {},
        # Wave-20: the machine's own ranked improvement plan.
        "self_improvement": _load_json(rd / "self_improvement_plan.json") or {},
        # Wave-22: the Universal Sports Engine sidecar's artifact summary.
        "use_sidecar": _use_sidecar_summary(rd),
        # Wave-26: the vNext sovereign-forecasting shadow runtime.
        "vnext_shadow": _load_json(rd / "vnext_shadow_status.json") or {},
        # Wave-35: operator control switches (main/crypto/sports-by-league/llm).
        "switches": _switches_summary(),
    }


def _switches_summary() -> dict[str, Any]:
    try:
        from autonomy.switches import Switches

        return Switches.load().summary()
    except Exception:
        return {}


def _live_controls_status() -> dict[str, Any]:
    """Local live-authority status; reads configuration only, never Kalshi."""
    try:
        from live_firewall.firewall import live_execution_authority_status

        return live_execution_authority_status()
    except Exception as exc:  # noqa: BLE001 -- dashboard must fail closed
        return {
            "state": "invalid_or_blocked",
            "execution_authority": False,
            "blocker": f"LIVE_AUTHORITY_STATUS_UNAVAILABLE:{type(exc).__name__}",
            "default_disabled": False,
            "proof_scope": "one_controlled_proof",
            "central_firewall_required": True,
            "limit_orders_only": True,
            "market_orders_allowed": False,
            "paper_results_authority": "RETIRED_NON_AUTHORITATIVE",
            "paper_results_can_enable_live": False,
            "paper_results_can_block_live": False,
            "broker_contacted": False,
        }


def _live_account_status(runtime_dir: Path) -> dict[str, Any]:
    """Read the validated cached Kalshi account artifact without broker I/O."""
    from autonomy.live_account_snapshot import read_live_account_snapshot

    account = read_live_account_snapshot(
        runtime_dir / "live_account_snapshot.json"
    )
    if account is not None:
        return {**account, "broker_contacted_by_dashboard": False}
    return {
        "schema": "dummy.live_account_snapshot",
        "version": 1,
        "generated_at": None,
        "status": "UNAVAILABLE",
        "stale": True,
        "reason": "missing_or_invalid_cached_artifact",
        "execution_authority": False,
        "balance_cents": None,
        "open_positions_count": None,
        "open_orders_count": None,
        "historical_orders_count": None,
        "order_status_counts": {},
        "source": {
            "provider": "kalshi",
            "authenticated": False,
            "data_class": "live_account_read_only",
        },
        "http_proof": {
            "get_only": None,
            "total_requests": 0,
            "mutation_count": 0,
        },
        "errors": [],
        "broker_contacted_by_dashboard": False,
    }


def _retired_paper_canary_status(value: dict[str, Any] | None) -> dict[str, Any]:
    """Expose legacy paper readiness as audit metadata, never authority."""
    value = value if isinstance(value, dict) else {}
    return {
        "status": "RETIRED_NON_AUTHORITATIVE",
        "ready": False,
        "execution_authority": False,
        "can_enable_live": False,
        "can_block_live": False,
        "historical_research_ready": bool(
            value.get("historical_research_ready", value.get("ready"))
        ),
    }


def _use_sidecar_summary(rd: Path) -> dict[str, Any]:
    predictions = _load_json(rd / "use_predictions.json") or {}
    provenance: dict[str, int] = {}
    for row in predictions.get("rows") or []:
        if isinstance(row, dict) and "error" not in row:
            key = str(row.get("provenance"))
            provenance[key] = provenance.get(key, 0) + 1
    try:
        with (rd / "use_outcomes.jsonl").open(encoding="utf-8") as fh:
            outcomes = sum(1 for _ in fh)
    except OSError:
        outcomes = 0
    return {
        "status": predictions.get("status"),
        "generated_at": predictions.get("generated_at"),
        "predictions": sum(provenance.values()),
        "provenance": provenance,
        "outcomes_on_tape": outcomes,
    }


def assemble_status_snapshot(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Fast, precomputed operator snapshot -- reads fresh runtime JSON only.

    This NEVER touches ledger.db (no backtest, no bootstrap, no canary): it is
    the responsive endpoint the dashboard falls back to while the heavy
    /api/autonomy report is (re)computing. Every panel carries an explicit age
    and stale flag so stale data is visibly stale rather than shown as healthy.
    """
    rd = runtime_dir or RUNTIME_DIR
    now_epoch = datetime.now(timezone.utc).timestamp()

    heartbeat = _load_json(rd / "heartbeat.json") or {"alive": False}
    live_account = _live_account_status(rd)
    panels_raw = {
        "heartbeat": heartbeat,
        "live_account": live_account,
        "sports_model_seed": (
            _load_json(rd / SPORTS_MODEL_SEED_STATUS_FILE) or {}
        ),
        "mispricing_monitor": _load_json(rd / "mispricing_monitor_latest.json") or {},
        "crypto_paper_twin": _load_json(rd / "crypto_paper_twin_latest.json") or {},
        "sports_simulation": _load_json(rd / "sports_simulation_latest.json") or {},
        "simulation_training": _load_json(rd / "simulation_training_latest.json") or {},
        "readiness_report": _load_json(rd / "readiness_report.json") or {},
        "council_snapshot": _load_json(rd / "council_snapshot.json") or {},
        "clv_report": _load_json(rd / "clv_report.json") or {},
        "execution_tournament": _load_json(rd / "execution_tournament.json") or {},
    }
    data_ages: dict[str, Any] = {}
    for name, payload in panels_raw.items():
        data_ages[name] = _panel_data_age(name, payload, now_epoch)

    watchdog_status = _dashboard_watchdog_status(rd, now_epoch)
    return {
        "generated_at": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
        "source": "status_snapshot",
        "ledger_touched": False,
        "heartbeat": heartbeat,
        "session": session_authorization_state(rd),
        "live_controls": _live_controls_status(),
        "live_account": live_account,
        "paper_results": {
            "status": "RETIRED_NON_AUTHORITATIVE",
            "execution_authority": False,
            "can_enable_live": False,
            "can_block_live": False,
            "raw_history_preserved": True,
        },
        "risk_state": _load_json(rd / "risk_state_live.json"),
        "risk_state_scope": "live",
        "watchdog": watchdog_status,
        "data_ages": data_ages,
        "sports_model_seed": panels_raw["sports_model_seed"],
        "mispricing_monitor": panels_raw["mispricing_monitor"],
        "mispricing_monitor_authority": dict(MISPRICING_MONITOR_AUTHORITY),
        "crypto_paper_twin": panels_raw["crypto_paper_twin"],
        "sports_simulation": panels_raw["sports_simulation"],
        "simulation_training": panels_raw["simulation_training"],
        "readiness_report": panels_raw["readiness_report"],
        "clv_report": panels_raw["clv_report"],
        "sports_clv": _sports_clv_summary(panels_raw["clv_report"]),
        "execution_tournament": _tournament_status_panel(panels_raw["execution_tournament"]),
        "alerts": _tail_jsonl(rd / "alerts.jsonl", 20),
        "recent_cycles": _tail_jsonl(rd / "cycles.jsonl", 10),
        # Both are cheap runtime-file reads (no ledger), so they belong in the
        # fast snapshot too: /api/autonomy 503s under a busy ledger, and without
        # these the vNext and USE cards would render blank on that fallback.
        "vnext_shadow": _load_json(rd / "vnext_shadow_status.json") or {},
        "use_sidecar": _use_sidecar_summary(rd),
        "switches": _switches_summary(),
    }


def _tournament_status_panel(report: dict[str, Any]) -> dict[str, Any]:
    """Compact execution-tournament view for the /api/status payload."""
    if not report or not report.get("report_name"):
        return {}
    try:
        from autonomy.execution_tournament import summarize_tournament

        return summarize_tournament(report)
    except Exception:
        return {
            "report_name": report.get("report_name"),
            "ranking": report.get("ranking", []),
            "headline": report.get("headline", {}),
            "generated_at": report.get("generated_at"),
        }


_HTML = DASHBOARD_HTML
_html_state: dict[str, Any] = {"mtime": None}


# Historical shadow/paper economics and promotion machinery may remain
# available for audit, but they are not current operator state and have no live
# authority.  Keep this boundary list centralized so both fresh and cached
# legacy /api/autonomy payloads are quarantined consistently.
_RETIRED_AUTONOMY_FIELDS = (
    "ledger",
    "canary",
    "settled_markets",
    "realized_shadow_pnl_cents",
    "decision_policy",
    "fill_conditioned_policy",
    "shadow_ttl_sensitivity",
    "crypto_diagnostics",
    "crypto_challenger_gates",
    "tier_performance",
    "crypto_paper_twin",
    "clv_report",
    "sports_clv",
    "loss_attribution",
    "auto_promotion",
    "paper_operation",
    "paper_scheduler",
    "sports_operation",
    "sports_scheduler",
    "execution_quality",
    "execution_drift",
    "scale_readiness",
    "recent_cycles",
    "bankroll_curve",
)
_RETIRED_DATA_AGE_FIELDS = (
    "crypto_paper_twin",
    "sports_simulation",
)


def sanitize_autonomy_response(value: dict[str, Any] | None) -> dict[str, Any]:
    """Quarantine legacy paper results outside current /api/autonomy state.

    This is deliberately an API-boundary copy: raw artifacts and ledger rows
    are neither rewritten nor deleted.  Reapplying it is idempotent, which
    keeps both warm cached responses and freshly assembled legacy payloads safe.
    """
    result = dict(value or {})
    existing_history = result.pop("retired_audit_history", {})
    history = dict(existing_history) if isinstance(existing_history, dict) else {}

    for field in _RETIRED_AUTONOMY_FIELDS:
        if field in result:
            history[field] = result.pop(field)

    data_ages = result.get("data_ages")
    if isinstance(data_ages, dict):
        current_ages = dict(data_ages)
        retired_ages = dict(history.get("data_ages") or {})
        for field in _RETIRED_DATA_AGE_FIELDS:
            if field in current_ages:
                retired_ages[field] = current_ages.pop(field)
        result["data_ages"] = current_ages
        if retired_ages:
            history["data_ages"] = retired_ages

    scheduler_fleet = result.get("scheduler_fleet")
    if isinstance(scheduler_fleet, list):
        current_schedulers: list[Any] = []
        retired_schedulers = list(history.get("scheduler_fleet") or [])
        for row in scheduler_fleet:
            role = str(row.get("role", "")).lower() if isinstance(row, dict) else ""
            if "paper" in role:
                retired_schedulers.append(row)
            else:
                current_schedulers.append(row)
        result["scheduler_fleet"] = current_schedulers
        if retired_schedulers:
            history["scheduler_fleet"] = retired_schedulers

    retirement = {
        "status": "RETIRED_NON_AUTHORITATIVE",
        "execution_authority": False,
        "can_enable_live": False,
        "can_block_live": False,
        "raw_history_preserved": True,
    }
    history.update(retirement)
    result["retired_audit_history"] = history
    result["paper_results"] = dict(retirement)
    return result


def _current_html() -> str:
    """Serve the dashboard HTML, hot-reloading ``dashboard_ui.py`` when it
    changes on disk -- so a UI edit goes live on the next request without
    restarting the uvicorn server (the HTML used to be frozen at import time,
    which is why frontend changes appeared stale until a manual restart). Falls
    back to the import-time copy on any reload error."""
    import importlib

    from autonomy import dashboard_ui as _mod
    try:
        mtime = os.path.getmtime(_mod.__file__)
        if mtime != _html_state["mtime"]:
            importlib.reload(_mod)
            _html_state["mtime"] = mtime
        return _mod.DASHBOARD_HTML
    except Exception:  # noqa: BLE001
        return _HTML


def build_app():
    """Construct the evidence dashboard and paper-scheduler control surface."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from autonomy.paper_dashboard import (
        PAPER_CONTROL_HEADER,
        control_paper_scheduler,
        scheduled_task_status,
    )
    from autonomy.sports.dashboard import SPORTS_TASK_NAME

    import os
    import threading
    from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout

    app = FastAPI(title="Dummy Autonomy Dashboard")
    # The /api/autonomy report includes a 1,000-resample cluster bootstrap over
    # a multi-gigabyte ledger and can exceed a browser/proxy timeout on a cold
    # cache. Guard it: a 30-second cache serves warm polls; a cold poll kicks
    # the heavy assembly onto a background worker and waits only up to a bounded
    # deadline. If the deadline passes it returns 503 pointing at /api/status
    # (which never touches ledger.db) instead of blocking the event loop, while
    # the background job keeps running to populate the cache for the next poll.
    state_cache: dict[str, Any] = {"at": 0.0, "value": None, "epoch": 0}
    compute_lock = threading.Lock()
    pending: dict[str, Future | None] = {"future": None}
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dashboard-state")
    deadline_seconds = float(os.environ.get("DUMMY_DASHBOARD_STATE_DEADLINE_SECONDS", "20"))
    # The heavy /api/autonomy report runs a backtest that holds the (large,
    # non-WAL) ledger; each assembly is a lock window the brain's write can
    # collide with. A longer cache TTL means fewer such reads. Env-tunable;
    # raised 30 -> 120s to cut ledger contention (the report is evidence, not
    # a hot control surface, so a couple minutes of staleness is fine).
    state_ttl_seconds = float(os.environ.get("DUMMY_DASHBOARD_STATE_TTL_SECONDS", "120"))

    def _store(epoch_at_submit: int, assembled: dict[str, Any]) -> None:
        # A control action can invalidate the cache while this expensive report
        # assembles. Never let that stale request overwrite post-control state.
        safe_assembled = sanitize_autonomy_response(assembled)
        with compute_lock:
            if epoch_at_submit == int(state_cache["epoch"]):
                state_cache["value"] = safe_assembled
                state_cache["at"] = _monotonic()

    def _ensure_compute() -> tuple[Future, int]:
        with compute_lock:
            fut = pending["future"]
            epoch_at_submit = int(state_cache["epoch"])
            if fut is not None and not fut.done():
                return fut, epoch_at_submit
            new_fut = worker.submit(assemble_dashboard_state)
            pending["future"] = new_fut
        # Populate the cache even when the requester times out below. Attached
        # OUTSIDE compute_lock: a future that finished already runs its callback
        # synchronously here, and _store re-acquires the (non-reentrant) lock.
        new_fut.add_done_callback(
            lambda f: _store(epoch_at_submit, f.result()) if not f.cancelled() and f.exception() is None else None
        )
        return new_fut, epoch_at_submit

    @app.get("/api/autonomy")
    def api_state() -> JSONResponse:
        now = _monotonic()
        if state_cache["value"] is not None and now - float(state_cache["at"]) < state_ttl_seconds:
            return JSONResponse(sanitize_autonomy_response(state_cache["value"]))
        fut, epoch_at_submit = _ensure_compute()
        try:
            assembled = fut.result(timeout=deadline_seconds)
            _store(epoch_at_submit, assembled)  # inline: no callback-ordering race
            return JSONResponse(sanitize_autonomy_response(assembled))
        except FutureTimeout:
            # Serve a stale cached value rather than nothing, if we have one.
            if state_cache["value"] is not None:
                payload = sanitize_autonomy_response(state_cache["value"])
                payload["stale_cache"] = True
                return JSONResponse(payload)
            return JSONResponse(
                {
                    "status": "COMPUTING",
                    "detail": (
                        "The full evidence report is still assembling "
                        "(cluster bootstrap over the ledger). Poll /api/status "
                        "for the fast precomputed snapshot in the meantime."
                    ),
                    "hint": "/api/status",
                },
                status_code=503,
            )

    @app.get("/api/status")
    def api_status() -> JSONResponse:
        # Fast, precomputed snapshot: fresh runtime JSON + watchdog only, never
        # ledger.db. Always responsive, even while /api/autonomy recomputes.
        return JSONResponse(assemble_status_snapshot())

    @app.get("/api/walk_forward")
    def api_walk_forward() -> JSONResponse:
        # Point-in-time Glicko-2 backtest per league from the history lake
        # (written by the walk-forward task). Static artifact; never the ledger.
        return JSONResponse(_load_json(RUNTIME_DIR / "sports_walk_forward.json") or {})

    @app.get("/api/bet_board")
    def api_bet_board() -> JSONResponse:
        # The request path is artifact-only. A stale cycle artifact remains
        # visible but labelled; missing/invalid artifacts fail explicitly and
        # never trigger a scan of the busy signal ledger.
        from autonomy.bet_board import read_current_board_artifact
        from autonomy.sports_markets import SPORTS_LEAGUES

        try:
            board = read_current_board_artifact(
                RUNTIME_DIR / "bet_board.json",
                display_path=RUNTIME_DIR / "bet_board_display.json",
            )
            available = board.get("artifact_status") in {"FRESH", "STALE"}
            return JSONResponse(board, status_code=200 if available else 503)
        except Exception as exc:
            return JSONResponse({
                "artifact_status": "UNAVAILABLE",
                "error": f"{type(exc).__name__}: {exc}"[:200],
                "generated_at": None,
                "age_seconds": None,
                "stale": True,
                "rows": 0,
                "groups": {},
                "top": [],
                "sports_leagues": list(SPORTS_LEAGUES),
                "sports_league_roster_kind": (
                    "year_round_navigation_not_current_listings"
                ),
            }, status_code=503)

    @app.get("/api/tier-performance")
    def api_tier_performance() -> JSONResponse:
        """Persisted evidence plus current board counts; never scans ledger.db."""
        try:
            from autonomy.bet_board import (
                current_board_tier_distribution,
                read_current_board_artifact,
            )
            from autonomy.dashboard_snapshot import read_dashboard_snapshot
            from autonomy.tier_policy import (
                TIER_POLICY_SHA256,
                TIER_POLICY_SPEC,
                TIER_POLICY_VERSION,
            )
            from autonomy.tier_performance import (
                MIN_FORWARD_EVENT_CLUSTERS,
                MIN_FORWARD_N,
            )

            snap = read_dashboard_snapshot(
                RUNTIME_DIR / "latest_dashboard_snapshot.json"
            )
            raw_report = (
                (snap.get("backtest") or {}).get("tier_performance")
                if isinstance(snap, dict)
                else None
            )
            report_validation_error = _tier_performance_validation_error(
                raw_report,
                expected_policy_version=TIER_POLICY_VERSION,
                expected_policy_sha256=TIER_POLICY_SHA256,
                expected_policy_spec=TIER_POLICY_SPEC,
                min_forward_n=MIN_FORWARD_N,
                min_forward_event_clusters=MIN_FORWARD_EVENT_CLUSTERS,
            )
            validation_error = report_validation_error
            trusted_reported_status = (
                raw_report.get("status")
                if report_validation_error is None and isinstance(raw_report, dict)
                else None
            )
            backtest_stamp = (
                snap.get("backtest_generated_at") if isinstance(snap, dict) else None
            )
            tier_performance_stamp = (
                snap.get("tier_performance_generated_at")
                if isinstance(snap, dict)
                else None
            ) or backtest_stamp
            evidence_stamp = (
                tier_performance_stamp
                if isinstance(raw_report, dict) and bool(raw_report)
                else None
            )
            freshness = _tier_evidence_freshness(
                evidence_stamp,
                now_epoch=datetime.now(timezone.utc).timestamp(),
            )
            if freshness["evidence_time_status"] == "TIME_UNKNOWN":
                validation_error = validation_error or (
                    "Tier-performance evidence has no valid generation timestamp."
                )
            elif freshness["evidence_time_status"] == "FUTURE_SKEW":
                validation_error = validation_error or (
                    "Tier-performance evidence timestamp is too far in the future."
                )

            # Do not echo unvalidated metric lanes.  The UI renders table data
            # even when the top-level status is unavailable, so retaining a
            # forged/old-policy forecast block would still visually expose it.
            report = (
                dict(raw_report)
                if validation_error is None and isinstance(raw_report, dict)
                else {}
            )

            board = read_current_board_artifact(
                RUNTIME_DIR / "bet_board.json",
                display_path=RUNTIME_DIR / "bet_board_display.json",
            )
            board_available = board.get("artifact_status") in {"FRESH", "STALE"}
            report["current_distribution"] = current_board_tier_distribution(
                board if board_available else None
            )
            report["snapshot_generated_at"] = (
                snap.get("generated_at") if isinstance(snap, dict) else None
            )
            report["backtest_generated_at"] = backtest_stamp
            report["tier_performance_generated_at"] = tier_performance_stamp
            report.update(freshness)
            report["board_artifact_status"] = board.get("artifact_status")
            report["board_generated_at"] = board.get("generated_at")
            report["board_age_seconds"] = board.get("age_seconds")
            report["board_stale"] = board.get("stale")
            report["performance_artifact_status"] = (
                "MISSING"
                if not isinstance(raw_report, dict) or not raw_report
                else "INVALID"
                if validation_error
                else "VALID"
            )
            if validation_error or not board_available:
                report["performance_status"] = (
                    trusted_reported_status if validation_error else report.get("status")
                )
                report["status"] = "UNAVAILABLE"
                report["error"] = validation_error or (
                    board.get("error") or "Board artifact unavailable."
                )
            elif freshness["evidence_time_status"] == "STALE":
                report["performance_status"] = report.get("status")
                report["status"] = "STALE_EVIDENCE"
            available = not validation_error and board_available
            return JSONResponse(report, status_code=200 if available else 503)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({
                "status": "UNAVAILABLE",
                "error": f"{type(exc).__name__}: {exc}"[:200],
                "performance_artifact_status": "UNAVAILABLE",
                "performance_status": None,
                "evidence_generated_at": None,
                "evidence_age_seconds": None,
                "evidence_stale": True,
                "evidence_time_status": "TIME_UNKNOWN",
                "board_artifact_status": "UNAVAILABLE",
                "board_generated_at": None,
                "board_age_seconds": None,
                "board_stale": True,
                "current_distribution": {
                    "n": 0,
                    "counts": {
                        "A": 0,
                        "B": 0,
                        "C": 0,
                        "WATCH": 0,
                        "UNATTRIBUTED": 0,
                    },
                },
            }, status_code=503)

    @app.get("/api/model-arsenal")
    def api_model_arsenal() -> JSONResponse:
        """Read local, redacted four-model status without provider contact."""
        from dashboard.model_arsenal_status import build_model_arsenal_status

        return JSONResponse(build_model_arsenal_status())

    def _snapshot_block(key: str) -> dict[str, Any]:
        # Wave-51: serve the redesigned dashboard's overview / per-scope blocks
        # straight from the persisted snapshot artifact -- never opens the ledger,
        # always fast, and a missing block is an empty dict, never a 500.
        from autonomy.dashboard_snapshot import read_dashboard_snapshot

        snap = read_dashboard_snapshot(RUNTIME_DIR / "latest_dashboard_snapshot.json") or {}
        block = dict(snap.get(key) or {})
        if key == "overview":
            from autonomy.dashboard_snapshot import sanitize_primary_overview

            block = sanitize_primary_overview(block)
        snapshot_stamp = snap.get("generated_at")
        block_stamp = snap.get(f"{key}_generated_at") or snapshot_stamp
        block["generated_at"] = block_stamp
        block["snapshot_generated_at"] = snapshot_stamp
        block["data_age_seconds"] = _age_seconds(block_stamp, time.time())
        block["data_status"] = (snap.get("block_status") or {}).get(
            key,
            "LEGACY_SNAPSHOT" if block else "UNAVAILABLE",
        )
        error = (snap.get("block_errors") or {}).get(key)
        if error:
            block["data_error"] = error
        block["backtest_generated_at"] = snap.get("backtest_generated_at")
        return block

    @app.get("/api/overview")
    def api_overview() -> JSONResponse:
        try:
            block = _snapshot_block("overview")
            block["live_controls"] = _live_controls_status()
            block["live_account"] = _live_account_status(RUNTIME_DIR)
            block["paper_results_status"] = "RETIRED_NON_AUTHORITATIVE"
            block["paper_results_can_enable_live"] = False
            block["paper_results_can_block_live"] = False
            block["paper_history_preserved_for_audit"] = True
            return JSONResponse(block)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200]})

    @app.get("/api/scopes")
    def api_scopes() -> JSONResponse:
        # Wave-52: the graded scopes from the snapshot, each enriched with its
        # "other data" -- council/LLM row, CLV, live mispricing opportunities,
        # ejection/injury events -- read fresh from the runtime artifacts (no
        # ledger) so the live tape stays current between snapshots.
        from autonomy.sports_markets import SPORTS_LEAGUES

        try:
            block = _snapshot_block("scopes")
            block["sports_leagues"] = list(SPORTS_LEAGUES)
            block["sports_league_roster_kind"] = (
                "year_round_navigation_not_current_listings"
            )
            verticals = block.get("verticals") or {}
            # Older snapshots could call a league "in" merely because it had
            # an open pick, even with zero current-window grades.  Normalize
            # that impossible state at the artifact boundary so a preseason
            # NFL listing reads as upcoming, not as a season already underway.
            sports_scopes = (
                (verticals.get("SPORTS") or {}).get("scopes") or {}
            )
            for scope in sports_scopes.values():
                if not isinstance(scope, dict):
                    continue
                graded_raw = (scope.get("summary") or {}).get("n")
                graded = (
                    int(graded_raw)
                    if isinstance(graded_raw, (int, float))
                    and not isinstance(graded_raw, bool)
                    and math.isfinite(float(graded_raw))
                    else 0
                )
                if scope.get("in_season") is False:
                    scope["season_status"] = "off"
                elif graded == 0 and scope.get("season_status") == "in":
                    scope["season_status"] = "upcoming"
                    if scope.get("basis") == "current":
                        scope["basis"] = "none"
            scope_keys = [
                (vertical, label)
                for vertical, vblock in verticals.items()
                for label in (vblock.get("scopes") or {})
            ]
            if scope_keys:
                from autonomy.dashboard_snapshot import read_dashboard_snapshot
                from autonomy.scope_analytics import build_scope_extras

                snap = read_dashboard_snapshot(RUNTIME_DIR / "latest_dashboard_snapshot.json") or {}
                try:
                    council_rows = _council_panel(
                        _load_json(RUNTIME_DIR / "council_snapshot.json") or {},
                        _load_json(RUNTIME_DIR / "season_state.json") or {},
                        snap.get("backtest") or {},
                        _load_json(RUNTIME_DIR / "clv_report.json") or {},
                        _load_json(RUNTIME_DIR / "loss_attribution.json") or {},
                    )
                except Exception:  # noqa: BLE001
                    council_rows = []
                extras = build_scope_extras(RUNTIME_DIR, scope_keys, council_rows=council_rows)
                for vertical, vblock in verticals.items():
                    for label, scope in (vblock.get("scopes") or {}).items():
                        scope["extras"] = extras.get(vertical, {}).get(label, {})
            return JSONResponse(block)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({
                "error": f"{type(exc).__name__}: {exc}"[:200],
                "verticals": {},
                "sports_leagues": list(SPORTS_LEAGUES),
                "sports_league_roster_kind": (
                    "year_round_navigation_not_current_listings"
                ),
            })

    def _scheduler_control(
        action: str, request: Request, task_name: str | None = None
    ) -> JSONResponse:
        """Shared paper-scheduler control: CSRF header + loopback origin, fixed task.

        ``task_name=None`` targets the default crypto paper task and keeps the
        one-argument call contract the paper endpoint has always had.
        """
        if request.headers.get("x-dummy-paper-control") != PAPER_CONTROL_HEADER:
            raise HTTPException(status_code=403, detail="paper control header required")
        origin = request.headers.get("origin")
        if origin and urlparse(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise HTTPException(status_code=403, detail="loopback origin required")
        try:
            if task_name is None:
                result = control_paper_scheduler(action)
            else:
                result = control_paper_scheduler(action, task_name=task_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state_cache["epoch"] = int(state_cache["epoch"]) + 1
        state_cache["at"] = 0.0
        state_cache["value"] = None
        result["scheduler"] = (
            scheduled_task_status() if task_name is None else scheduled_task_status(task_name)
        )
        return JSONResponse(result, status_code=200 if result.get("ok") else 503)

    @app.post("/api/paper-scheduler/{action}")
    def paper_scheduler_control(action: str, request: Request) -> JSONResponse:
        return _scheduler_control(action, request)

    @app.post("/api/sports-paper-scheduler/{action}")
    def sports_paper_scheduler_control(action: str, request: Request) -> JSONResponse:
        return _scheduler_control(action, request, SPORTS_TASK_NAME)

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(_current_html())

    return app
