"""Paired quant-vs-LLM value evidence on identical settled markets.

Answers the audit's model incremental-value question with a paired design:
for every settled market where a sealed LLM voice opined, compare that
voice's Brier against the fused quant forecast-of-record and the market
prior on the SAME markets. Event-cluster bootstrap CIs; report-only
(``runtime/autonomy/llm_value_report.json``). Nothing here grants model
probability authority — the authority registry has its own, stricter
dossier (>=300 clusters, digest-matched canonical artifact).
"""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.correlation import group_key

REPORT_PATH = Path("runtime/autonomy/llm_value_report.json")
MIN_PAIRED_ROWS = 12
MIN_CLUSTERS = 6
BOOTSTRAP_ROUNDS = 1000


def _brier(probability: float, result_yes: bool) -> float:
    outcome = 1.0 if result_yes else 0.0
    return (probability - outcome) ** 2


def _cluster_bootstrap_ci(
    diffs_by_cluster: dict[str, list[float]], *, rounds: int = BOOTSTRAP_ROUNDS,
) -> tuple[float, float] | None:
    clusters = [values for values in diffs_by_cluster.values() if values]
    if len(clusters) < MIN_CLUSTERS:
        return None
    rng = random.Random(20260722)
    means: list[float] = []
    for _ in range(rounds):
        sample: list[float] = []
        for _ in range(len(clusters)):
            sample.extend(rng.choice(clusters))
        means.append(sum(sample) / len(sample))
    means.sort()
    low = means[int(0.025 * (len(means) - 1))]
    high = means[int(0.975 * (len(means) - 1))]
    return round(low, 6), round(high, 6)


def _paired_rows(
    conn: sqlite3.Connection, voice: str, *, days: float | None,
) -> list[dict[str, Any]]:
    clause = ""
    params: list[Any] = [voice]
    if days is not None:
        clause = " AND v.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} day")
    rows = conn.execute(
        """
        SELECT v.market_ticker, v.probability_yes AS voice_prob,
               f.probability_yes AS fused_prob,
               m.probability_yes AS market_prob,
               t.result_yes
        FROM signal_history v
        JOIN settlements t ON t.market_ticker = v.market_ticker
        JOIN signal_history f ON f.market_ticker = v.market_ticker
             AND f.source = 'fused_forecast'
             AND f.id = (SELECT MAX(f2.id) FROM signal_history f2
                         WHERE f2.market_ticker = v.market_ticker
                           AND f2.source = 'fused_forecast')
        LEFT JOIN signal_history m ON m.market_ticker = v.market_ticker
             AND m.source = 'market_prior'
             AND m.id = (SELECT MAX(m2.id) FROM signal_history m2
                         WHERE m2.market_ticker = v.market_ticker
                           AND m2.source = 'market_prior')
        WHERE v.source = ?
        """ + clause,
        params,
    ).fetchall()
    out = []
    for ticker, voice_prob, fused_prob, market_prob, result_yes in rows:
        out.append({
            "ticker": str(ticker),
            "voice": float(voice_prob),
            "fused": float(fused_prob),
            "market": float(market_prob) if market_prob is not None else None,
            "result_yes": bool(result_yes),
        })
    return out


def build_llm_value_report(
    conn: sqlite3.Connection, *, days: float | None = 90.0,
) -> dict[str, Any]:
    from autonomy.picks import llm_voice_sources

    voices = llm_voice_sources(conn, days=days)
    comparisons: list[dict[str, Any]] = []
    for voice in voices:
        paired = _paired_rows(conn, voice, days=days)
        if len(paired) < MIN_PAIRED_ROWS:
            comparisons.append({
                "voice": voice, "status": "INSUFFICIENT_PAIRED_ROWS",
                "paired_rows": len(paired),
            })
            continue
        vs_fused: dict[str, list[float]] = {}
        vs_market: dict[str, list[float]] = {}
        voice_brier_total = fused_brier_total = 0.0
        market_brier_total = 0.0
        market_rows = 0
        for row in paired:
            cluster = group_key(row["ticker"])
            voice_brier = _brier(row["voice"], row["result_yes"])
            fused_brier = _brier(row["fused"], row["result_yes"])
            voice_brier_total += voice_brier
            fused_brier_total += fused_brier
            # Positive diff = the voice was better (lower Brier) than fused.
            vs_fused.setdefault(cluster, []).append(fused_brier - voice_brier)
            if row["market"] is not None:
                market_brier = _brier(row["market"], row["result_yes"])
                market_brier_total += market_brier
                market_rows += 1
                vs_market.setdefault(cluster, []).append(market_brier - voice_brier)
        n = len(paired)
        ci_fused = _cluster_bootstrap_ci(vs_fused)
        ci_market = _cluster_bootstrap_ci(vs_market)
        comparisons.append({
            "voice": voice,
            "status": "OK",
            "paired_rows": n,
            "event_clusters": len(vs_fused),
            "voice_brier": round(voice_brier_total / n, 6),
            "fused_brier": round(fused_brier_total / n, 6),
            "market_brier": (
                round(market_brier_total / market_rows, 6) if market_rows else None
            ),
            "brier_advantage_vs_fused_ci95": ci_fused,
            "brier_advantage_vs_market_ci95": ci_market,
            "adds_value_over_fused": (
                bool(ci_fused and ci_fused[0] > 0.0)
            ),
        })
    return {
        "report_version": "llm_value_report_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": (
            "paired per-market Brier: voice vs fused forecast-of-record vs "
            "market prior on identical settled markets; event-cluster "
            "bootstrap CI95; positive advantage = voice better"
        ),
        "authority": "report_only_no_probability_or_execution_authority",
        "voices": comparisons,
    }


def write_llm_value_report(
    db_path: Path | str, *, path: Path | str = REPORT_PATH, days: float | None = 90.0,
) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        report = build_llm_value_report(conn, days=days)
    finally:
        conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    return report
