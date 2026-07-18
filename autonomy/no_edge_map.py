"""NO_EDGE_MAP: where Dummy has no demonstrated advantage (Wave-7).

Ascendancy delta #4. "Where we bleed" was a one-liner; this is the full map.
Knowing where there is NO edge is as operationally valuable as knowing where
there is one — it stops re-litigating dead ideas, steers research compute,
and keeps the operator's mental model honest.

Classification per grading scope (from the latest backtest report):

  * ``edge``                    — contested CI95 lower bound > 0 at >= MIN_CLUSTERS.
  * ``no_demonstrated_edge``    — enough clusters, CI spans 0 within +/- EPS.
  * ``significantly_negative``  — enough clusters, CI95 upper bound < 0
    (actively losing when contested; retirement-review material).
  * ``insufficient_evidence``   — below the cluster bar; no claim either way.

Evidence-only; nothing here gates or trades.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAP_PATH = Path("runtime/autonomy/no_edge_map.json")
MIN_CLUSTERS = 40
NO_EDGE_EPS = 0.005


def classify_scope(stats: dict[str, Any]) -> str:
    clusters = int(stats.get("contested_event_clusters") or 0)
    ci = stats.get("contested_mean_brier_edge_ci95") or {}
    lower = ci.get("lower")
    upper = ci.get("upper")
    if clusters < MIN_CLUSTERS or lower is None or upper is None:
        return "insufficient_evidence"
    if float(lower) > 0:
        return "edge"
    if float(upper) < 0:
        return "significantly_negative"
    return "no_demonstrated_edge"


def build_no_edge_map(backtest_report: dict[str, Any]) -> dict[str, Any]:
    scopes = backtest_report.get("sources_by_scope") or {}
    classified: dict[str, list[dict[str, Any]]] = {
        "edge": [], "no_demonstrated_edge": [],
        "significantly_negative": [], "insufficient_evidence": [],
    }
    for scope, stats in sorted(scopes.items()):
        ci = stats.get("contested_mean_brier_edge_ci95") or {}
        classified[classify_scope(stats)].append({
            "scope": scope,
            "clusters": int(stats.get("contested_event_clusters") or 0),
            "edge_mean": ci.get("mean"),
            "ci_lower": ci.get("lower"),
            "ci_upper": ci.get("upper"),
        })
    return {
        "report_name": "NO_EDGE_MAP",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_clusters": MIN_CLUSTERS,
        "counts": {k: len(v) for k, v in classified.items()},
        "edge": classified["edge"],
        "significantly_negative": classified["significantly_negative"],
        "no_demonstrated_edge": classified["no_demonstrated_edge"],
        "insufficient_evidence_scopes": [
            e["scope"] for e in classified["insufficient_evidence"]
        ],
    }


def write_no_edge_map(no_edge_map: dict[str, Any], path: Path | None = None) -> Path:
    path = path or MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(no_edge_map, indent=2, sort_keys=True), encoding="utf-8")
    return path


# A map older than this no longer reflects the current evidence; a stale
# artifact must not keep suppressing (or un-suppressing) fusion members.
NEGATIVE_SCOPE_MAX_AGE_DAYS = 7.0


def load_negative_scopes(path: Path | None = None) -> frozenset[str]:
    """Scopes the evidence grades SIGNIFICANTLY NEGATIVE (CI95 upper < 0),
    for the Wave-19 fusion floor. Fail-open: missing/malformed/stale artifact
    -> empty set (no suppression on guesswork)."""
    try:
        payload = json.loads((path or MAP_PATH).read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(str(payload.get("generated_at")))
        age_days = (
            datetime.now(timezone.utc) - generated
        ).total_seconds() / 86400.0
        if age_days > NEGATIVE_SCOPE_MAX_AGE_DAYS:
            return frozenset()
        return frozenset(
            str(entry.get("scope"))
            for entry in payload.get("significantly_negative") or []
            if isinstance(entry, dict) and entry.get("scope")
        )
    except (OSError, ValueError, TypeError):
        return frozenset()
