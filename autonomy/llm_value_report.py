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


_BASELINE_TEMP_TABLES: tuple[tuple[str, str], ...] = (
    ("_lvr_latest_fused", "fused_forecast"),
    ("_lvr_latest_market", "market_prior"),
)


def _build_baselines(conn: sqlite3.Connection) -> None:
    """Materialise the latest fused / market row per market, once per report.

    The original shape carried two CORRELATED ``MAX(id)`` subqueries evaluated
    per candidate row, per voice. Against ``signal_history`` -- a UNION over the
    hot ledger and the multi-million-row archive -- that ran the writer past its
    120s budget every time, so the report produced nothing at all and the
    improvement planner independently flagged it as a dead loop. Eleven
    correlated scans become two grouped scans plus indexed joins.

    ``probability_yes`` is a bare column beside ``MAX(id)``: SQLite guarantees
    bare columns come from the row that supplied the min/max, which is exactly
    the "latest emission wins" tie-break the correlated form had. That guarantee
    is SQLite-specific, and this ledger is SQLite-only.

    Deliberately NOT filtered by ``days``: the original only windowed the voice
    side (``v``), so windowing the baselines here would silently drop pairs the
    old query kept and make the two reports incomparable.
    """
    for table, source in _BASELINE_TEMP_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS temp.{table}")
        conn.execute(
            f"CREATE TEMP TABLE {table} AS "
            "SELECT market_ticker, probability_yes, MAX(id) AS id "
            "FROM signal_history WHERE source = ? GROUP BY market_ticker",
            (source,),
        )
        conn.execute(
            f"CREATE INDEX temp.idx_{table} ON {table}(market_ticker)"
        )


def _paired_rows(
    conn: sqlite3.Connection, voice: str, *, days: float | None,
) -> list[dict[str, Any]]:
    clause = ""
    params: list[Any] = [voice]
    if days is not None:
        clause = " AND v.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} day")
    # INNER JOIN on fused / LEFT JOIN on market mirrors the original exactly:
    # a market with no fused forecast is not a pair, a missing market prior
    # leaves ``market_prob`` NULL.
    rows = conn.execute(
        """
        SELECT v.market_ticker, v.probability_yes AS voice_prob,
               f.probability_yes AS fused_prob,
               m.probability_yes AS market_prob,
               t.result_yes
        FROM signal_history v
        JOIN settlements t ON t.market_ticker = v.market_ticker
        JOIN _lvr_latest_fused f ON f.market_ticker = v.market_ticker
        LEFT JOIN _lvr_latest_market m ON m.market_ticker = v.market_ticker
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
    _build_baselines(conn)
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
    from autonomy.retention import (
        bounded_statements,
        ensure_signal_history,
        report_writer_budget_s,
    )

    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        # ``signal_history`` is a per-CONNECTION temp view unioning the hot
        # ledger with the settled-signal archive; a fresh connection that skips
        # this install fails with "no such table: signal_history". That is why
        # this report was one of the writers silently absent from runtime before
        # the 2026-07-24 failure rail exposed it. Safe on a read-only main: the
        # view lives in the temp database and the archive attaches read-only.
        ensure_signal_history(conn)
        # These queries scan the hot+archive union; bound them so a slow pass
        # surfaces as a recorded writer failure instead of running the whole
        # readiness task into its scheduler kill (which would write nothing).
        with bounded_statements(conn, report_writer_budget_s()):
            report = build_llm_value_report(conn, days=days)
    finally:
        conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    return report
