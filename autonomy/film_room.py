"""Film room: the day's worst plays, replayed with everything we saw.

Football film study is not scope-level attribution -- it is watching the exact
plays that failed, seeing what the offense saw pre-snap, and asking what was
missed. The loss engine attributes bleeding to scopes; this reel reconstructs
the N WORST settled fused forecasts individually:

  * what the fused forecast said, what the market said, what settled;
  * every source's opinion on that ticker at emission (who dissented);
  * the decision-time features persisted with the forecast (tier snapshot,
    market state).

Report-only. The reel is the operator's (and the debate panel's) film session:
recurring shapes in the worst plays become the next challenger or quarantine.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_PATH = Path("runtime/autonomy/film_room.json")
REEL_SIZE = 10
MAX_SOURCE_OPINIONS = 12


def _worst_misses(
    conn: sqlite3.Connection, *, days: float, limit: int,
) -> list[tuple]:
    from autonomy.retention import install_signal_history

    install_signal_history(conn)
    return conn.execute(
        """
        SELECT s.market_ticker, s.probability_yes, s.created_at, s.features,
               t.result_yes,
               (SELECT m.probability_yes FROM signal_history m
                WHERE m.market_ticker = s.market_ticker AND m.source = 'market_prior'
                  AND m.created_at <= s.created_at
                ORDER BY m.created_at DESC LIMIT 1) AS market_p
        FROM signal_history s
        JOIN settlements t ON t.market_ticker = s.market_ticker
        WHERE s.source = 'fused_forecast' AND s.mode = 'live'
          AND s.created_at >= datetime('now', ?)
          AND s.id = (SELECT MAX(s2.id) FROM signal_history s2
                      WHERE s2.market_ticker = s.market_ticker
                        AND s2.source = 'fused_forecast')
        ORDER BY (s.probability_yes - t.result_yes) * (s.probability_yes - t.result_yes) DESC
        LIMIT ?
        """,
        (f"-{float(days)} day", int(limit)),
    ).fetchall()


def _source_opinions(
    conn: sqlite3.Connection, ticker: str, created_at: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT source, probability_yes FROM signal_history
        WHERE market_ticker = ? AND created_at <= ?
          AND source NOT IN ('fused_forecast')
          AND id IN (SELECT MAX(id) FROM signal_history
                     WHERE market_ticker = ? AND created_at <= ?
                     GROUP BY source)
        ORDER BY source
        LIMIT ?
        """,
        (ticker, created_at, ticker, created_at, MAX_SOURCE_OPINIONS),
    ).fetchall()
    return [
        {"source": str(source), "probability_yes": round(float(prob), 4)}
        for source, prob in rows
    ]


def build_film_room(
    conn: sqlite3.Connection, *, days: float = 7.0, reel_size: int = REEL_SIZE,
) -> dict[str, Any]:
    plays: list[dict[str, Any]] = []
    for ticker, prob, created_at, features_json, result_yes, market_p in _worst_misses(
        conn, days=days, limit=reel_size,
    ):
        outcome = 1.0 if result_yes else 0.0
        our_brier = (float(prob) - outcome) ** 2
        market_brier = (
            (float(market_p) - outcome) ** 2 if market_p is not None else None
        )
        try:
            features = json.loads(features_json) if features_json else {}
        except (TypeError, ValueError):
            features = {}
        opinions = _source_opinions(conn, str(ticker), str(created_at))
        dissenters = [
            o for o in opinions
            if o["source"] != "market_prior"
            and abs(o["probability_yes"] - outcome) < abs(float(prob) - outcome) - 0.10
        ]
        plays.append({
            "ticker": str(ticker),
            "forecast_yes": round(float(prob), 4),
            "market_yes": round(float(market_p), 4) if market_p is not None else None,
            "settled_yes": bool(result_yes),
            "our_brier": round(our_brier, 4),
            "market_brier": round(market_brier, 4) if market_brier is not None else None,
            "worse_than_market": (
                market_brier is not None and our_brier > market_brier
            ),
            "emitted_at": str(created_at),
            "source_opinions": opinions,
            "sources_that_saw_it_better": [d["source"] for d in dissenters],
            "tier": (features or {}).get("tier"),
            "tier_reason": (features or {}).get("tier_reason"),
        })
    return {
        "report_version": "film_room_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "reel": plays,
        "purpose": (
            "the worst individual settled forecasts with full decision-time "
            "context -- who dissented, what the market knew; report-only"
        ),
    }


def write_film_room(
    db_path: Path | str, *, path: Path | str = REPORT_PATH, days: float = 7.0,
) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        report = build_film_room(conn, days=days)
    finally:
        conn.close()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return report
