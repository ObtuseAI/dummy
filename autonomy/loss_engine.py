"""Loss-deconstruction evolution engine (Phenon Harness WS-B).

Deterministic, read-only "where do we lose to the market" analysis over
settled, market-benchmarked signal history. Reuses the strategy miner's
plumbing exactly (``load_settled_rows``, ``_brier_edge``, per-event-cluster
mean aggregation, ``autonomy.stats.mean_ci95``) -- no new statistics engine.

Discipline (mirrors ``autonomy/strategy_miner.py`` and ``autonomy/tuner.py``):
  * Challenger-only / fail-closed / point-in-time: ``now_iso`` is passed IN
    (never ``datetime.now()`` inside ``build_loss_attribution``); rows come
    from ``load_settled_rows``, which only returns settlement-graded,
    market-benchmarked emissions (a market only has a ``settlements`` row
    once it is final -- the "post" status equivalent).
  * Per-event-cluster means, never per-row: every edge computed here goes
    through ``_cluster_mean_edges``, exactly like the miner and tuner.
  * Family-size disclosure: the artifact states how many scopes and how many
    candidate buckets were evaluated, mirroring ``rules_tested`` /
    ``family_size`` in the miner/tuner.
  * PROPOSE-THEN-HUMAN-PROMOTE, mutates NOTHING: this module writes exactly
    one JSON artifact (``runtime/autonomy/loss_attribution.json``) and never
    touches any ``.py`` source, constant, or ``promotions.json``. The LLM
    narration (``narrate_losses``) is commentary for a human reviewer only --
    it cannot reach params, promotions, or execution logic, and fails closed
    to ``{}`` on any router trouble. See
    ``tests/test_autonomy_loss_engine.py``'s no-mutation test (mirrors the
    WS-9 tuner's SHA-256 source-hash test, extended to also cover
    ``runtime/autonomy/promotions.json``).

Loop wiring: ``loss_priority`` returns an ORDERED list of bleeding scope keys
(worst first). ``autonomy/tuner.py`` reads it to reorder/annotate which
tunables it evaluates first -- it must never change the walk-forward CI gate
or the candidate/keep verdict (see ``autonomy.tuner._load_loss_priority``).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autonomy.stats import mean_ci95
from autonomy.strategy_miner import MIN_TEST_CLUSTERS as MIN_CLUSTERS
from autonomy.strategy_miner import NUMERIC_FEATURES, MinedRow, _cluster_mean_edges
from autonomy.taxonomy import specialist_for

# How many worst buckets to surface per bleeding scope in the artifact.
TOP_BUCKETS_PER_SCOPE = 3


# -- scope grouping -----------------------------------------------------------


def _scope_key(row: MinedRow) -> str:
    """The (specialist, market_type, phase_or_horizon) grouping key.

    ``row.scope`` (set by ``load_settled_rows`` via
    ``autonomy.taxonomy.grading_scope``) is already
    ``f"{source}|{market_type}|{axis}"``; this swaps the raw emitted-source
    segment for its coarser specialist label (``specialist_for``) so e.g.
    ``mlb_win_prob`` and ``mlb_totals`` roll up under one ``mlb`` scope for
    the loss-deconstruction pass, while keeping the exact market_type/axis
    the taxonomy already computed (never re-derived).
    """
    specialist = specialist_for(row.source)
    parts = str(row.scope or "").split("|", 1)
    axis_part = parts[1] if len(parts) > 1 else "na|pre"
    return f"{specialist}|{axis_part}"


# -- bucket candidates ----------------------------------------------------------


def _terciles(values: list[float]) -> list[float]:
    """Same tercile-cut construction as ``strategy_miner._terciles`` (not
    imported directly since it is private module state there; the formula is
    reproduced verbatim, not reinvented)."""
    ordered = sorted(values)
    n = len(ordered)
    if n < 3:
        return []
    cuts = []
    for fraction in (1.0 / 3.0, 2.0 / 3.0):
        index = min(n - 1, max(0, int(round(fraction * (n - 1)))))
        cuts.append(ordered[index])
    return sorted(set(cuts))


def _tercile_band(value: float, cuts: list[float]) -> str | None:
    if len(cuts) < 2:
        return None
    low, high = cuts[0], cuts[-1]
    if value <= low:
        return "low"
    if value <= high:
        return "mid"
    return "high"


def _feature_buckets(rows: list[MinedRow]) -> dict[str, list[MinedRow]]:
    """Feature-regime tercile buckets: which logged feature values coincide
    with the worst losses (the primary localization mechanism)."""
    buckets: dict[str, list[MinedRow]] = {}
    for feature in NUMERIC_FEATURES:
        values: list[float] = []
        for row in rows:
            value = row.features.get(feature)
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        if len(values) < 3:
            continue
        cuts = _terciles(values)
        if len(cuts) < 2:
            continue
        for row in rows:
            raw = row.features.get(feature)
            if raw is None:
                continue
            try:
                number = float(raw)
            except (TypeError, ValueError):
                continue
            band = _tercile_band(number, cuts)
            if band is None:
                continue
            buckets.setdefault(f"{feature}:{band}", []).append(row)
    return buckets


def _categorical_buckets(rows: list[MinedRow]) -> dict[str, list[MinedRow]]:
    """market_type / pre-vs-live / horizon buckets.

    Within one scope the axis segment of ``row.scope`` (phase for
    sports-like specialists, horizon bucket for crypto -- see
    ``autonomy.taxonomy.grading_scope``) and ``market_type`` are usually
    already fixed by the scope grouping itself; these buckets are still
    evaluated (and counted in the family-size disclosure) per the brief, and
    become genuinely informative whenever a scope's rows mix more than one
    raw source string with differing regimes.
    """
    buckets: dict[str, list[MinedRow]] = {}
    for row in rows:
        market_type = row.features.get("market_type")
        if market_type:
            buckets.setdefault(f"market_type:{market_type}", []).append(row)
        parts = str(row.scope or "").split("|")
        axis = parts[-1] if len(parts) > 1 else "unknown"
        buckets.setdefault(f"regime:{axis or 'unknown'}", []).append(row)
    return buckets


def _bucket_stats(rows: list[MinedRow]) -> dict[str, Any] | None:
    edges = _cluster_mean_edges(rows)
    n_clusters = len(edges)
    if n_clusters == 0:
        return None
    mean = sum(edges) / n_clusters
    stats = mean_ci95(edges) or {}
    lower = stats.get("lower")
    upper = stats.get("upper")
    return {
        "edge": round(mean, 6),
        "ci95": [
            round(float(lower), 6) if lower is not None else None,
            round(float(upper), 6) if upper is not None else None,
        ],
        "n_clusters": n_clusters,
    }


# -- attribution ----------------------------------------------------------------


def build_loss_attribution(rows: list[MinedRow], now_iso: str) -> dict[str, Any]:
    """Deterministic loss-deconstruction pass -> JSON-able artifact.

    Point-in-time: ``now_iso`` is the caller's clock, never read internally
    (mirrors how ``strategy_miner.mining_report``/``tuner.tuning_report``
    take their timestamp). Pure and read-only: no I/O, no mutation.
    """
    by_scope: dict[str, list[MinedRow]] = {}
    for row in rows:
        by_scope.setdefault(_scope_key(row), []).append(row)

    scope_entries: list[dict[str, Any]] = []
    scopes_evaluated = 0
    buckets_evaluated = 0

    for scope, scope_rows in sorted(by_scope.items()):
        scopes_evaluated += 1
        cluster_edges = _cluster_mean_edges(scope_rows)
        n_clusters = len(cluster_edges)
        cluster_edge = round(sum(cluster_edges) / n_clusters, 6) if n_clusters else 0.0

        if n_clusters < MIN_CLUSTERS:
            scope_entries.append({
                "scope": scope, "n_clusters": n_clusters, "cluster_edge": cluster_edge,
                "worst_buckets": [], "verdict": "insufficient_data",
            })
            continue

        if cluster_edge >= 0.0:
            scope_entries.append({
                "scope": scope, "n_clusters": n_clusters, "cluster_edge": cluster_edge,
                "worst_buckets": [], "verdict": "not_bleeding",
            })
            continue

        # Bleeding: cluster_edge < 0 and n_clusters >= MIN_CLUSTERS. Bucket it.
        candidates: dict[str, list[MinedRow]] = {}
        candidates.update(_feature_buckets(scope_rows))
        candidates.update(_categorical_buckets(scope_rows))

        evaluated: list[dict[str, Any]] = []
        for label, bucket_rows in sorted(candidates.items()):
            buckets_evaluated += 1
            stat = _bucket_stats(bucket_rows)
            if stat is None:
                continue
            evaluated.append({"bucket": label, **stat})

        qualifying = [b for b in evaluated if b["n_clusters"] >= MIN_CLUSTERS]
        qualifying.sort(key=lambda bucket: bucket["edge"])
        worst = qualifying[:TOP_BUCKETS_PER_SCOPE]

        scope_entries.append({
            "scope": scope, "n_clusters": n_clusters, "cluster_edge": cluster_edge,
            "worst_buckets": worst,
            "verdict": "bleeding" if worst else "insufficient_data",
        })

    return {
        "generated_at": now_iso,
        "settled_rows": len(rows),
        "scopes": scope_entries,
        # Multiple-comparisons disclosure mirroring strategy_miner's
        # `rules_tested` / tuner's `family_size`: how many grading scopes and
        # how many candidate buckets (across bleeding scopes only, since only
        # bleeding scopes are decomposed) were evaluated.
        "family_size": {
            "scopes_evaluated": scopes_evaluated,
            "buckets_evaluated": buckets_evaluated,
        },
        # Filled by narrate_losses(); never populated here so a caller who
        # skips narration still gets a well-formed, honestly-empty artifact.
        "narration": {},
        "note": (
            "Read-only loss-deconstruction artifact. Cluster-level means"
            " only (never per-row); a scope/bucket below MIN_CLUSTERS event"
            " clusters is marked insufficient_data, never a confident claim."
            " Proposes a priority ordering for the tuner and a bleeding"
            " summary for the dashboard/readiness report -- mutates no"
            " source file, constant, or promotion."
        ),
    }


# -- narration (commentary only, fail-closed) ------------------------------------


def narrate_losses(attribution: dict[str, Any], router: Any) -> dict[str, Any]:
    """Per-scope 'what went wrong + a hypothesis' commentary for a human
    reviewer. Reuses the SAME verified-LLM router infra as
    ``autonomy.signals.llm_analyst.LlmAnalystSignal`` (construct via that
    class's own ``_get_router()``; never a new client here).

    Commentary only: the returned dict is never read back into any pricing,
    tuning, or promotion path -- it only ever lands in the artifact's
    ``narration`` field for a person to read. Fail-closed to ``{}`` on any
    trouble at all (no router, nested event loop, timeout, malformed
    response) -- the deterministic attribution this function receives is
    never mutated.
    """
    if router is None:
        return {}
    bleeding = [
        entry for entry in (attribution or {}).get("scopes", [])
        if entry.get("verdict") == "bleeding"
    ]
    if not bleeding:
        return {}

    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        # Called from inside an existing event loop: skip rather than nest
        # asyncio.run (same guard LlmAnalystSignal.generate uses).
        return {}

    from model_router.tasks import ModelTask

    narration: dict[str, str] = {}
    for entry in bleeding:
        scope = str(entry.get("scope"))
        prompt = (
            f"Grading scope: {scope}\n"
            f"Cluster-mean Brier edge vs market: {entry.get('cluster_edge')}"
            " (negative = we trail the market)\n"
            f"Worst buckets (cluster-level, with 95% CI): "
            f"{json.dumps(entry.get('worst_buckets'), sort_keys=True)}\n"
            "In 2-3 sentences: what likely went wrong, and one hypothesis to"
            " test. This is commentary for a human reviewer only -- do not"
            " propose a specific parameter value or code change to apply"
            " automatically."
        )
        try:
            envelope = asyncio.run(
                router.call(ModelTask.FORECAST_OPINION, prompt, context={"scope": scope})
            )
            text = str(getattr(envelope, "content", "") or "")
        except Exception:
            # Fail-closed: ANY router trouble blanks the whole narration pass
            # rather than a partially-filled, possibly-misleading one.
            return {}
        narration[scope] = text[:800]
    return narration


# -- loop wiring: tuner priority (order/annotate only, never gates) --------------


def loss_priority(attribution: dict[str, Any]) -> list[str]:
    """Ordered list of bleeding scope keys, worst (most negative) first.

    Consumed by ``autonomy.tuner`` to decide which tunables to evaluate /
    surface FIRST. It is purely an ordering signal: the tuner's walk-forward
    CI gate and candidate/keep verdict must be computed exactly as before and
    are never touched by this list (see
    ``tests/test_autonomy_loss_engine.py::test_tuner_priority_...``).
    """
    bleeding = [
        entry for entry in (attribution or {}).get("scopes", [])
        if entry.get("verdict") == "bleeding"
    ]
    bleeding.sort(key=lambda entry: entry.get("cluster_edge", 0.0))
    return [str(entry["scope"]) for entry in bleeding]


# -- artifact I/O -----------------------------------------------------------------


def write_report(report: dict[str, Any], path: Path) -> None:
    """Atomic write, byte-for-byte the same pattern as
    ``strategy_miner.write_report`` / ``tuner.write_report``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
