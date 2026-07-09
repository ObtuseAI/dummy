"""Tape reader: market microstructure features from Kalshi candlesticks.

A quant does not look at a JPEG of a chart; they read the numbers the chart
is drawn from. This module turns a market's recent 1-minute candlesticks
into a compact feature block — momentum, volume surge, range position,
spread — consumed two ways:

  1. As context for the LLM debate panel on top-K edge markets, so the
     panel sees how the tape is moving, not just a static quote.
  2. As logged features for future grading (the retro engine can replay
     tape states against settlements to learn which patterns carry signal
     before any tape-driven sizing is trusted).

Fail-closed: not enough candles -> None, and the loop proceeds without it.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from autonomy.retro import candle_quote_at, default_fetch_candles

LOOKBACK_MINUTES = 120


def _mid(candle: dict[str, Any]) -> float | None:
    from autonomy.retro import _dollars_to_cents

    bid = _dollars_to_cents((candle.get("yes_bid") or {}).get("close_dollars"))
    ask = _dollars_to_cents((candle.get("yes_ask") or {}).get("close_dollars"))
    if bid is None or ask is None or ask <= 0:
        return None
    return (bid + ask) / 2.0


def tape_features(series: str, ticker: str,
                  fetch_candles: Callable[..., list[dict[str, Any]]] | None = None,
                  now_ts: int | None = None) -> dict[str, Any] | None:
    """Microstructure snapshot from the last two hours of 1-minute candles."""
    fetch = fetch_candles or default_fetch_candles
    now_ts = now_ts or int(time.time())
    try:
        candles = fetch(series, ticker, now_ts - LOOKBACK_MINUTES * 60, now_ts, 1)
    except Exception:
        return None
    points: list[tuple[int, float, float]] = []  # (end_ts, mid, volume)
    for candle in candles:
        mid = _mid(candle)
        if mid is None:
            continue
        try:
            end = int(candle.get("end_period_ts", 0))
            volume = float(candle.get("volume_fp") or 0)
        except Exception:
            continue
        points.append((end, mid, volume))
    if len(points) < 3:
        return None
    points.sort()

    def mid_at(age_seconds: int) -> float | None:
        cutoff = now_ts - age_seconds
        older = [p for p in points if p[0] <= cutoff]
        return older[-1][1] if older else None

    mid_now = points[-1][1]
    mid_15 = mid_at(15 * 60)
    mid_60 = mid_at(60 * 60)
    mids = [p[1] for p in points]
    lo, hi = min(mids), max(mids)
    total_volume = sum(p[2] for p in points)
    recent_volume = sum(p[2] for p in points if p[0] > now_ts - 15 * 60)
    # Volume surge: last 15 minutes vs a uniform share of the window.
    expected_recent = total_volume * (15.0 / LOOKBACK_MINUTES)
    surge = (recent_volume / expected_recent) if expected_recent > 0 else None

    quote = candle_quote_at(candles, now_ts)
    return {
        "mid_now_cents": round(mid_now, 1),
        "momentum_15m_cents": round(mid_now - mid_15, 1) if mid_15 is not None else None,
        "momentum_60m_cents": round(mid_now - mid_60, 1) if mid_60 is not None else None,
        "range_low_cents": round(lo, 1),
        "range_high_cents": round(hi, 1),
        "range_position": round((mid_now - lo) / (hi - lo), 2) if hi > lo else None,
        "volume_2h": round(total_volume, 1),
        "volume_surge_15m": round(surge, 2) if surge is not None else None,
        "spread_cents": (quote["yes_ask"] - quote["yes_bid"]) if quote else None,
        "n_candles": len(points),
    }


def describe_tape(features: dict[str, Any] | None) -> str:
    """One-line tape summary for an LLM prompt; empty string when absent."""
    if not features:
        return ""
    bits = [f"mid {features['mid_now_cents']}c"]
    if features.get("momentum_15m_cents") is not None:
        bits.append(f"15m move {features['momentum_15m_cents']:+.1f}c")
    if features.get("momentum_60m_cents") is not None:
        bits.append(f"60m move {features['momentum_60m_cents']:+.1f}c")
    if features.get("range_position") is not None:
        bits.append(f"at {features['range_position']:.0%} of 2h range "
                    f"[{features['range_low_cents']}-{features['range_high_cents']}c]")
    if features.get("volume_surge_15m") is not None:
        bits.append(f"15m volume {features['volume_surge_15m']}x baseline")
    if features.get("spread_cents") is not None:
        bits.append(f"spread {features['spread_cents']}c")
    return "Tape (2h, 1-min candles): " + ", ".join(bits)
