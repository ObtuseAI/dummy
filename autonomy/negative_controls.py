"""Negative-control battery: cheap falsification before belief (Wave-7).

Ascendancy delta #1. A source's measured edge is only meaningful if it
DISAPPEARS when the world is scrambled. Each control below builds an invalid
world; a source that still "wins" there is exhibiting contamination, not
skill. The 2026-07-17 fabricated-mid bug is the motivating case: a
placebo-prior control (grade against a coin instead of the recorded prior)
would have screamed years earlier, because the phantom edge lived in the
prior, not the forecast.

Controls (all computed per source over settled, market-benchmarked rows):

  * shuffled_labels  — outcomes randomly permuted within the source's rows.
    This measures ROW-LEVEL DISCRIMINATION: real_edge - shuffled_edge. On an
    informative-prior panel, shuffling weakens the BENCHMARK too, so a
    calibrated extreme-heavy source can "survive" the shuffle on rate
    structure alone — survival is therefore never flagged as contamination.
    Instead, a source claiming positive edge whose discrimination is <= 0 is
    NOTED as rate-based (its edge lives in calibration/base-rate structure,
    not in knowing which row resolves YES).
  * rotated_priors   — each row graded against ANOTHER market's recorded
    prior (deterministic rotation). Reported as diagnostic context only:
    genuine skill ALSO survives rotation (scrambling the benchmark makes it
    weaker, not stronger), so survival is ambiguous and never flagged.
  * benchmark_calibration — an honest market's average contested price sits
    near the realized prevalence (markets are calibrated); a fabricated or
    dead benchmark is wildly off (the 2026-07 bug: avg recorded prior 0.42-
    0.48 against ~3% realized YES). A large gap while claiming positive edge
    is the fabricated-benchmark signature. Expectation: gap < 0.15.
  * random_forecaster — the source's probability replaced by a deterministic
    pseudo-uniform draw. A random forecaster must not beat the market;
    if it does, the benchmark itself is broken. Expectation: CI upper <= 0
    or spans 0.
  * placebo_prior    — rows re-graded against a flat 0.5 "market". This is a
    diagnostic baseline, not a contamination test: a useful model should
    normally beat a flat coin by much more than it beats an already-strong
    market. The falsification question is instead whether the flat coin
    significantly BEATS the recorded market on the same contested rows. If it
    does, the benchmark is weak/fabricated and any claimed edge against it is
    unsafe to trust.
  * best_day_removal — the top decile of days by contributed edge removed.
    Reported as the retained fraction; a knife-edge source retains little.
  * best_cluster_removal — the top 5 event clusters removed, same idea.

Read-only, evidence-only: this module never gates or trades. The report is a
reviewable artifact; a flagged control emits a NEGATIVE_CONTROL_FLAG alert.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPORT_PATH = Path("runtime/autonomy/negative_control_report.json")

MIN_CONTESTED_ROWS = 100      # repeated emissions alone do not establish power
MIN_CONTESTED_CLUSTERS = 30   # inference unit: independent event clusters
BOOTSTRAP_RESAMPLES = 500
CONTESTED_DISAGREEMENT = 0.05
SEED = 20260717               # deterministic battery; reruns reproduce

# An honest market's average contested price tracks realized prevalence;
# beyond this gap (while claiming positive edge) the benchmark is suspect.
MAX_BENCHMARK_PREVALENCE_GAP = 0.15
# A knife-edge source retains less than this after best-decile-day removal.
MIN_RETAINED_FRACTION = 0.0   # disclosed, not gated (sign flip is the alarm)


def _brier(p: float, outcome: int) -> float:
    return (p - float(outcome)) ** 2


def _contested_edges(
    rows: list[dict[str, Any]],
) -> list[tuple[str, float]]:
    """(cluster, market_brier - source_brier) for contested rows."""
    out = []
    for row in rows:
        p = float(row["probability_yes"])
        prior = float(row["market_probability"])
        if abs(p - prior) < CONTESTED_DISAGREEMENT:
            continue
        outcome = int(row["result_yes"])
        out.append((str(row["event_cluster"]), _brier(prior, outcome) - _brier(p, outcome)))
    return out


def _cluster_bootstrap_ci(
    edges: list[tuple[str, float]], resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, float | int] | None:
    if not edges:
        return None
    by_cluster: dict[str, list[float]] = {}
    for cluster, edge in edges:
        by_cluster.setdefault(cluster, []).append(edge)
    cluster_means = [sum(v) / len(v) for v in by_cluster.values()]
    n = len(cluster_means)
    mean = sum(cluster_means) / n
    if n < 2:
        return {"mean": round(mean, 6), "lower": round(mean, 6), "upper": round(mean, 6), "clusters": n}
    rng = random.Random(SEED)
    stats = []
    for _ in range(resamples):
        sample = [cluster_means[rng.randrange(n)] for _ in range(n)]
        stats.append(sum(sample) / n)
    stats.sort()
    lo = stats[max(0, int(0.025 * resamples) - 1)]
    hi = stats[min(resamples - 1, int(0.975 * resamples))]
    return {"mean": round(mean, 6), "lower": round(lo, 6), "upper": round(hi, 6), "clusters": n}


def _field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _rowset(rows: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append({
            "probability_yes": float(_field(row, "probability_yes")),
            "market_probability": float(_field(row, "market_probability")),
            "result_yes": int(_field(row, "result_yes")),
            "event_cluster": str(_field(row, "event_cluster")),
            "created_at": str(_field(row, "created_at", "") or ""),
        })
    return out


def _pseudo_uniform(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % 10_000) / 10_000.0


def run_battery_for_source(source: str, rows: Iterable[Any]) -> dict[str, Any]:
    """The full negative-control battery for one source's settled rows."""
    data = _rowset(rows)
    real = _cluster_bootstrap_ci(_contested_edges(data))
    result: dict[str, Any] = {
        "source": source,
        "rows": len(data),
        "real_edge": real,
        "controls": {},
        "flags": [],   # contamination-suspect signals only
        "notes": [],   # honest structural observations (never "flagged")
    }
    if real is None or len(data) < MIN_CONTESTED_ROWS:
        result["status"] = "insufficient_rows"
        return result
    if int(real.get("clusters") or 0) < MIN_CONTESTED_CLUSTERS:
        # A hundred repeated ladder/prop emissions can still represent one
        # independent event. Bootstrapping one or two clusters produces a
        # degenerate interval and must never be described as a powered
        # falsification result.
        result["status"] = "insufficient_clusters"
        result["minimum_contested_clusters"] = MIN_CONTESTED_CLUSTERS
        return result

    rng = random.Random(SEED)

    # 1. Shuffled labels -> row-level discrimination measurement.
    outcomes = [row["result_yes"] for row in data]
    rng.shuffle(outcomes)
    shuffled = [dict(row, result_yes=outcome) for row, outcome in zip(data, outcomes)]
    ci = _cluster_bootstrap_ci(_contested_edges(shuffled))
    result["controls"]["shuffled_labels"] = ci
    if ci is not None:
        discrimination = round(real["mean"] - ci["mean"], 6)
        result["controls"]["row_discrimination"] = discrimination
        if real["lower"] > 0 and discrimination <= 0:
            result["notes"].append("edge_is_rate_based_not_row_level")

    # 2. Rotated priors (diagnostic only — genuine skill also survives this,
    # since a scrambled benchmark is weaker, not stronger).
    priors = [row["market_probability"] for row in data]
    rotated = [dict(row, market_probability=priors[(i + 1) % len(priors)])
               for i, row in enumerate(data)]
    result["controls"]["rotated_priors"] = _cluster_bootstrap_ci(_contested_edges(rotated))

    # 2b. Benchmark calibration: on contested rows, an honest market's average
    # price sits near the realized prevalence. A big gap while claiming edge
    # is the fabricated/dead-benchmark signature (the 2026-07 bug class).
    contested_rows = [row for row in data
                      if abs(row["probability_yes"] - row["market_probability"]) >= CONTESTED_DISAGREEMENT]
    if contested_rows:
        avg_prior = sum(r["market_probability"] for r in contested_rows) / len(contested_rows)
        prevalence = sum(r["result_yes"] for r in contested_rows) / len(contested_rows)
        gap = abs(avg_prior - prevalence)
        result["controls"]["benchmark_calibration"] = {
            "avg_contested_prior": round(avg_prior, 4),
            "realized_prevalence": round(prevalence, 4),
            "gap": round(gap, 4),
        }
        if real["lower"] > 0 and gap > MAX_BENCHMARK_PREVALENCE_GAP:
            result["flags"].append("benchmark_miscalibrated_vs_prevalence")

    # 3. Random forecaster: deterministic pseudo-uniform replaces the model.
    randomized = [dict(row, probability_yes=_pseudo_uniform(f"{source}|{i}"))
                  for i, row in enumerate(data)]
    ci = _cluster_bootstrap_ci(_contested_edges(randomized))
    result["controls"]["random_forecaster"] = ci
    if ci and ci["lower"] > 0:
        result["flags"].append("random_forecaster_beats_market")

    # 4. Placebo prior: grade the source against a flat coin instead of the
    # real prior. This is diagnostic only. A calibrated source can quite
    # legitimately beat a flat coin by 10-20pp of Brier while improving only
    # a few tenths of a point over an efficient market; that is incremental
    # skill, not contamination.
    placebo = [dict(row, market_probability=0.5) for row in data]
    ci = _cluster_bootstrap_ci(_contested_edges(placebo))
    result["controls"]["placebo_prior"] = ci

    # Direct benchmark falsification: positive values mean the RECORDED
    # market has larger Brier error than the flat 0.5 baseline. Cluster the
    # comparison exactly as every other edge statistic so repeated emissions
    # for one event cannot manufacture significance. A strictly-positive
    # lower bound is a real measurement-integrity alarm.
    flat_vs_recorded = _cluster_bootstrap_ci([
        (
            str(row["event_cluster"]),
            _brier(float(row["market_probability"]), int(row["result_yes"]))
            - _brier(0.5, int(row["result_yes"])),
        )
        for row in contested_rows
    ])
    result["controls"]["flat_prior_vs_recorded_market"] = flat_vs_recorded
    if flat_vs_recorded and flat_vs_recorded["lower"] > 0:
        result["flags"].append("flat_prior_beats_recorded_market")

    # 5. Best-day removal: drop the top decile of days by contributed edge.
    by_day: dict[str, float] = {}
    for row in data:
        day = (row.get("created_at") or "")[:10] or "unknown"
        p, prior, outcome = row["probability_yes"], row["market_probability"], row["result_yes"]
        if abs(p - prior) >= CONTESTED_DISAGREEMENT:
            by_day[day] = by_day.get(day, 0.0) + (_brier(prior, outcome) - _brier(p, outcome))
    top_days = {d for d, _ in sorted(by_day.items(), key=lambda kv: -kv[1])[:max(1, len(by_day) // 10)]}
    trimmed = [row for row in data if ((row.get("created_at") or "")[:10] or "unknown") not in top_days]
    ci = _cluster_bootstrap_ci(_contested_edges(trimmed))
    result["controls"]["best_day_removed"] = ci
    if ci is not None and real["mean"] > 0:
        result["controls"]["best_day_retained_fraction"] = round(
            max(0.0, ci["mean"]) / max(1e-9, real["mean"]), 4)

    # 6. Best-cluster removal: drop the top 5 event clusters by edge.
    cluster_edge: dict[str, float] = {}
    for cluster, edge in _contested_edges(data):
        cluster_edge[cluster] = cluster_edge.get(cluster, 0.0) + edge
    top_clusters = {c for c, _ in sorted(cluster_edge.items(), key=lambda kv: -kv[1])[:5]}
    trimmed = [row for row in data if row["event_cluster"] not in top_clusters]
    ci = _cluster_bootstrap_ci(_contested_edges(trimmed))
    result["controls"]["best_clusters_removed"] = ci

    result["status"] = "flagged" if result["flags"] else "clean"
    return result


def run_battery(rows_by_source: dict[str, list[Any]]) -> dict[str, Any]:
    """Battery over every supplied source; writes nothing (pure)."""
    sources = {
        source: run_battery_for_source(source, rows)
        for source, rows in sorted(rows_by_source.items())
    }
    flagged = sorted(s for s, r in sources.items() if r.get("flags"))
    powered_count = sum(
        result.get("status") in {"clean", "flagged"}
        for result in sources.values()
    )
    return {
        "report_name": "NEGATIVE_CONTROL_REPORT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "sources": sources,
        "screened_source_count": len(sources),
        "powered_source_count": powered_count,
        "insufficient_source_count": len(sources) - powered_count,
        "flagged_sources": flagged,
        "status": "FLAGGED" if flagged else "CLEAN",
    }


def write_report(report: dict[str, Any], path: Path | None = None) -> Path:
    path = path or REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path
