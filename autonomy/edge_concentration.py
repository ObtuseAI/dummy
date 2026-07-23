"""Edge-concentration / selection-bias audit (master-list evaluation).

A source's measured Brier edge is only trustworthy if it is spread across many
market types and event clusters. When nearly all of a source's edge comes from
a single market type or a handful of clusters, the "edge" is more likely a data
artifact (one quirky market, a settlement convention, a few lucky events) than
a durable skill. This audit computes, per source, how concentrated the positive
edge is -- a Herfindahl-Hirschman index over market types and the share from the
top few event clusters -- and flags sources whose edge is dangerously narrow.

Report-only: it never demotes or promotes. It is a lens the readiness review
and the promotion decision consult, exactly like the CLV grader.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/edge_concentration.json")
MIN_ROWS = 40
# HHI ranges 0..1; >0.6 over market types, or >0.5 top-3-cluster share, is a
# narrow-edge warning (not a verdict).
HHI_WARN = 0.60
TOP_CLUSTER_SHARE_WARN = 0.50


def _brier_edge(model_p: float, market_p: float, result_yes: int) -> float:
    outcome = 1.0 if result_yes else 0.0
    return (market_p - outcome) ** 2 - (model_p - outcome) ** 2


def _hhi(shares: dict[str, float]) -> float:
    total = sum(abs(v) for v in shares.values())
    if total <= 0:
        return 0.0
    return sum((abs(v) / total) ** 2 for v in shares.values())


def build_edge_concentration(
    conn: sqlite3.Connection, *, days: float | None = 120.0,
) -> dict[str, Any]:
    from autonomy.retention import install_signal_history

    install_signal_history(conn)
    clause = ""
    params: list[Any] = []
    if days is not None:
        clause = " AND s.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} day")
    rows = conn.execute(
        """
        SELECT s.source, s.market_ticker, s.probability_yes, s.features, t.result_yes,
               (SELECT m.probability_yes FROM signal_history m
                WHERE m.market_ticker = s.market_ticker AND m.source = 'market_prior'
                  AND m.created_at <= s.created_at
                ORDER BY m.created_at DESC LIMIT 1) AS market_p
        FROM signal_history s
        JOIN settlements t ON t.market_ticker = s.market_ticker
        WHERE s.source NOT IN ('market_prior', 'fused_forecast') AND s.mode = 'live'
        """ + clause,
        params,
    ).fetchall()

    from autonomy.correlation import group_key
    from autonomy.taxonomy import market_type_for

    by_source_mt: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_source_cluster: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, int] = defaultdict(int)
    total_edge: dict[str, float] = defaultdict(float)
    for source, ticker, model_p, features_json, result_yes, market_p in rows:
        if market_p is None or model_p is None:
            continue
        try:
            features = json.loads(features_json) if features_json else {}
        except (TypeError, ValueError):
            features = {}
        mt = str(
            (features or {}).get("market_type")
            or market_type_for(str(source), str(ticker), features)
            or "market"
        )
        edge = _brier_edge(float(model_p), float(market_p), int(result_yes))
        by_source_mt[source][mt] += edge
        by_source_cluster[source][group_key(str(ticker))] += edge
        counts[source] += 1
        total_edge[source] += edge

    audits = []
    for source in sorted(counts):
        if counts[source] < MIN_ROWS:
            continue
        mt_pos = {k: v for k, v in by_source_mt[source].items() if v > 0}
        cl_pos = {k: v for k, v in by_source_cluster[source].items() if v > 0}
        hhi_mt = round(_hhi(mt_pos), 4)
        top_cluster_share = 0.0
        if cl_pos:
            total_pos = sum(cl_pos.values())
            top3 = sorted(cl_pos.values(), reverse=True)[:3]
            top_cluster_share = round(sum(top3) / total_pos, 4) if total_pos > 0 else 0.0
        warnings = []
        if hhi_mt > HHI_WARN:
            warnings.append("edge_concentrated_in_one_market_type")
        if top_cluster_share > TOP_CLUSTER_SHARE_WARN:
            warnings.append("edge_concentrated_in_few_event_clusters")
        audits.append({
            "source": source,
            "rows": counts[source],
            "mean_edge": round(total_edge[source] / counts[source], 6),
            "market_type_hhi": hhi_mt,
            "positive_market_types": len(mt_pos),
            "top3_cluster_edge_share": top_cluster_share,
            "narrow_edge_warning": bool(warnings),
            "warnings": warnings,
        })

    return {
        "report_version": "edge_concentration_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "flag sources whose measured edge concentrates in one market type "
            "or a few clusters (likely artifact, not durable skill); report-only"
        ),
        "sources": sorted(audits, key=lambda item: -item["market_type_hhi"]),
        "narrow_edge_sources": [
            a["source"] for a in audits if a["narrow_edge_warning"]
        ],
    }


def write_edge_concentration(
    db_path: Path | str, *, path: Path | str = REPORT_PATH, days: float | None = 120.0,
) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        report = build_edge_concentration(conn, days=days)
    finally:
        conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
