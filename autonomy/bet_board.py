"""The bet board (Wave-15): every market dummy currently prices, ranked.

Operator ask: "display dummy ranking every bet along with its decided
probability and edge percentages, sectioned by league and bet type."

Wave-14 made this a query: the brain records its FINAL fused probability as a
``fused_forecast`` ledger row for every scored market, carrying the
contemporaneous market-implied probability in features. The board is the
latest fused emission per still-open market inside a freshness window,
grouped (league, market type) via the series registry and ranked by absolute
edge within each group plus one global top list.

Read-only, cheap (indexed single-source scan + settlement anti-join), and
display-only: nothing here feeds fusion, trust, promotion, or execution.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from autonomy.picks import FUSED_SOURCE, NO_PICK_BAND
from autonomy.sports_markets import FULL, spec_for
from autonomy.taxonomy import prediction_subject

# A fused emission older than this no longer reflects a live opinion (the
# scanner re-prices continuously; anything stale usually means the market
# closed or left the watchlist).
FRESH_HOURS = 36.0

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
    """Human-readable middle token: date + teams (best effort, ticker-only)."""
    parts = str(ticker).split("-")
    return parts[1] if len(parts) >= 2 else str(ticker)


def assemble_bet_board(
    db_path: str = "runtime/autonomy/ledger.db",
    *,
    fresh_hours: float = FRESH_HOURS,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """The board payload: {generated_rows, top, groups: {league: {type: [rows]}}}."""
    owns = conn is None
    if conn is None:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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

    board_rows: list[dict[str, Any]] = []
    for ticker, (created_at, probability, uncertainty, features) in latest.items():
        market_prob = features.get("market_implied_yes")
        edge = None
        if isinstance(market_prob, (int, float)):
            edge = probability - float(market_prob)
        league, bet_type = _group_of(ticker)
        board_rows.append({
            "ticker": ticker,
            "matchup": _matchup(ticker),
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

    def _rank_key(row: dict[str, Any]) -> tuple[float, float]:
        edge = row["edge"]
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
        "fresh_hours": fresh_hours,
        "note": (
            "Display-only ranking of every market the brain currently prices "
            "(latest fused_forecast per open market). Edge = fused probability "
            "minus the market-implied probability at emission time."),
    }
