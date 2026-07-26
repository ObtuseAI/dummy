"""Loopback-only, query-only operator dashboard for the autonomy predator."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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
STATUS_TAIL_MAX_BYTES = 1_048_576
STATUS_CYCLE_WINDOW = 40
# Current boards legitimately contain thousands of rows. Keep a generous hard
# ceiling, but refuse to hand an arbitrarily large local artifact to the JSON
# parser from the latency-sensitive status endpoint.
STATUS_BOARD_MAX_BYTES = 32 * 1024 * 1024
STATUS_CAPS_MAX_BYTES = 64 * 1024
PROMOTION_STATUS_MAX_AGE_SECONDS = 172_800.0
EXECUTION_TOURNAMENT_MAX_AGE_SECONDS = 172_800.0
KXSOL15M_SERIES = "KXSOL15M"
KXSOL15M_SOURCE = "crypto_patience_confirm"
CAPS_CONFIG_PATH = Path("configs/caps.json")

MISPRICING_MONITOR_AUTHORITY = {
    "status": "LEGACY_RESEARCH_NON_AUTHORITATIVE",
    "execution_authority": False,
    "can_gate_sports_grades": False,
    "can_gate_live": False,
}

_LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
_TEST_CLIENT_NAME = "testclient"
_TEST_HOST_NAME = "testserver"
_DASHBOARD_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; "
        "connect-src 'self'; "
        "img-src data:; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'unsafe-inline'; "
        "font-src 'self'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    ),
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": (
        "camera=(), display-capture=(), geolocation=(), microphone=(), "
        "payment=(), usb=()"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _is_loopback_address(value: str | None, *, allow_test_name: bool = False) -> bool:
    """Return whether an ASGI peer/host is an explicit loopback address.

    Uvicorn supplies a numeric socket peer, so names other than ``localhost``
    are never resolved here. ``testclient`` is an in-process Starlette sentinel
    and cannot be supplied by a network socket.
    """
    candidate = str(value or "").strip().casefold().rstrip(".")
    if allow_test_name and candidate == _TEST_CLIENT_NAME:
        return True
    if candidate == "localhost":
        return True
    try:
        return ipaddress.ip_address(candidate.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


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
        epoch = float(value)
        return epoch if math.isfinite(epoch) else None
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


def _bounded_tail_text(path: Path, max_bytes: int = STATUS_TAIL_MAX_BYTES) -> str | None:
    """Read at most ``max_bytes`` from a file tail without trusting its size."""
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, 2)
            start = max(0, size - max_bytes)
            handle.seek(start)
            payload = handle.read(max_bytes)
    except OSError:
        return None
    if start:
        _, separator, payload = payload.partition(b"\n")
        if not separator:
            return None
    return payload.decode("utf-8", errors="replace")


def _bounded_file_bytes(
    path: Path,
    *,
    max_bytes: int = STATUS_TAIL_MAX_BYTES,
) -> tuple[bytes | None, str | None]:
    """Read a complete small artifact or return a fail-closed reason.

    Reading ``max_bytes + 1`` closes the stat/read race: even if a producer
    grows the file after a size check, the dashboard never buffers beyond the
    declared bound.
    """

    try:
        with path.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    if len(payload) > max_bytes:
        return None, "size_limit_exceeded"
    return payload, None


def _bounded_json_object(
    path: Path,
    *,
    max_bytes: int = STATUS_TAIL_MAX_BYTES,
) -> tuple[dict[str, Any] | None, str | None]:
    payload, error = _bounded_file_bytes(path, max_bytes=max_bytes)
    if payload is None:
        return None, error
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "not_an_object"
    return value, None


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    text = _bounded_tail_text(path)
    if text is None:
        return []
    out = []
    for line in text.strip().splitlines()[-limit:]:
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def _aware_timestamp(
    value: Any,
    *,
    now_epoch: float | None = None,
    future_tolerance_seconds: float = 300.0,
) -> tuple[float, str] | None:
    """Return a timezone-aware timestamp only; naive receipts are not evidence."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    normalized = parsed.astimezone(timezone.utc)
    epoch = normalized.timestamp()
    if now_epoch is not None and epoch - now_epoch > future_tolerance_seconds:
        return None
    return epoch, normalized.isoformat()


def _bounded_cycle_window(
    path: Path,
    *,
    limit: int = STATUS_CYCLE_WINDOW,
) -> tuple[list[dict[str, Any]], int]:
    """Collect the last valid cycle receipts from a bounded byte tail."""
    text = _bounded_tail_text(path)
    if text is None:
        return [], 0
    records: list[dict[str, Any]] = []
    malformed = 0
    for line in reversed(text.splitlines()):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            malformed += 1
            continue
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("status"), str)
            or not value["status"].strip()
        ):
            malformed += 1
            continue
        records.append(value)
        if len(records) >= limit:
            break
    records.reverse()
    return records, malformed


def _bounded_structured_records(
    path: Path,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Extract concatenated top-level JSON receipts from a bounded log tail."""
    text = _bounded_tail_text(path)
    if text is None:
        return []
    decoder = json.JSONDecoder()
    records: list[dict[str, Any]] = []
    position = 0
    while position < len(text):
        start = text.find("{", position)
        if start < 0:
            break
        line_start = text.rfind("\n", 0, start) + 1
        if start != line_start:
            position = start + 1
            continue
        try:
            value, end = decoder.raw_decode(text, start)
        except ValueError:
            position = start + 1
            continue
        if isinstance(value, dict):
            records.append(value)
        position = end
    return records[-limit:]


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _count_or_list_length(value: Any) -> int | None:
    count = _nonnegative_int(value)
    if count is not None:
        return count
    return len(value) if isinstance(value, list) else None


def _cycle_timestamp(
    record: dict[str, Any],
    *,
    now_epoch: float,
) -> tuple[float, str] | None:
    for field in ("completed_at", "at", "started_at"):
        parsed = _aware_timestamp(record.get(field), now_epoch=now_epoch)
        if parsed is not None:
            return parsed
    return None


def _ledger_health_status(
    runtime_dir: Path,
    *,
    heartbeat: dict[str, Any],
    watchdog: dict[str, Any],
    cycles: list[dict[str, Any]],
    now_epoch: float,
) -> dict[str, Any]:
    raw_health = heartbeat.get("ledger_health")
    health = raw_health if isinstance(raw_health, dict) else {}
    size_bytes = _nonnegative_int(health.get("size_bytes"))
    wal_size_bytes = _nonnegative_int(health.get("wal_size_bytes"))
    source = "heartbeat.ledger_health"
    wal_source = "heartbeat.ledger_health"
    if size_bytes is None:
        try:
            size_bytes = (runtime_dir / "ledger.db").stat().st_size
            source = "filesystem_stat"
        except OSError:
            size_bytes = None
    if wal_size_bytes is None:
        try:
            wal_size_bytes = (runtime_dir / "ledger.db-wal").stat().st_size
            wal_source = "filesystem_stat"
        except OSError:
            wal_size_bytes = None
            wal_source = "unavailable"

    sampled = _aware_timestamp(
        heartbeat.get("last_cycle_at"),
        now_epoch=now_epoch,
    )
    sampled_at = sampled[1] if sampled is not None else None
    if source == "filesystem_stat":
        sampled_at = datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat()

    max_gb = _finite_number(watchdog.get("ledger_max_gb"))
    threshold_bytes = None if max_gb is None or max_gb < 0 else round(max_gb * 1e9)
    over_threshold = watchdog.get("ledger_over_threshold")
    if not isinstance(over_threshold, bool):
        over_threshold = (
            size_bytes is not None
            and threshold_bytes is not None
            and size_bytes > threshold_bytes
        )

    samples: list[tuple[float, str, int]] = []
    for cycle in cycles:
        cycle_health = cycle.get("ledger_health")
        if not isinstance(cycle_health, dict):
            continue
        cycle_size = _nonnegative_int(cycle_health.get("size_bytes"))
        cycle_time = _cycle_timestamp(cycle, now_epoch=now_epoch)
        if cycle_size is None or cycle_time is None:
            continue
        samples.append((cycle_time[0], cycle_time[1], cycle_size))
    if size_bytes is not None and sampled is not None:
        samples.append((sampled[0], sampled[1], size_bytes))
    samples = sorted({(epoch, stamp, size) for epoch, stamp, size in samples})

    growth: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "insufficient_persisted_history",
        "sample_count": len(samples),
        "window_start": None,
        "window_end": None,
        "bytes_delta": None,
        "bytes_per_hour": None,
    }
    if len(samples) >= 2:
        start_epoch, start_stamp, start_size = samples[0]
        end_epoch, end_stamp, end_size = samples[-1]
        elapsed = end_epoch - start_epoch
        if elapsed > 0:
            delta = end_size - start_size
            growth = {
                "status": "AVAILABLE",
                "reason": None,
                "sample_count": len(samples),
                "window_start": start_stamp,
                "window_end": end_stamp,
                "bytes_delta": delta,
                "bytes_per_hour": round(delta * 3600.0 / elapsed, 3),
            }
        else:
            growth["reason"] = "nonpositive_history_window"

    return {
        "status": "AVAILABLE" if size_bytes is not None else "UNAVAILABLE",
        "source": source,
        "sampled_at": sampled_at,
        "size_bytes": size_bytes,
        "size_gib": (
            None if size_bytes is None else round(size_bytes / (1024 ** 3), 3)
        ),
        "wal_size_bytes": wal_size_bytes,
        "wal_source": wal_source,
        "threshold_bytes": threshold_bytes,
        "over_threshold": bool(over_threshold),
        "growth": growth,
    }


def _retention_status(
    runtime_dir: Path,
    *,
    watchdog: dict[str, Any],
    now_epoch: float,
) -> dict[str, Any]:
    records = [
        record
        for record in _bounded_structured_records(
            runtime_dir / "ledger_retention_stdout.log"
        )
        if isinstance(record.get("status"), str) and record["status"].strip()
    ]
    task = next(
        (
            row
            for row in (watchdog.get("tasks") or [])
            if isinstance(row, dict)
            and row.get("task_name") == "DummyLedgerRetention"
        ),
        {},
    )
    latest = records[-1] if records else {}
    last_run_status = str(latest.get("status") or task.get("last_status") or "").upper()
    last_run_status = last_run_status or None

    latest_time = None
    for field in ("generated_at", "completed_at", "at"):
        latest_time = _aware_timestamp(latest.get(field), now_epoch=now_epoch)
        if latest_time is not None:
            break
    if latest_time is None:
        latest_time = _aware_timestamp(task.get("last_status_at"), now_epoch=now_epoch)

    success_time = None
    for record in reversed(records):
        if str(record.get("status") or "").upper() != "APPLIED":
            continue
        for field in ("generated_at", "completed_at", "at"):
            success_time = _aware_timestamp(record.get(field), now_epoch=now_epoch)
            if success_time is not None:
                break
        if success_time is not None:
            break
    if success_time is None:
        success_time = _aware_timestamp(
            task.get("last_success_at"),
            now_epoch=now_epoch,
        )

    next_due = _aware_timestamp(task.get("next_due_at"), now_epoch=now_epoch)
    cadence = _nonnegative_int(task.get("cadence_seconds"))
    if cadence is None:
        cadence = 86_400
    threshold_seconds = _finite_number(task.get("threshold_seconds"))
    if threshold_seconds is None or threshold_seconds <= 0:
        threshold_seconds = float(cadence * 2)
    last_run_age = (
        None if latest_time is None else max(0.0, now_epoch - latest_time[0])
    )
    last_success_age = (
        None if success_time is None else max(0.0, now_epoch - success_time[0])
    )
    last_run_stale = (
        None if last_run_age is None else last_run_age > threshold_seconds
    )
    last_success_stale = (
        None if last_success_age is None else last_success_age > threshold_seconds
    )
    next_due_overdue = next_due is not None and next_due[0] < now_epoch
    task_stale = task.get("stale") if isinstance(task.get("stale"), bool) else None
    task_contract_valid = bool(task) and task_stale is not None
    lock_retries = _nonnegative_int(latest.get("lock_retries"))
    failure_reason = latest.get("error") or task.get("content_error")
    if not isinstance(failure_reason, str) or not failure_reason.strip():
        failure_reason = None
    elif len(failure_reason) > 240:
        failure_reason = failure_reason[:240]

    if (
        last_run_status in {"REFUSED", "FAILED", "ERROR"}
        or last_run_stale is True
        or last_success_stale is True
        or next_due_overdue
        or task_stale is True
    ):
        status = "DEGRADED"
    elif (
        last_run_status == "APPLIED"
        and latest_time is not None
        and success_time is not None
        and next_due is not None
        and task_contract_valid
    ):
        status = "AVAILABLE"
    elif last_run_status is None:
        status = "UNAVAILABLE"
    else:
        status = "PARTIAL"
    return {
        "status": status,
        "source": "ledger_retention_stdout.log+watchdog.tasks",
        "last_run_status": last_run_status,
        "last_run_at": latest_time[1] if latest_time is not None else None,
        "last_run_age_seconds": (
            round(last_run_age, 1) if last_run_age is not None else None
        ),
        "last_run_stale": last_run_stale,
        "last_success_at": success_time[1] if success_time is not None else None,
        "last_success_age_seconds": (
            round(last_success_age, 1) if last_success_age is not None else None
        ),
        "last_success_stale": last_success_stale,
        "next_due_at": next_due[1] if next_due is not None else None,
        "next_due_status": (
            "OVERDUE"
            if next_due_overdue
            else ("AVAILABLE" if next_due is not None else "UNAVAILABLE")
        ),
        "next_due_overdue": next_due_overdue,
        "cadence_seconds": cadence,
        "threshold_seconds": round(threshold_seconds, 1),
        "watchdog_task_stale": task_stale,
        "records_considered": len(records),
        "lock_retries_last_run": lock_retries,
        "failure_reason": failure_reason,
    }


def _sqlite_contention_status(
    *,
    heartbeat: dict[str, Any],
    cycles: list[dict[str, Any]],
) -> dict[str, Any]:
    retry_samples: list[int] = []
    terminal_failures = 0
    for cycle in cycles:
        contention = cycle.get("sqlite_contention")
        if isinstance(contention, dict):
            retry_count = _nonnegative_int(contention.get("retry_events"))
            if retry_count is not None:
                retry_samples.append(retry_count)
        status = str(cycle.get("status") or "")
        error = str(cycle.get("error") or "").casefold()
        if (
            status == "CYCLE_ERROR:OperationalError"
            and ("database is locked" in error or "sqlite_busy" in error)
        ):
            terminal_failures += 1

    health = heartbeat.get("ledger_health")
    checkpoint = health.get("wal_checkpoint") if isinstance(health, dict) else None
    checkpoint_busy = (
        _nonnegative_int(checkpoint.get("busy"))
        if isinstance(checkpoint, dict)
        else None
    )
    retry_events = sum(retry_samples) if retry_samples else None
    status = "AVAILABLE" if retry_events is not None else (
        "PARTIAL" if cycles else "UNAVAILABLE"
    )
    return {
        "status": status,
        "retry_events": retry_events,
        "retry_events_status": (
            "AVAILABLE" if retry_events is not None else "UNAVAILABLE"
        ),
        "terminal_failure_count": terminal_failures,
        "wal_checkpoint_busy": checkpoint_busy,
        "records_considered": len(cycles),
        "reason": (
            None
            if retry_events is not None
            else "per_cycle_retry_counter_not_persisted"
        ),
    }


def _cycle_deadline_status(
    cycles: list[dict[str, Any]],
    *,
    malformed_records: int,
    now_epoch: float,
) -> dict[str, Any]:
    deadline_count = sum(
        1 for cycle in cycles if cycle.get("status") == "CYCLE_ERROR:CycleDeadline"
    )
    first = _cycle_timestamp(cycles[0], now_epoch=now_epoch) if cycles else None
    last = _cycle_timestamp(cycles[-1], now_epoch=now_epoch) if cycles else None
    return {
        "status": "AVAILABLE" if cycles else "UNAVAILABLE",
        "source": "cycles.jsonl",
        "window_kind": "last_valid_records",
        "tail_limit": STATUS_CYCLE_WINDOW,
        "records_considered": len(cycles),
        "malformed_records": malformed_records,
        "deadline_count": deadline_count,
        "rate": round(deadline_count / len(cycles), 6) if cycles else None,
        "window_start": first[1] if first is not None else None,
        "window_end": last[1] if last is not None else None,
    }


def _promotion_run_status(
    payload: Any,
    *,
    now_epoch: float,
) -> dict[str, Any]:
    unavailable = {
        "status": "UNAVAILABLE",
        "source": "auto_promotion_state.json",
        "generated_at": None,
        "age_seconds": None,
        "stale": True,
        "run_status": None,
        "scopes_evaluated": None,
        "eligible_scopes": None,
        "promoted_count": None,
        "declined_count": None,
        "human_review_candidate_count": None,
        "live_trading_authority": None,
        "execution_authority": False,
    }
    if not isinstance(payload, dict) or payload.get("report_name") != "AUTO_PROMOTION":
        return unavailable
    timestamp = _aware_timestamp(payload.get("generated_at"), now_epoch=now_epoch)
    if timestamp is None:
        return {**unavailable, "status": "INVALID"}
    lists = {
        "promoted_count": payload.get("promoted"),
        "declined_count": payload.get("declined"),
        "human_review_candidate_count": payload.get("human_review_candidates"),
    }
    if any(not isinstance(value, list) for value in lists.values()):
        return {
            **unavailable,
            "status": "INVALID",
            "generated_at": timestamp[1],
        }
    age = max(0.0, now_epoch - timestamp[0])
    stale = age > PROMOTION_STATUS_MAX_AGE_SECONDS
    run_status = str(payload.get("status") or "").upper() or None
    status = "STALE" if stale else "AVAILABLE"
    if run_status not in {"OK"}:
        status = "DEGRADED"
    return {
        "status": status,
        "source": "auto_promotion_state.json",
        "generated_at": timestamp[1],
        "age_seconds": round(age, 1),
        "stale": stale,
        "run_status": run_status,
        "scopes_evaluated": _count_or_list_length(
            payload.get("scopes_evaluated")
        ),
        "eligible_scopes": _count_or_list_length(payload.get("eligible_scopes")),
        "promoted_count": len(lists["promoted_count"]),
        "declined_count": len(lists["declined_count"]),
        "human_review_candidate_count": len(
            lists["human_review_candidate_count"]
        ),
        "live_trading_authority": (
            payload.get("live_trading_authority")
            if isinstance(payload.get("live_trading_authority"), str)
            else None
        ),
        "execution_authority": False,
    }


def _watchdog_health_contract(watchdog: Any) -> dict[str, Any]:
    """Sanitize the supervisory verdict without treating absence as health."""

    payload = watchdog if isinstance(watchdog, dict) else {}
    healthy = payload.get("healthy") if isinstance(payload.get("healthy"), bool) else None
    raw_stale_tasks = payload.get("stale_tasks")
    stale_tasks_valid = isinstance(raw_stale_tasks, list) and all(
        isinstance(item, str) and item.strip() for item in raw_stale_tasks
    )
    stale_tasks = (
        [item.strip() for item in raw_stale_tasks[:50]]
        if stale_tasks_valid
        else []
    )
    contract_valid = healthy is not None and stale_tasks_valid
    available = contract_valid and healthy is True and not stale_tasks
    if not contract_valid:
        reason = "watchdog_health_contract_missing_or_invalid"
    elif healthy is not True:
        reason = "watchdog_reported_unhealthy"
    elif stale_tasks:
        reason = "watchdog_authoritative_tasks_stale"
    else:
        reason = None
    return {
        "status": "AVAILABLE" if available else "DEGRADED",
        "healthy": healthy,
        "stale_tasks": stale_tasks,
        "contract_valid": contract_valid,
        "reason": reason,
    }


def _system_health_status(
    runtime_dir: Path,
    *,
    heartbeat: dict[str, Any],
    watchdog: dict[str, Any],
    cycles: list[dict[str, Any]],
    malformed_cycles: int,
    promotion: Any,
    now_epoch: float,
) -> dict[str, Any]:
    ledger = _ledger_health_status(
        runtime_dir,
        heartbeat=heartbeat,
        watchdog=watchdog,
        cycles=cycles,
        now_epoch=now_epoch,
    )
    retention = _retention_status(
        runtime_dir,
        watchdog=watchdog,
        now_epoch=now_epoch,
    )
    sqlite_contention = _sqlite_contention_status(
        heartbeat=heartbeat,
        cycles=cycles,
    )
    cycle_deadlines = _cycle_deadline_status(
        cycles,
        malformed_records=malformed_cycles,
        now_epoch=now_epoch,
    )
    promotion_run = _promotion_run_status(promotion, now_epoch=now_epoch)
    watchdog_health = _watchdog_health_contract(watchdog)
    degraded = (
        watchdog_health["status"] != "AVAILABLE"
        or ledger.get("over_threshold") is True
        or retention["status"] in {"DEGRADED", "STALE"}
        or bool(cycle_deadlines["deadline_count"])
        or promotion_run["status"] == "DEGRADED"
    )
    complete = (
        watchdog_health["status"] == "AVAILABLE"
        and ledger["status"] == "AVAILABLE"
        and ledger["growth"]["status"] == "AVAILABLE"
        and retention["status"] == "AVAILABLE"
        and retention["next_due_status"] == "AVAILABLE"
        and sqlite_contention["status"] == "AVAILABLE"
        and cycle_deadlines["status"] == "AVAILABLE"
        and promotion_run["status"] == "AVAILABLE"
    )
    return {
        "schema_version": 1,
        "status": "DEGRADED" if degraded else ("AVAILABLE" if complete else "PARTIAL"),
        "authority": {"execution": False, "promotion": False},
        "watchdog": watchdog_health,
        "ledger": ledger,
        "retention": retention,
        "sqlite_contention": sqlite_contention,
        "cycle_deadlines": cycle_deadlines,
        "promotion_run": promotion_run,
    }


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
        # Launch-plan truth surfaces: one strategy catalog and one harvested
        # adapter lifecycle registry. Both are read-only and grant no authority.
        "strategy_catalog": _strategy_catalog_status(),
        "repo_harvester": _repo_harvester_status(),
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


def _strategy_catalog_status() -> dict[str, Any]:
    try:
        from strategies.registry import strategy_catalog_payload

        return strategy_catalog_payload()
    except Exception as exc:  # noqa: BLE001 -- dashboard must fail closed
        return {
            "catalog_status": "UNAVAILABLE_FAIL_CLOSED",
            "execution_authority_count": 0,
            "strategies": [],
            "error": f"{type(exc).__name__}: {exc}"[:200],
        }


def _repo_harvester_status() -> dict[str, Any]:
    try:
        from repo_harvester.incorporation_registry import dashboard_registry_payload

        return dashboard_registry_payload()
    except Exception as exc:  # noqa: BLE001 -- dashboard must fail closed
        return {
            "registry_status": "UNAVAILABLE_FAIL_CLOSED",
            "verified_challenger_count": 0,
            "dormant_adapter_count": 0,
            "all_unverified_adapters_dormant": False,
            "authority": {"prediction": False, "execution": False},
            "adapters": [],
            "error": f"{type(exc).__name__}: {exc}"[:200],
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
    predictions, predictions_error = _bounded_json_object(
        rd / "use_predictions.json",
        max_bytes=STATUS_TAIL_MAX_BYTES,
    )
    predictions = predictions or {}
    provenance: dict[str, int] = {}
    rows = predictions.get("rows")
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and "error" not in row:
            key = str(row.get("provenance"))
            provenance[key] = provenance.get(key, 0) + 1
    outcomes_payload, outcomes_error = _bounded_file_bytes(
        rd / "use_outcomes.jsonl",
        max_bytes=STATUS_TAIL_MAX_BYTES,
    )
    outcomes = None
    if outcomes_payload is not None:
        try:
            outcomes = len(outcomes_payload.decode("utf-8").splitlines())
        except UnicodeError:
            outcomes_error = "invalid_utf8"
    return {
        "status": (
            predictions.get("status")
            if predictions_error is None
            else "UNAVAILABLE"
        ),
        "generated_at": predictions.get("generated_at"),
        "predictions": sum(provenance.values()),
        "provenance": provenance,
        "outcomes_on_tape": outcomes,
        "outcomes_status": "AVAILABLE" if outcomes is not None else "UNAVAILABLE",
        "outcomes_unavailable_reason": outcomes_error,
        "bounded_read_limit_bytes": STATUS_TAIL_MAX_BYTES,
    }


def _flatten_board_rows(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for markets in (board.get("groups") or {}).values()
        if isinstance(markets, dict)
        for rows in markets.values()
        if isinstance(rows, list)
        for row in rows
        if isinstance(row, dict)
    ]


def _quantile(sorted_values: list[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return (
        sorted_values[lower] * (1.0 - weight)
        + sorted_values[upper] * weight
    )


def _board_artifact_size_error(runtime_dir: Path) -> str | None:
    for name in ("bet_board.json", "bet_board_display.json"):
        path = runtime_dir / name
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            continue
        except OSError:
            return f"artifact_stat_unavailable:{name}"
        if size > STATUS_BOARD_MAX_BYTES:
            return f"artifact_size_limit_exceeded:{name}"
    return None


def _board_edge_quality(
    runtime_dir: Path,
    *,
    now_epoch: float,
) -> dict[str, Any]:
    from autonomy.bet_board import read_current_board_artifact

    current = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    size_error = _board_artifact_size_error(runtime_dir)
    if size_error is None:
        board = read_current_board_artifact(
            runtime_dir / "bet_board.json",
            display_path=runtime_dir / "bet_board_display.json",
            now=current,
        )
    else:
        board = {
            "artifact_status": "INVALID",
            "generated_at": None,
            "stale": True,
            "groups": {},
        }
    rows = _flatten_board_rows(board)
    artifact_status = str(board.get("artifact_status") or "UNAVAILABLE").upper()
    is_fresh = artifact_status == "FRESH" and board.get("stale") is False
    valid_labels = {"A", "B", "C", "WATCH"}
    validated = (
        [
            row
            for row in rows
            if str(row.get("tier_display_bucket") or "") in valid_labels
        ]
        if is_fresh
        else []
    )
    edges = sorted(
        edge
        for row in validated
        if (edge := _finite_number(row.get("after_fee_edge"))) is not None
    )
    bins = [
        {"label": "<0%", "count": sum(value < 0.0 for value in edges)},
        {
            "label": "0% to <1%",
            "count": sum(0.0 <= value < 0.01 for value in edges),
        },
        {
            "label": "1% to <2%",
            "count": sum(0.01 <= value < 0.02 for value in edges),
        },
        {
            "label": "2% to <4%",
            "count": sum(0.02 <= value < 0.04 for value in edges),
        },
        {"label": ">=4%", "count": sum(value >= 0.04 for value in edges)},
    ]
    if not is_fresh:
        edge_reason = "board_not_fresh"
    elif not validated:
        edge_reason = "no_schema_valid_current_rows"
    elif not edges:
        edge_reason = "validated_rows_missing_after_fee_edge"
    else:
        edge_reason = None
    after_fee = {
        "status": "AVAILABLE" if edges else "UNAVAILABLE",
        "reason": edge_reason,
        "sample_count": len(edges),
        "missing_count": len(validated) - len(edges),
        "bins": bins,
        "min": round(edges[0], 6) if edges else None,
        "p50": (
            round(value, 6)
            if (value := _quantile(edges, 0.5)) is not None
            else None
        ),
        "p90": (
            round(value, 6)
            if (value := _quantile(edges, 0.9)) is not None
            else None
        ),
        "max": round(edges[-1], 6) if edges else None,
        "mean": round(sum(edges) / len(edges), 6) if edges else None,
    }

    reason_counts: dict[tuple[str, str], int] = {}
    for row in rows if is_fresh else []:
        tier = str(row.get("tier_display_bucket") or "UNATTRIBUTED")
        if tier not in {"WATCH", "UNATTRIBUTED"}:
            continue
        reason = str(row.get("tier_display_reason") or "").strip()
        if not reason:
            continue
        key = tier, reason
        reason_counts[key] = reason_counts.get(key, 0) + 1
    gate_reason_counts = [
        {"tier": tier, "reason": reason, "count": count}
        for (tier, reason), count in sorted(
            reason_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:20]
    ]

    if artifact_status in {"MISSING", "INVALID", "UNREADABLE", "UNAVAILABLE"}:
        status = "UNAVAILABLE"
    elif not is_fresh:
        status = "STALE"
    elif validated:
        status = "AVAILABLE"
    else:
        status = "PARTIAL"
    return {
        "status": status,
        "source": "bet_board.json+bet_board_display.json",
        "reason": size_error,
        "artifact_status": artifact_status,
        "generated_at": board.get("generated_at"),
        "stale": board.get("stale") is not False,
        "total_rows": len(rows),
        "validated_rows": len(validated),
        "excluded_rows": len(rows) - len(validated),
        "after_fee_edge": after_fee,
        "actionable_share": {
            "status": "UNAVAILABLE",
            "reason": "dedicated_actionable_population_receipt_missing",
            "numerator": None,
            "denominator": None,
            "value": None,
            "definition": (
                "trailing main-lane decisions meeting the declared "
                "submission-actionable gate"
            ),
            "execution_authority": False,
        },
        "gate_reason_counts": gate_reason_counts,
    }


def _execution_cohort(
    report: dict[str, Any],
    *,
    cohort_name: str,
    expected_mode: str,
) -> dict[str, Any] | None:
    matches = [
        cohort
        for cohort in (report.get("cohorts") or [])
        if isinstance(cohort, dict)
        and isinstance(cohort.get("policy"), dict)
        and cohort["policy"].get("cohort") == cohort_name
    ]
    if len(matches) != 1:
        return None
    cohort = matches[0]
    policy = cohort["policy"]
    if policy.get("mode") != expected_mode:
        return None
    fills = _nonnegative_int(cohort.get("fills"))
    clusters = _nonnegative_int(cohort.get("fill_event_clusters"))
    fill_rate = _finite_number(cohort.get("fill_rate"))
    if fills is None or clusters is None or fill_rate is None or not 0 <= fill_rate <= 1:
        return None
    evidence_class = cohort.get("evidence_class")
    output_authority = cohort.get("output_authority")
    if not isinstance(evidence_class, str) or not isinstance(output_authority, str):
        return None
    authority_flags = {
        "witnessed_broker_fill_backing": cohort.get(
            "witnessed_broker_fill_backing"
        ),
        "counts_toward_policy_switch": cohort.get(
            "counts_toward_policy_switch"
        ),
        "counts_toward_promotion_readiness": cohort.get(
            "counts_toward_promotion_readiness"
        ),
        "promotion_review_eligible": cohort.get("promotion_review_eligible"),
    }
    if any(not isinstance(value, bool) for value in authority_flags.values()):
        return None
    return {
        "cohort": cohort_name,
        "mode": expected_mode,
        "label": (
            policy.get("label") if isinstance(policy.get("label"), str) else None
        ),
        "evidence_basis": (
            cohort.get("evidence_basis")
            if isinstance(cohort.get("evidence_basis"), str)
            else None
        ),
        "fills": fills,
        "fill_event_clusters": clusters,
        "fill_rate": fill_rate,
        "brier_edge_vs_market": _finite_number(
            cohort.get("fill_conditioned_brier_edge_vs_market")
        ),
        "net_pnl_cents": _finite_number(cohort.get("net_pnl_cents")),
        "mean_pnl_cents": _finite_number(cohort.get("mean_pnl_cents")),
        "gate_status": (
            cohort.get("gate_status")
            if isinstance(cohort.get("gate_status"), str)
            else None
        ),
        "evidence_class": evidence_class,
        "output_authority": output_authority,
        **authority_flags,
    }


def _execution_comparison_status(
    report: Any,
    *,
    now_epoch: float,
) -> dict[str, Any]:
    unavailable = {
        "status": "UNAVAILABLE",
        "source": "execution_tournament.json",
        "generated_at": None,
        "age_seconds": None,
        "stale": True,
        "audit_only": True,
        "policy_switch_authority": False,
        "maker": None,
        "taker": None,
    }
    if (
        not isinstance(report, dict)
        or report.get("report_name") != "EXECUTION_POLICY_TOURNAMENT"
    ):
        return unavailable
    timestamp = _aware_timestamp(report.get("generated_at"), now_epoch=now_epoch)
    if timestamp is None:
        return {**unavailable, "status": "INVALID"}
    switch = report.get("policy_switch_authority")
    if not isinstance(switch, dict) or switch.get("auto_switch") is not False:
        return {
            **unavailable,
            "status": "INVALID",
            "generated_at": timestamp[1],
        }
    maker = _execution_cohort(report, cohort_name="C0", expected_mode="maker")
    taker = _execution_cohort(report, cohort_name="C1", expected_mode="taker")
    if maker is None or taker is None:
        return {
            **unavailable,
            "status": "INVALID",
            "generated_at": timestamp[1],
        }
    if (
        maker.get("evidence_class") != "observed_incumbent_fill_replay"
        or taker.get("evidence_class") != "modeled_counterfactual"
        or taker.get("witnessed_broker_fill_backing") is not False
        or taker.get("counts_toward_policy_switch") is not False
        or taker.get("counts_toward_promotion_readiness") is not False
        or taker.get("promotion_review_eligible") is not False
    ):
        return {
            **unavailable,
            "status": "INVALID",
            "generated_at": timestamp[1],
        }
    age = max(0.0, now_epoch - timestamp[0])
    return {
        "status": "AUDIT_ONLY",
        "source": "execution_tournament.json",
        "generated_at": timestamp[1],
        "age_seconds": round(age, 1),
        "stale": age > EXECUTION_TOURNAMENT_MAX_AGE_SECONDS,
        "audit_only": True,
        "policy_switch_authority": False,
        "maker": maker,
        "taker": taker,
    }


def _caps_evidence_status() -> dict[str, Any]:
    """Verify the protected caps contract before exposing allowlist evidence."""

    from core import caps_authority

    try:
        caps_size = CAPS_CONFIG_PATH.stat().st_size
        size_error = (
            "CAPS_CONFIG_SIZE_LIMIT_EXCEEDED"
            if caps_size > STATUS_CAPS_MAX_BYTES
            else None
        )
    except FileNotFoundError:
        caps_size = None
        size_error = "CAPS_CONFIG_MISSING"
    except OSError:
        caps_size = None
        size_error = "CAPS_CONFIG_UNREADABLE"

    authority = None
    if size_error is None:
        try:
            authority = caps_authority.evaluate_caps_authority(
                caps_path=CAPS_CONFIG_PATH
            )
        except Exception as exc:
            size_error = f"CAPS_AUTHORITY_EVALUATION_FAILED:{type(exc).__name__}"

    config_verified = bool(
        authority is not None and authority.config_integrity_valid
    )
    caps = None
    caps_error = None
    if config_verified:
        caps, caps_error = _bounded_json_object(
            CAPS_CONFIG_PATH,
            max_bytes=STATUS_CAPS_MAX_BYTES,
        )
    allowed_series = caps.get("allowed_series") if isinstance(caps, dict) else None
    valid_series = (
        isinstance(allowed_series, list)
        and all(isinstance(item, str) and item for item in allowed_series)
    )
    exact_series_allowed = bool(
        config_verified
        and caps_error is None
        and valid_series
        and KXSOL15M_SERIES in allowed_series
    )
    errors = list(authority.errors) if authority is not None else []
    if size_error is not None:
        errors.append(size_error)
    if caps_error is not None:
        errors.append(f"CAPS_CONFIG_{caps_error.upper()}")
    return {
        "status": (
            "AVAILABLE"
            if config_verified and caps_error is None and valid_series
            else "INVALID"
        ),
        "source": str(CAPS_CONFIG_PATH).replace("\\", "/"),
        "size_bytes": caps_size,
        "authority_state": authority.state if authority is not None else None,
        "config_integrity_valid": config_verified,
        "authority_registration_valid": (
            authority.authority_registration_valid
            if authority is not None
            else False
        ),
        "current_caps_sha256": (
            authority.current_caps_sha256 if authority is not None else None
        ),
        "protected_caps_sha256": caps_authority.PROTECTED_CAPS_SHA256,
        "errors": errors,
        "exact_series_allowed": exact_series_allowed,
        "matched_series": KXSOL15M_SERIES if exact_series_allowed else None,
        "execution_authority": False,
    }


def _kxsol15m_status(
    runtime_dir: Path,
    *,
    live_controls: dict[str, Any],
    session: dict[str, Any],
    now_epoch: float,
) -> dict[str, Any]:
    from autonomy.no_edge_map import load_negative_scopes
    from autonomy.taxonomy import grading_scope

    scope = grading_scope(
        KXSOL15M_SOURCE,
        KXSOL15M_SERIES,
        {"vertical": "CRYPTO", "market_type": "15m_direction"},
    )
    map_path = runtime_dir / "no_edge_map.json"
    now = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    evidence = load_negative_scopes(map_path, now=now)
    payload = _load_json(map_path)
    classification = None
    selected: dict[str, Any] | None = None
    if evidence.trusted and isinstance(payload, dict):
        matches: list[tuple[str, dict[str, Any]]] = []
        for category in (
            "edge",
            "no_demonstrated_edge",
            "significantly_negative",
        ):
            for row in payload.get(category) or []:
                if isinstance(row, dict) and row.get("scope") == scope:
                    matches.append((category, row))
        if scope in (payload.get("insufficient_evidence_scopes") or []):
            matches.append(("insufficient_evidence", {"scope": scope}))
        if len(matches) == 1:
            classification, selected = matches[0]

    clusters = (
        _nonnegative_int(selected.get("clusters"))
        if isinstance(selected, dict)
        else None
    )
    edge_mean = (
        _finite_number(selected.get("edge_mean"))
        if isinstance(selected, dict)
        else None
    )
    ci_lower = (
        _finite_number(selected.get("ci_lower"))
        if isinstance(selected, dict)
        else None
    )
    ci_upper = (
        _finite_number(selected.get("ci_upper"))
        if isinstance(selected, dict)
        else None
    )
    selected_complete = classification == "insufficient_evidence" or (
        classification is not None
        and clusters is not None
        and edge_mean is not None
        and ci_lower is not None
        and ci_upper is not None
    )
    statistical_status = (
        "AVAILABLE" if evidence.trusted and selected_complete else "UNAVAILABLE"
    )
    generated_at = (
        evidence.generated_at.isoformat()
        if evidence.generated_at is not None
        else None
    )
    statistical = {
        "status": statistical_status,
        "source": "no_edge_map.json",
        "generated_at": generated_at,
        "stale": evidence.status == "stale",
        "trust_status": evidence.status,
        "classification": classification,
        "clusters": clusters,
        "edge_mean": edge_mean,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "execution_authority": False,
    }

    caps_evidence = _caps_evidence_status()
    exact_series_allowed = caps_evidence["exact_series_allowed"] is True
    source_state = (
        live_controls.get("state")
        if isinstance(live_controls.get("state"), str)
        else "invalid_or_blocked"
    )
    blocker = (
        live_controls.get("blocker")
        if isinstance(live_controls.get("blocker"), str)
        else None
    )
    live_authority = {
        "state": source_state,
        # This observer contract can never grant submission authority.
        "execution_authority": False,
        "blocker": blocker,
        "session_status": session.get("status"),
        "session_expired": (
            session.get("expired")
            if isinstance(session.get("expired"), bool)
            else None
        ),
    }
    if statistical_status != "AVAILABLE":
        conclusion = "STATISTICAL_SCOPE_EVIDENCE_UNAVAILABLE"
    elif not exact_series_allowed:
        conclusion = "STATISTICAL_EVIDENCE_PRESENT_SERIES_CAP_ABSENT"
    else:
        conclusion = (
            "STATISTICAL_EVIDENCE_PRESENT_SERIES_CAP_PRESENT_"
            "LIVE_AUTHORITY_FALSE"
        )
    return {
        "status": (
            "EVIDENCE_ONLY"
            if statistical_status == "AVAILABLE"
            and caps_evidence["status"] == "AVAILABLE"
            else "PARTIAL"
        ),
        "series": KXSOL15M_SERIES,
        "scope_mapping": {
            "status": "EXACT_TAXONOMY",
            "scope": scope,
            "source": "autonomy.taxonomy.grading_scope",
        },
        "statistical_evidence": statistical,
        "caps_evidence": caps_evidence,
        "live_authority": live_authority,
        "conclusion": conclusion,
        "execution_authority": False,
    }


def _edge_quality_status(
    runtime_dir: Path,
    *,
    tournament: Any,
    live_controls: dict[str, Any],
    session: dict[str, Any],
    now_epoch: float,
) -> dict[str, Any]:
    current_board = _board_edge_quality(runtime_dir, now_epoch=now_epoch)
    comparison = _execution_comparison_status(tournament, now_epoch=now_epoch)
    kxsol = _kxsol15m_status(
        runtime_dir,
        live_controls=live_controls,
        session=session,
        now_epoch=now_epoch,
    )
    available = (
        current_board["status"] in {"AVAILABLE", "PARTIAL", "STALE"}
        or comparison["status"] == "AUDIT_ONLY"
        or kxsol["status"] == "EVIDENCE_ONLY"
    )
    return {
        "schema_version": 1,
        # Actionable-share producer truth is deliberately still unavailable.
        "status": "PARTIAL" if available else "UNAVAILABLE",
        "authority": {"execution": False, "promotion": False},
        "current_board": current_board,
        "execution_comparison": comparison,
        "kxsol15m": kxsol,
    }


def assemble_status_snapshot(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Fast, precomputed operator snapshot -- reads runtime artifacts only.

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
    promotion = _load_json(rd / "auto_promotion_state.json") or {}
    data_ages: dict[str, Any] = {}
    for name, payload in panels_raw.items():
        data_ages[name] = _panel_data_age(name, payload, now_epoch)

    watchdog_status = _dashboard_watchdog_status(rd, now_epoch)
    cycles, malformed_cycles = _bounded_cycle_window(rd / "cycles.jsonl")
    session = session_authorization_state(rd)
    live_controls = _live_controls_status()
    system_health = _system_health_status(
        rd,
        heartbeat=heartbeat,
        watchdog=watchdog_status,
        cycles=cycles,
        malformed_cycles=malformed_cycles,
        promotion=promotion,
        now_epoch=now_epoch,
    )
    edge_quality = _edge_quality_status(
        rd,
        tournament=panels_raw["execution_tournament"],
        live_controls=live_controls,
        session=session,
        now_epoch=now_epoch,
    )
    return {
        "generated_at": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
        "source": "status_snapshot",
        "ledger_touched": False,
        "heartbeat": heartbeat,
        "session": session,
        "live_controls": live_controls,
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
        "system_health": system_health,
        "edge_quality": edge_quality,
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
        "recent_cycles": cycles[-10:],
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

        summary = summarize_tournament(report)
        ranking = summary.get("ranking")
        headline = summary.get("headline")
        switch = summary.get("policy_switch_authority")
        expected_research_classes = {
            "C1": "modeled_counterfactual",
            "C2": "modeled_counterfactual",
            "C3": "observed_fill_censoring_counterfactual",
            "C4": "modeled_counterfactual",
        }
        valid_research_authority = (
            isinstance(ranking, list)
            and isinstance(headline, dict)
            and isinstance(switch, dict)
            and switch.get("auto_switch") is False
            and headline.get("evidence_sufficient_for_promotion_review") is False
            and headline.get("evidence_sufficient_for_policy_switch") is False
        )
        by_cohort = {
            row.get("cohort"): row
            for row in ranking or []
            if isinstance(row, dict)
        }
        for cohort_name, evidence_class in expected_research_classes.items():
            row = by_cohort.get(cohort_name)
            if row is None:
                continue
            valid_research_authority = valid_research_authority and (
                row.get("evidence_class") == evidence_class
                and row.get("witnessed_broker_fill_backing") is False
                and row.get("counts_toward_policy_switch") is False
                and row.get("counts_toward_promotion_readiness") is False
                and row.get("promotion_review_eligible") is False
            )
        if valid_research_authority:
            return summary
    except Exception:
        pass
    return {
        "report_name": report.get("report_name"),
        "status": "INVALID",
        "audit_only": True,
        "ranking": [],
        "headline": {
            "leading_cohort": None,
            "evidence_sufficient_for_promotion_review": False,
            "evidence_sufficient_for_policy_switch": False,
        },
        "policy_switch_authority": {
            "auto_switch": False,
            "reason": "invalid_or_unlabeled_tournament_evidence",
        },
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
    """Construct the canonical loopback-only, query-only evidence dashboard."""
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

    import os
    import threading
    from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout

    app = FastAPI(title="Dummy Autonomy Dashboard")

    @app.middleware("http")
    async def _loopback_only(request: Request, call_next):
        """Fail closed if either the socket peer or Host header is non-local."""
        peer = request.client.host if request.client is not None else None
        peer_ok = _is_loopback_address(peer, allow_test_name=True)
        host = request.url.hostname
        host_ok = _is_loopback_address(host)
        if peer == _TEST_CLIENT_NAME and str(host or "").casefold() == _TEST_HOST_NAME:
            host_ok = True
        if not peer_ok or not host_ok:
            response = JSONResponse(
                {"detail": "Dummy dashboard is available on loopback only."},
                status_code=403,
            )
        else:
            response = await call_next(request)
        for name, value in _DASHBOARD_SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

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

    @app.get("/api/repo-harvester")
    def api_repo_harvester() -> JSONResponse:
        """Dashboard-visible lifecycle registry; artifact-only, no network."""

        return JSONResponse(_repo_harvester_status())

    @app.get("/api/strategy-catalog")
    def api_strategy_catalog() -> JSONResponse:
        """Single research-strategy catalog with explicit authority state."""

        return JSONResponse(_strategy_catalog_status())

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
        from autonomy.model_arsenal_status import build_model_arsenal_status

        return JSONResponse(build_model_arsenal_status())

    @app.get("/api/market-observer/chart/{asset}/{timeframe}")
    def api_market_observer_chart(asset: str, timeframe: str) -> JSONResponse:
        """Serve a validated immutable chart artifact without refreshing it."""
        from autonomy.dashboard_market_observer import (
            ChartArtifactError,
            read_market_chart,
        )
        from autonomy.market_observer.contracts import (
            ALLOWED_ASSETS,
            ALLOWED_TIMEFRAMES,
        )

        normalized_asset = str(asset).upper()
        normalized_timeframe = str(timeframe)
        if (
            normalized_asset not in ALLOWED_ASSETS
            or normalized_timeframe not in ALLOWED_TIMEFRAMES
        ):
            return JSONResponse(
                {
                    "available": False,
                    "artifact_status": "UNAVAILABLE",
                    "detail": "Unsupported market-observer chart identity.",
                    "allowed_assets": sorted(ALLOWED_ASSETS),
                    "allowed_timeframes": sorted(ALLOWED_TIMEFRAMES),
                    "authority": {
                        "allocation": False,
                        "amend": False,
                        "cancel": False,
                        "execution": False,
                        "order": False,
                        "promotion": False,
                    },
                },
                status_code=404,
            )
        root = Path(
            os.environ.get(
                "DUMMY_MARKET_OBSERVER_ROOT",
                "artifacts/dummy/market_observer",
            )
        )
        try:
            payload = read_market_chart(
                root,
                normalized_asset,
                normalized_timeframe,
            )
            return JSONResponse(
                payload,
                status_code=200 if payload.get("available") is True else 503,
            )
        except ChartArtifactError as exc:
            return JSONResponse(
                {
                    "available": False,
                    "artifact_status": "SCHEMA_DRIFT",
                    "asset": normalized_asset,
                    "timeframe": normalized_timeframe,
                    "detail": "Stored chart artifact failed validation.",
                    "error_type": type(exc).__name__,
                    "authority": {
                        "allocation": False,
                        "amend": False,
                        "cancel": False,
                        "execution": False,
                        "order": False,
                        "promotion": False,
                    },
                },
                status_code=503,
            )
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            return JSONResponse(
                {
                    "available": False,
                    "artifact_status": "UNAVAILABLE",
                    "asset": normalized_asset,
                    "timeframe": normalized_timeframe,
                    "detail": "Stored chart artifact is unavailable.",
                    "error_type": type(exc).__name__,
                    "authority": {
                        "allocation": False,
                        "amend": False,
                        "cancel": False,
                        "execution": False,
                        "order": False,
                        "promotion": False,
                    },
                },
                status_code=503,
            )

    @app.get(
        "/assets/vendor/lightweight-charts/5.2.0/"
        "lightweight-charts.standalone.production.js",
        include_in_schema=False,
    )
    def lightweight_charts_asset() -> FileResponse:
        """Serve the pinned local renderer; it contains no market data client."""
        from autonomy.dashboard_market_observer import LIGHTWEIGHT_CHARTS_ASSET

        return FileResponse(
            LIGHTWEIGHT_CHARTS_ASSET,
            media_type="application/javascript",
        )

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

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(_current_html())

    return app
