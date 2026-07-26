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

The map never grants trading authority.  A fresh, schema-valid map can only
remove significantly negative scopes from fusion.  If the artifact cannot be
trusted, the forecaster hard-abstains independent predictive fusion instead of
silently treating the exclusion set as empty.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dummy.truth import holm_bonferroni

MAP_PATH = Path("runtime/autonomy/no_edge_map.json")
MIN_CLUSTERS = 40
NO_EDGE_EPS = 0.005
EDGE_FAMILYWISE_ALPHA = 0.05


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
    eligible_scope_ids: list[str] = []
    positive_tests: list[tuple[str, float]] = []
    for scope, stats in sorted(scopes.items()):
        clusters = int(stats.get("contested_event_clusters") or 0)
        ci = stats.get("contested_mean_brier_edge_ci95") or {}
        if clusters < MIN_CLUSTERS or ci.get("lower") is None or ci.get("upper") is None:
            continue
        eligible_scope_ids.append(scope)
        sign_test = (
            (stats.get("contested_edge_sign_test") or {}).get("positive_edge")
            or {}
        )
        p_value = sign_test.get("p_value")
        if (
            not isinstance(p_value, bool)
            and isinstance(p_value, (int, float))
            and math.isfinite(float(p_value))
            and 0.0 <= float(p_value) <= 1.0
        ):
            positive_tests.append((scope, float(p_value)))
    family_complete = len(positive_tests) == len(eligible_scope_ids)
    corrections = {
        item.hypothesis_id: item
        for item in holm_bonferroni(
            tuple(positive_tests), alpha=EDGE_FAMILYWISE_ALPHA
        )
    } if positive_tests else {}
    unconfirmed_positive: list[dict[str, Any]] = []
    for scope, stats in sorted(scopes.items()):
        ci = stats.get("contested_mean_brier_edge_ci95") or {}
        pointwise = classify_scope(stats)
        correction = corrections.get(scope)
        row = {
            "scope": scope,
            "clusters": int(stats.get("contested_event_clusters") or 0),
            "edge_mean": ci.get("mean"),
            "ci_lower": ci.get("lower"),
            "ci_upper": ci.get("upper"),
        }
        if correction is not None:
            row.update({
                "raw_one_sided_p_value": correction.raw_p_value,
                "adjusted_p_value": correction.adjusted_p_value,
                "familywise_confirmed": bool(correction.rejected_null),
            })
        if pointwise == "edge" and (
            not family_complete
            or correction is None
            or not correction.rejected_null
        ):
            # A pointwise-positive CI selected from hundreds of scopes is not a
            # demonstrated edge. Keep it out of the headline and collect more
            # independent evidence instead.
            classified["insufficient_evidence"].append(row)
            unconfirmed_positive.append(row)
            continue
        classified[pointwise].append(row)
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
        "multiple_testing": {
            "method": "HOLM_BONFERRONI",
            "primary_endpoint": "positive_contested_brier_edge",
            "alpha": EDGE_FAMILYWISE_ALPHA,
            "eligible_family_size": len(eligible_scope_ids),
            "tested_family_size": len(positive_tests),
            "complete_family": family_complete,
            "confirmed_positive_scopes": len(classified["edge"]),
            "unconfirmed_pointwise_positive_scopes": unconfirmed_positive,
            "policy": (
                "pointwise-positive scopes enter the edge headline only after "
                "family-wise rejection; incomplete families fail closed"
            ),
        },
    }


def write_no_edge_map(no_edge_map: dict[str, Any], path: Path | None = None) -> Path:
    path = path or MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(no_edge_map, indent=2, sort_keys=True), encoding="utf-8")
    return path


# A map older than this no longer reflects the current evidence; a stale
# artifact must not silently un-suppress fusion members.
NEGATIVE_SCOPE_MAX_AGE_DAYS = 7.0
NEGATIVE_SCOPE_FUTURE_TOLERANCE_SECONDS = 300.0


class NegativeScopeEvidence(frozenset[str]):
    """Set-compatible exclusion evidence with an explicit trust disposition.

    Keeping this a ``frozenset`` subtype preserves callers that compare or
    iterate ``load_negative_scopes()`` results.  The additional attributes let
    the forecaster distinguish a trusted empty map ("no scopes are currently
    negative") from an unavailable map ("we do not know which scopes remain
    negative").
    """

    trusted: bool
    status: str
    generated_at: datetime | None
    source_path: Path

    def __new__(
        cls,
        scopes: Iterable[str] = (),
        *,
        trusted: bool,
        status: str,
        generated_at: datetime | None,
        source_path: Path,
    ) -> NegativeScopeEvidence:
        instance = super().__new__(cls, scopes)
        instance.trusted = bool(trusted)
        instance.status = str(status)
        instance.generated_at = generated_at
        instance.source_path = Path(source_path)
        return instance


def _untrusted_negative_scopes(
    status: str,
    source_path: Path,
    *,
    generated_at: datetime | None = None,
) -> NegativeScopeEvidence:
    return NegativeScopeEvidence(
        trusted=False,
        status=status,
        generated_at=generated_at,
        source_path=source_path,
    )


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def load_negative_scopes(
    path: Path | None = None,
    *,
    now: datetime | None = None,
) -> NegativeScopeEvidence:
    """Scopes the evidence grades SIGNIFICANTLY NEGATIVE (CI95 upper < 0),
    for the Wave-19 fusion floor.

    The return value remains set-compatible, but ``trusted`` is false for a
    missing, unreadable, malformed, future-dated, or stale artifact.  Callers
    that can influence execution must honor that disposition rather than
    interpreting an untrusted empty set as permission to fuse every scope.
    """
    source_path = MAP_PATH if path is None else Path(path)
    try:
        raw_payload = source_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _untrusted_negative_scopes("missing", source_path)
    except OSError:
        return _untrusted_negative_scopes("unreadable", source_path)

    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        return _untrusted_negative_scopes("malformed_json", source_path)
    if not isinstance(payload, dict):
        return _untrusted_negative_scopes("malformed_schema", source_path)

    try:
        generated = datetime.fromisoformat(str(payload.get("generated_at")))
    except (ValueError, TypeError):
        return _untrusted_negative_scopes("malformed_timestamp", source_path)
    if generated.tzinfo is None or generated.utcoffset() is None:
        return _untrusted_negative_scopes("malformed_timestamp", source_path)
    generated = generated.astimezone(timezone.utc)

    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    age_seconds = (
        observed_now.astimezone(timezone.utc) - generated
    ).total_seconds()
    if age_seconds < -NEGATIVE_SCOPE_FUTURE_TOLERANCE_SECONDS:
        return _untrusted_negative_scopes(
            "future_dated", source_path, generated_at=generated
        )
    if age_seconds > NEGATIVE_SCOPE_MAX_AGE_DAYS * 86400.0:
        return _untrusted_negative_scopes(
            "stale", source_path, generated_at=generated
        )

    if payload.get("report_name") != "NO_EDGE_MAP":
        return _untrusted_negative_scopes(
            "malformed_schema", source_path, generated_at=generated
        )
    if payload.get("min_clusters") != MIN_CLUSTERS:
        return _untrusted_negative_scopes(
            "policy_mismatch", source_path, generated_at=generated
        )

    counts = payload.get("counts")
    if not isinstance(counts, dict):
        return _untrusted_negative_scopes(
            "malformed_schema", source_path, generated_at=generated
        )
    category_rows = {
        "edge": payload.get("edge"),
        "no_demonstrated_edge": payload.get("no_demonstrated_edge"),
        "significantly_negative": payload.get("significantly_negative"),
        "insufficient_evidence": payload.get("insufficient_evidence_scopes"),
    }
    for category, rows in category_rows.items():
        count = counts.get(category)
        if (
            not isinstance(rows, list)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or count != len(rows)
        ):
            return _untrusted_negative_scopes(
                "malformed_schema", source_path, generated_at=generated
            )

    scopes: list[str] = []
    seen: set[str] = set()
    for category in ("edge", "no_demonstrated_edge", "significantly_negative"):
        for entry in category_rows[category]:
            if not isinstance(entry, dict):
                return _untrusted_negative_scopes(
                    "malformed_schema", source_path, generated_at=generated
                )
            scope = entry.get("scope")
            clusters = entry.get("clusters")
            ci_lower = _finite_number(entry.get("ci_lower"))
            ci_upper = _finite_number(entry.get("ci_upper"))
            if (
                not isinstance(scope, str)
                or not scope.strip()
                or scope != scope.strip()
                or scope in seen
                or isinstance(clusters, bool)
                or not isinstance(clusters, int)
                or clusters < MIN_CLUSTERS
                or ci_lower is None
                or ci_upper is None
                or ci_lower > ci_upper
                or (category == "edge" and ci_lower <= 0.0)
                or (
                    category == "no_demonstrated_edge"
                    and not (ci_lower <= 0.0 <= ci_upper)
                )
                or (category == "significantly_negative" and ci_upper >= 0.0)
            ):
                return _untrusted_negative_scopes(
                    "malformed_schema", source_path, generated_at=generated
                )
            seen.add(scope)
            if category == "significantly_negative":
                scopes.append(scope)

    for scope in category_rows["insufficient_evidence"]:
        if (
            not isinstance(scope, str)
            or not scope.strip()
            or scope != scope.strip()
            or scope in seen
        ):
            return _untrusted_negative_scopes(
                "malformed_schema", source_path, generated_at=generated
            )
        seen.add(scope)

    return NegativeScopeEvidence(
        scopes,
        trusted=True,
        status="fresh",
        generated_at=generated,
        source_path=source_path,
    )
