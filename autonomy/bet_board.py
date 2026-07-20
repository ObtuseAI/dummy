"""The bet board (Wave-15): every market dummy currently prices, ranked.

Operator ask: "display dummy ranking every bet along with its decided
probability and edge percentages, sectioned by league and bet type."

Wave-14 made this a query: the brain records its FINAL fused probability as a
``fused_forecast`` ledger row for every scored market, carrying the
contemporaneous market-implied probability in features. The board is the
latest fused emission per still-open market inside a freshness window,
grouped (league, market type) via the series registry and ranked by absolute
edge within each group plus one global top list.

Two paths, artifact-first (matching every other dashboard panel):

  * ``write_board_artifact`` -- the brain calls this at the end of each cycle
    with the in-memory (market, forecast) pairs it just scored, atomically
    writing ``runtime/autonomy/bet_board.json``. No DB involved: the cycle
    already holds every row, titles included, and the busy ledger (single
    writer, non-WAL) must never be contended for a display read.
  * ``assemble_bet_board`` -- serve the fresh artifact; only when it is
    missing/stale fall back to a busy-tolerant read of the Wave-14
    ``fused_forecast`` ledger rows (cold-start path).

Display-only: nothing here feeds fusion, trust, promotion, or execution.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from autonomy.picks import FUSED_SOURCE, NO_PICK_BAND
from autonomy.sports_markets import FULL, spec_for
from autonomy.taxonomy import prediction_subject

# A fused emission older than this no longer reflects a live opinion (the
# scanner re-prices continuously; anything stale usually means the market
# closed or left the watchlist).
FRESH_HOURS = 36.0

BOARD_PATH = Path("runtime/autonomy/bet_board.json")
# Cycles run every ~10 minutes; an artifact older than this is treated as
# stale and the ledger fallback is consulted instead.
ARTIFACT_FRESH_SECONDS = 2 * 3600.0

# Confidence tiers on distance from the coin flip, mirroring picks grading:
# inside NO_PICK_BAND there is no pick at all.
TIERS = (
    (0.20, "A"),      # >= 70/30
    (0.10, "B"),      # >= 60/40
    (NO_PICK_BAND, "C"),
)


def _tier(probability: float) -> str | None:
    distance = abs(probability - 0.5)
    for threshold, label in TIERS:
        if distance >= threshold:
            return label
    return None


def _group_of(ticker: str) -> tuple[str, str]:
    """(league, bet type) for grouping; non-sports fall to their subject."""
    spec = spec_for(ticker)
    if spec is not None:
        label = spec.market_type
        if spec.segment != FULL:
            label = f"{spec.segment}_{spec.market_type}"
        if spec.is_prop and spec.stat:
            label = f"prop_{spec.stat}"
        return spec.league, label
    subject = prediction_subject(ticker)
    return subject or "other", "market"


def _matchup(ticker: str) -> str:
    """Human-readable matchup (``SD vs ATL``), ticker-only, fail-soft to raw."""
    from autonomy.market_labels import humanize_ticker

    return humanize_ticker(ticker)["matchup"]


def _finish_board(board_rows: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Rank, group, and wrap raw board rows into the served payload."""
    def _rank_key(row: dict[str, Any]) -> tuple[float, float]:
        edge = row.get("edge")
        return (abs(edge) if edge is not None else -1.0,
                abs(row["probability"] - 0.5))

    board_rows.sort(key=_rank_key, reverse=True)
    for position, row in enumerate(board_rows, start=1):
        row["rank"] = position
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in board_rows:
        groups.setdefault(row["league"], {}).setdefault(row["bet_type"], []).append(row)
    return {
        "rows": len(board_rows),
        "top": board_rows[:25],
        "groups": groups,
        "note": (
            "Display-only ranking of every market the brain currently prices. "
            "Edge = fused probability minus the market-implied probability."),
        **extra,
    }


def write_board_artifact(
    scored: list[tuple[Any, Any]],
    *,
    path: Path | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Write the board from the cycle's in-memory (market, forecast) pairs.

    Called by the brain at the end of every cycle -- titles included, no DB
    touched, atomic replace so the dashboard never reads a torn file."""
    from datetime import datetime, timezone

    from autonomy.market_labels import humanize_ticker

    board_rows: list[dict[str, Any]] = []
    for market, forecast in scored:
        probability = float(forecast.probability_yes)
        market_prob = forecast.market_implied_yes
        league, bet_type = _group_of(market.ticker)
        hl = humanize_ticker(market.ticker)
        board_rows.append({
            "ticker": market.ticker,
            "title": getattr(market, "title", None) or hl["label"],
            "matchup": hl["matchup"],
            "market": hl["market"],
            "label": hl["label"],
            "league": league,
            "bet_type": bet_type,
            "probability": round(probability, 4),
            "market_probability": (
                round(float(market_prob), 4)
                if isinstance(market_prob, (int, float)) else None),
            "edge": (round(probability - float(market_prob), 4)
                     if isinstance(market_prob, (int, float)) else None),
            "pick": ("yes" if probability >= 0.5 else "no")
                    if _tier(probability) else None,
            "tier": _tier(probability),
            "uncertainty": round(float(forecast.uncertainty), 3),
            # Wave-26: the cycle's live book, captured point-in-time so the
            # vNext shadow runtime issues episodes from this artifact with
            # zero additional network reads.
            "yes_bid": getattr(market, "yes_bid", None),
            "yes_ask": getattr(market, "yes_ask", None),
            "no_bid": getattr(market, "no_bid", None),
            "no_ask": getattr(market, "no_ask", None),
            "liquidity": getattr(market, "liquidity", None),
            "close_time": getattr(market, "close_time", None),
        })
    payload = _finish_board(
        board_rows,
        generated_at=now_iso or datetime.now(timezone.utc).isoformat(),
        source="cycle_artifact",
    )
    target = path or BOARD_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    return payload


def _artifact_board(path: Path) -> dict[str, Any] | None:
    from datetime import datetime, timezone

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        generated = payload.get("generated_at")
        stamp = datetime.fromisoformat(str(generated))
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
    except (OSError, ValueError, TypeError):
        return None
    if age > ARTIFACT_FRESH_SECONDS:
        return None
    payload["age_seconds"] = round(age, 1)
    return payload


def assemble_bet_board(
    db_path: str = "runtime/autonomy/ledger.db",
    *,
    fresh_hours: float = FRESH_HOURS,
    conn: sqlite3.Connection | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """The board payload: cycle artifact first, ledger fallback (cold start)."""
    if conn is None:
        artifact = _artifact_board(artifact_path or BOARD_PATH)
        if artifact is not None:
            return artifact
    owns = conn is None
    if conn is None:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        except sqlite3.Error as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "rows": 0, "groups": {}}
    try:
        try:
            from autonomy.retention import install_signal_history

            install_signal_history(conn)
            rows = conn.execute(
                """
                SELECT s.market_ticker, s.probability_yes, s.uncertainty,
                       s.created_at, s.features
                FROM signal_history s
                WHERE s.source = ?
                  AND s.created_at >= datetime('now', ?)
                  AND s.market_ticker NOT IN (SELECT market_ticker FROM settlements)
                """,
                (FUSED_SOURCE, f"-{float(fresh_hours)} hours"),
            ).fetchall()
        except sqlite3.Error as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "rows": 0, "groups": {}}
    finally:
        if owns:
            conn.close()

    latest: dict[str, tuple[str, float, float, dict[str, Any]]] = {}
    for ticker, probability, uncertainty, created_at, features_raw in rows:
        ticker = str(ticker)
        held = latest.get(ticker)
        if held is not None and str(created_at) <= held[0]:
            continue
        try:
            features = json.loads(features_raw) if isinstance(features_raw, str) else (features_raw or {})
        except (TypeError, ValueError):
            features = {}
        latest[ticker] = (str(created_at), float(probability), float(uncertainty), features)

    from autonomy.market_labels import humanize_ticker

    board_rows: list[dict[str, Any]] = []
    for ticker, (created_at, probability, uncertainty, features) in latest.items():
        market_prob = features.get("market_implied_yes")
        edge = None
        if isinstance(market_prob, (int, float)):
            edge = probability - float(market_prob)
        league, bet_type = _group_of(ticker)
        hl = humanize_ticker(ticker)
        board_rows.append({
            "ticker": ticker,
            "matchup": hl["matchup"],
            "market": hl["market"],
            "label": hl["label"],
            "league": league,
            "bet_type": bet_type,
            "probability": round(probability, 4),
            "market_probability": (
                round(float(market_prob), 4)
                if isinstance(market_prob, (int, float)) else None),
            "edge": round(edge, 4) if edge is not None else None,
            "pick": ("yes" if probability >= 0.5 else "no")
                    if _tier(probability) else None,
            "tier": _tier(probability),
            "uncertainty": round(uncertainty, 3),
            "as_of": created_at,
        })

    return _finish_board(board_rows, fresh_hours=fresh_hours, source="ledger_fallback")
