"""Fusion ablation: each source's MARGINAL contribution to the ensemble.

Ablation is how ML science attributes value: remove one component, measure
the damage. Per-source standalone accuracy (the learner's contested Brier)
answers "is this source good?"; it cannot answer "does this source add
anything the ensemble doesn't already have?" -- a strong-but-redundant source
scores well standalone while contributing nothing marginal.

This report replays settled markets offline with a DISCLOSED approximation of
the fusion rule (global learner weight / emission variance, inverse-variance
mean -- the real fusion adds scope trust and family grouping, so this is a
ranking lens, not a weight authority) and computes each source's
leave-one-out Brier delta, averaged per event cluster:

  positive marginal = removing the source makes the ensemble WORSE (it adds
  information); ~zero with a healthy standalone record = redundancy.

Report-only; feeds roster review, never weights.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/fusion_ablation.json")
RECAL_PATH = Path("runtime/autonomy/last_recalibration.json")
MIN_SOURCES_PER_MARKET = 3
MIN_MARKETS_PER_SOURCE = 30
REDUNDANCY_EPSILON = 0.0005


def _weights(recal_path: Path) -> dict[str, float]:
    try:
        recal = json.loads(Path(recal_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    merged: dict[str, float] = {}
    for key in ("weights", "global_weights", "source_weights"):
        block = recal.get(key)
        if isinstance(block, dict):
            for name, value in block.items():
                if isinstance(value, (int, float)):
                    merged[str(name)] = float(value)
    return merged


def _emissions(conn: sqlite3.Connection, days: float | None) -> list[tuple]:
    from autonomy.retention import install_signal_history

    install_signal_history(conn)
    clause = ""
    params: list[Any] = []
    if days is not None:
        clause = " AND s.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} day")
    return conn.execute(
        """
        SELECT s.market_ticker, s.source, s.probability_yes, s.uncertainty,
               t.result_yes
        FROM signal_history s
        JOIN settlements t ON t.market_ticker = s.market_ticker
        WHERE s.mode = 'live'
          AND s.source NOT IN ('fused_forecast', 'market_prior')
          AND s.source NOT LIKE '%::cal'
          AND s.id IN (SELECT MAX(id) FROM signal_history
                       WHERE market_ticker = s.market_ticker AND source = s.source)
        """ + clause,
        params,
    ).fetchall()


def build_fusion_ablation(
    conn: sqlite3.Connection, *, days: float | None = 90.0,
    recal_path: Path = RECAL_PATH,
) -> dict[str, Any]:
    from autonomy.correlation import group_key

    weights = _weights(recal_path)
    markets: dict[str, dict[str, Any]] = {}
    for ticker, source, prob, uncertainty, result_yes in _emissions(conn, days):
        entry = markets.setdefault(str(ticker), {
            "result": bool(result_yes), "members": {},
        })
        sigma2 = max(1e-4, float(uncertainty or 0.1) ** 2)
        entry["members"][str(source)] = (
            float(prob), weights.get(str(source), 1.0) / sigma2,
        )

    deltas: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    used_markets = 0
    for ticker, entry in markets.items():
        members: dict[str, tuple[float, float]] = entry["members"]
        if len(members) < MIN_SOURCES_PER_MARKET:
            continue
        used_markets += 1
        outcome = 1.0 if entry["result"] else 0.0
        total_weight = sum(w for _p, w in members.values())
        if total_weight <= 0:
            continue
        fused = sum(p * w for p, w in members.values()) / total_weight
        full_brier = (fused - outcome) ** 2
        cluster = group_key(ticker)
        for source, (prob, weight) in members.items():
            remaining = total_weight - weight
            if remaining <= 0:
                continue
            loo = (sum(p * w for p, w in members.values()) - prob * weight) / remaining
            loo_brier = (loo - outcome) ** 2
            # Positive delta = ensemble got worse without the source.
            deltas[source][cluster].append(loo_brier - full_brier)

    sources = []
    for source, clusters in deltas.items():
        n_markets = sum(len(v) for v in clusters.values())
        if n_markets < MIN_MARKETS_PER_SOURCE:
            continue
        cluster_means = [sum(v) / len(v) for v in clusters.values()]
        marginal = sum(cluster_means) / len(cluster_means)
        sources.append({
            "source": source,
            "markets": n_markets,
            "event_clusters": len(cluster_means),
            "marginal_brier_contribution": round(marginal, 6),
            "adds_information": marginal > REDUNDANCY_EPSILON,
            "redundant_or_harmful": marginal <= REDUNDANCY_EPSILON,
        })
    sources.sort(key=lambda item: -item["marginal_brier_contribution"])
    return {
        "report_version": "fusion_ablation_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "approximate_inverse_variance_loo_v1: global learner weight / "
            "emission variance, leave-one-out per market, cluster-averaged; "
            "the production fusion adds scope trust + family grouping, so "
            "this ranks marginal value and never sets weights"
        ),
        "markets_used": used_markets,
        "sources": sources,
        "redundancy_candidates": [
            item["source"] for item in sources if item["redundant_or_harmful"]
        ],
    }


def write_fusion_ablation(
    db_path: Path | str, *, path: Path | str = REPORT_PATH,
    days: float | None = 90.0, recal_path: Path = RECAL_PATH,
) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        report = build_fusion_ablation(conn, days=days, recal_path=recal_path)
    finally:
        conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
