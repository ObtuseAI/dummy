"""The chartist: candlestick patterns, divergences, trends, cross-examined
across the full timeframe ladder (Wave-24).

Pure library over the CryptoDataHub's OHLCV streams (minute / hourly /
daily). Builds the analyst's actual workflow as code:

  LADDER      1m -> 5m -> 15m (aggregated from minute), 1h -> 4h
              (aggregated from hourly), 1d native. OHLCV-correct
              aggregation: open=first, high=max, low=min, close=last,
              volume=sum.
  PATTERNS    a context-gated candlestick arsenal -- engulfings, hammer /
              shooting star, doji, morning / evening star, three white
              soldiers / black crows, haramis, tweezers, marubozu -- each
              scored 0..1 and only credited where it means something (a
              hammer in an uptrend is noise; after a downswing it is a
              reversal candidate).
  DIVERGENCES swing-anchored, on RSI: REGULAR (price extreme not confirmed
              by the oscillator -> reversal warning) and HIDDEN (oscillator
              extreme against a shallower price retrace -> continuation
              evidence), both directions, strength by oscillator gap.
  TRENDS      EMA-pair slope + the structure library's fitted channel
              (reused, never duplicated) per timeframe.
  CROSS-EXAM  one synthesis: timeframe votes weighted by horizon, pattern
              and divergence evidence blended WITH vetoes -- a regular
              divergence against the trend cuts conviction, a hidden
              divergence with the trend raises it, and disagreement between
              timeframes is reported honestly instead of averaged away.

Everything is deterministic and side-effect-free; the signal wrapper
(autonomy/signals/crypto_chartist.py) owns market pricing and stays
challenger-only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from autonomy.crypto_structure import swing_points, trend_channel

# Timeframe ladder: (name, source stream, aggregation factor, cross-exam weight).
# Higher timeframes carry more weight -- a daily trend outranks a 5m pattern.
TIMEFRAMES: tuple[tuple[str, str, int, float], ...] = (
    ("5m", "minute", 5, 0.10),
    ("15m", "minute", 15, 0.15),
    ("1h", "hourly", 1, 0.20),
    ("4h", "hourly", 4, 0.25),
    ("1d", "daily", 1, 0.30),
)

PATTERN_LOOKBACK = 3          # patterns scored on the last few closed bars
DOJI_BODY_FRACTION = 0.1
MARUBOZU_BODY_FRACTION = 0.9
WICK_DOMINANCE = 2.0          # hammer/star: wick >= 2x body
DIVERGENCE_MIN_GAP = 2.0      # RSI points between swings to count


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(1e-12, self.high - self.low)

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


@dataclass(frozen=True)
class PatternHit:
    name: str
    direction: int            # +1 bullish, -1 bearish
    strength: float           # 0..1, context included


@dataclass(frozen=True)
class DivergenceHit:
    kind: str                 # regular_bullish / regular_bearish / hidden_bullish / hidden_bearish
    direction: int
    strength: float


@dataclass(frozen=True)
class TimeframeView:
    timeframe: str
    trend: float              # -1..1 (EMA slope + channel blend)
    channel_position: float | None
    patterns: tuple[PatternHit, ...]
    divergences: tuple[DivergenceHit, ...]
    rsi: float | None
    bars: int


@dataclass(frozen=True)
class CrossExam:
    score: float              # -1..1 blended directional conviction
    conviction: float         # 0..1 agreement-weighted confidence
    votes: dict[str, float] = field(default_factory=dict)
    boosts: tuple[str, ...] = ()
    vetoes: tuple[str, ...] = ()
    disagreements: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Candles
# ---------------------------------------------------------------------------


def candles_from_state(state: dict[str, Any], stream: str) -> list[Candle]:
    """Return oldest-first closed candles from one hub stream.

    The production hub emits a list of row dictionaries. Earlier Wave-24
    tests accidentally supplied a dict of arrays, which made the live chartist
    raise before silently abstaining. The legacy column shape remains accepted
    while production rows are now the primary, provenance-aware contract.
    """
    raw = state.get(f"{stream}_ohlcv") or []
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        rows = [row for row in raw if isinstance(row, dict)]
    elif isinstance(raw, dict):
        opens = raw.get("open") or []
        highs = raw.get("high") or []
        lows = raw.get("low") or []
        closes = raw.get("close") or []
        volumes = raw.get("volume") or []
        at_values = raw.get("at_s") or raw.get("open_time_s") or []
        count = min(len(opens), len(highs), len(lows), len(closes), len(volumes))
        for index in range(count):
            row = {
                "open": opens[index],
                "high": highs[index],
                "low": lows[index],
                "close": closes[index],
                "volume": volumes[index],
            }
            if index < len(at_values):
                row["open_time_s"] = at_values[index]
            rows.append(row)
    else:
        raise TypeError(f"{stream}_ohlcv must be a list of rows or dict of arrays")

    parsed: list[tuple[int | None, Candle, tuple[float, ...]]] = []
    for row in rows:
        if row.get("closed") is False:
            continue
        close_time = row.get("close_time_s")
        received_at = row.get("received_at_s", state.get("received_at_s"))
        if close_time is not None and received_at is not None:
            try:
                if float(close_time) > float(received_at):
                    continue
            except (TypeError, ValueError):
                continue
        try:
            candle = Candle(
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            not all(
                math.isfinite(value)
                for value in (
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                )
            )
            or min(candle.open, candle.high, candle.low, candle.close) <= 0
            or candle.volume < 0
            or candle.high < max(candle.open, candle.close, candle.low)
            or candle.low > min(candle.open, candle.close, candle.high)
        ):
            continue
        open_time_raw = row.get("open_time_s", row.get("at_s"))
        try:
            open_time = int(open_time_raw) if open_time_raw is not None else None
        except (TypeError, ValueError):
            open_time = None
        identity = (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        )
        parsed.append((open_time, candle, identity))

    if parsed and all(item[0] is not None for item in parsed):
        parsed.sort(key=lambda item: int(item[0] or 0))
        deduplicated: list[tuple[int | None, Candle, tuple[float, ...]]] = []
        for item in parsed:
            if deduplicated and item[0] == deduplicated[-1][0]:
                if item[2] != deduplicated[-1][2]:
                    raise ValueError(
                        f"conflicting duplicate {stream} candle at {item[0]}"
                    )
                continue
            deduplicated.append(item)
        parsed = deduplicated
    return [item[1] for item in parsed]


def aggregate_candles(candles: list[Candle], factor: int) -> list[Candle]:
    """OHLCV-correct roll-up; partial trailing group dropped (only closed bars)."""
    if factor <= 1:
        return list(candles)
    out: list[Candle] = []
    for start in range(0, len(candles) - factor + 1, factor):
        group = candles[start:start + factor]
        out.append(Candle(
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume=sum(c.volume for c in group),
        ))
    return out


# ---------------------------------------------------------------------------
# Indicators (local, minimal -- heavier ones live in ta_foundry)
# ---------------------------------------------------------------------------


def _ema(values: list[float], span: int) -> float | None:
    if len(values) < span:
        return None
    alpha = 2.0 / (span + 1.0)
    ema = values[0]
    for value in values[1:]:
        ema = alpha * value + (1.0 - alpha) * ema
    return ema


def rsi_series(closes: list[float], periods: int = 14) -> list[float]:
    """Wilder RSI per bar (NaN-free: seeded after ``periods`` bars)."""
    if len(closes) <= periods:
        return []
    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in zip(closes, closes[1:]):
        change = curr - prev
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
    avg_gain = sum(gains[:periods]) / periods
    avg_loss = sum(losses[:periods]) / periods
    series: list[float] = []
    for gain, loss in zip(gains[periods:], losses[periods:]):
        avg_gain = (avg_gain * (periods - 1) + gain) / periods
        avg_loss = (avg_loss * (periods - 1) + loss) / periods
        if avg_loss <= 0:
            series.append(100.0)
        else:
            rs = avg_gain / avg_loss
            series.append(100.0 - 100.0 / (1.0 + rs))
    return series


def trend_score(closes: list[float]) -> float:
    """-1..1 from the EMA(9/21) spread plus the fitted channel slope."""
    fast = _ema(closes[-60:], 9)
    slow = _ema(closes[-60:], 21)
    if fast is None or slow is None or slow <= 0:
        return 0.0
    ema_part = math.tanh((fast - slow) / slow * 200.0)
    channel = trend_channel(closes)
    channel_part = 0.0
    if channel is not None:
        channel_part = math.tanh(channel.slope_bps_per_bar / 20.0) * max(
            0.2, channel.r_squared)
    return max(-1.0, min(1.0, 0.6 * ema_part + 0.4 * channel_part))


# ---------------------------------------------------------------------------
# Candlestick patterns (context-gated)
# ---------------------------------------------------------------------------


def _context(closes: list[float]) -> float:
    """Local trend before the pattern bar(s); patterns score against it."""
    return trend_score(closes[:-PATTERN_LOOKBACK] or closes)


def detect_patterns(candles: list[Candle]) -> list[PatternHit]:
    """The arsenal over the last closed bars. Reversal patterns only score
    against an adverse prior trend; continuation stacks score with it."""
    if len(candles) < 25:
        return []
    closes = [c.close for c in candles]
    context = _context(closes)
    a, b, c = candles[-3], candles[-2], candles[-1]
    hits: list[PatternHit] = []

    def add(name: str, direction: int, base: float, needs_trend: int | None) -> None:
        # needs_trend: -1 -> pattern only meaningful after a downtrend,
        # +1 -> after an uptrend, None -> trend-agnostic. Context matching
        # the required prior trend boosts; the opposite context suppresses.
        if needs_trend is not None:
            alignment = context * needs_trend
            gate = max(0.0, min(1.0, 0.5 + alignment))
        else:
            gate = 0.6
        strength = max(0.0, min(1.0, base * gate))
        if strength >= 0.15:
            hits.append(PatternHit(name, direction, round(strength, 3)))

    body_frac = c.body / c.range
    # Single-bar family.
    if body_frac <= DOJI_BODY_FRACTION:
        add("doji", -1 if context > 0 else 1, 0.5, None)
    if body_frac >= MARUBOZU_BODY_FRACTION:
        add("marubozu", 1 if c.bullish else -1, 0.7, None)
    if (c.lower_wick >= WICK_DOMINANCE * c.body and
            c.upper_wick <= 0.5 * c.body and c.body > 0):
        add("hammer", 1, 0.8, needs_trend=-1)
    if (c.upper_wick >= WICK_DOMINANCE * c.body and
            c.lower_wick <= 0.5 * c.body and c.body > 0):
        add("shooting_star", -1, 0.8, needs_trend=1)
    # Two-bar family.
    if (c.bullish and not b.bullish and c.close > b.open and c.open < b.close):
        add("bullish_engulfing", 1, 0.85, needs_trend=-1)
    if (not c.bullish and b.bullish and c.open > b.close and c.close < b.open):
        add("bearish_engulfing", -1, 0.85, needs_trend=1)
    if (b.body > 0 and c.body <= 0.5 * b.body and
            max(c.open, c.close) <= max(b.open, b.close) and
            min(c.open, c.close) >= min(b.open, b.close)):
        add("harami", 1 if not b.bullish else -1, 0.5,
            needs_trend=-1 if not b.bullish else 1)
    wick_tol = 0.15 * c.range
    if abs(c.low - b.low) <= wick_tol and c.bullish and not b.bullish:
        add("tweezer_bottom", 1, 0.6, needs_trend=-1)
    if abs(c.high - b.high) <= wick_tol and not c.bullish and b.bullish:
        add("tweezer_top", -1, 0.6, needs_trend=1)
    # Three-bar family.
    if (not a.bullish and abs(b.body) <= 0.4 * a.body and
            c.bullish and c.close > (a.open + a.close) / 2.0):
        add("morning_star", 1, 0.9, needs_trend=-1)
    if (a.bullish and abs(b.body) <= 0.4 * a.body and
            not c.bullish and c.close < (a.open + a.close) / 2.0):
        add("evening_star", -1, 0.9, needs_trend=1)
    if all(x.bullish and x.body >= 0.5 * x.range for x in (a, b, c)) and \
            c.close > b.close > a.close:
        add("three_white_soldiers", 1, 0.8, None)
    if all((not x.bullish) and x.body >= 0.5 * x.range for x in (a, b, c)) and \
            c.close < b.close < a.close:
        add("three_black_crows", -1, 0.8, None)
    return hits


# ---------------------------------------------------------------------------
# Divergences (regular + hidden), swing-anchored
# ---------------------------------------------------------------------------


def detect_divergences(
    candles: list[Candle],
    periods: int = 14,
    oscillator: list[float] | None = None,
) -> list[DivergenceHit]:
    """Swing-anchored regular + hidden divergences.

    ``oscillator`` (aligned to the TAIL of the close series) defaults to
    Wilder RSI; injectable so other oscillators (MACD histogram) and tests
    can drive the classifier directly.
    """
    closes = [c.close for c in candles]
    rsi = oscillator if oscillator is not None else rsi_series(closes, periods)
    if len(rsi) < 10 or len(rsi) > len(closes):
        return []
    offset = len(closes) - len(rsi)
    swings = [
        (index, price, kind) for index, price, kind in swing_points(closes)
        if index >= offset
    ]
    highs = [(i, p) for i, p, k in swings if k == "high"][-2:]
    lows = [(i, p) for i, p, k in swings if k == "low"][-2:]
    hits: list[DivergenceHit] = []

    def osc(index: int) -> float:
        return rsi[index - offset]

    if len(highs) == 2:
        (i1, p1), (i2, p2) = highs
        gap = osc(i1) - osc(i2)
        if p2 > p1 and gap >= DIVERGENCE_MIN_GAP:
            hits.append(DivergenceHit(
                "regular_bearish", -1, min(1.0, gap / 15.0)))
        elif p2 < p1 and -gap >= DIVERGENCE_MIN_GAP:
            hits.append(DivergenceHit(
                "hidden_bearish", -1, min(1.0, -gap / 15.0)))
    if len(lows) == 2:
        (i1, p1), (i2, p2) = lows
        gap = osc(i2) - osc(i1)
        if p2 < p1 and gap >= DIVERGENCE_MIN_GAP:
            hits.append(DivergenceHit(
                "regular_bullish", 1, min(1.0, gap / 15.0)))
        elif p2 > p1 and -gap >= DIVERGENCE_MIN_GAP:
            hits.append(DivergenceHit(
                "hidden_bullish", 1, min(1.0, -gap / 15.0)))
    return hits


# ---------------------------------------------------------------------------
# Per-timeframe view + the cross-examination
# ---------------------------------------------------------------------------


def timeframe_view(timeframe: str, candles: list[Candle]) -> TimeframeView | None:
    if len(candles) < 25:
        return None
    closes = [c.close for c in candles]
    channel = trend_channel(closes)
    rsi = rsi_series(closes)
    return TimeframeView(
        timeframe=timeframe,
        trend=round(trend_score(closes), 4),
        channel_position=(round(channel.position, 4) if channel else None),
        patterns=tuple(detect_patterns(candles)),
        divergences=tuple(detect_divergences(candles)),
        rsi=(round(rsi[-1], 2) if rsi else None),
        bars=len(candles),
    )


def build_views(state: dict[str, Any]) -> dict[str, TimeframeView]:
    minute = candles_from_state(state, "minute")
    five_minute = candles_from_state(state, "five_minute")
    streams = {
        # A native 5m public stream supplies enough history for a 15m view.
        # Fall back to 1m for injected/legacy states.
        "minute": minute,
        "five_minute": five_minute or aggregate_candles(minute, 5),
        "hourly": candles_from_state(state, "hourly"),
        "daily": candles_from_state(state, "daily"),
    }
    views: dict[str, TimeframeView] = {}
    for name, stream, factor, _weight in TIMEFRAMES:
        source = streams[stream]
        if stream == "minute" and name in {"5m", "15m"}:
            source = streams["five_minute"]
            factor = 1 if name == "5m" else 3
        candles = aggregate_candles(source, factor)
        view = timeframe_view(name, candles)
        if view is not None:
            views[name] = view
    return views


def cross_examine(views: dict[str, TimeframeView]) -> CrossExam:
    """Blend the ladder into one directional conviction, with vetoes.

    Per timeframe: trend + pattern evidence + divergence evidence. A
    REGULAR divergence AGAINST that timeframe's trend is a veto (cuts the
    vote toward zero); a HIDDEN divergence WITH the trend boosts it.
    Timeframe votes combine by ladder weight; conviction reflects
    agreement, and disagreements between adjacent rungs are named.
    """
    votes: dict[str, float] = {}
    boosts: list[str] = []
    vetoes: list[str] = []
    weight_by_name = {name: weight for name, _s, _f, weight in TIMEFRAMES}
    for name, view in views.items():
        vote = view.trend
        for pattern in view.patterns:
            vote += 0.25 * pattern.direction * pattern.strength
        for divergence in view.divergences:
            regular = divergence.kind.startswith("regular")
            with_trend = divergence.direction * view.trend > 0
            if regular and not with_trend and abs(view.trend) > 0.15:
                vote *= max(0.0, 1.0 - 0.6 * divergence.strength)
                vetoes.append(f"{name}:{divergence.kind}")
            elif not regular and with_trend:
                vote += 0.20 * divergence.direction * divergence.strength
                boosts.append(f"{name}:{divergence.kind}")
            else:
                vote += 0.10 * divergence.direction * divergence.strength
        votes[name] = max(-1.0, min(1.0, vote))

    total_weight = sum(weight_by_name[name] for name in votes) or 1.0
    score = sum(weight_by_name[name] * vote for name, vote in votes.items()) / total_weight

    disagreements: list[str] = []
    ordered = [name for name, *_ in TIMEFRAMES if name in votes]
    for lower, higher in zip(ordered, ordered[1:]):
        if votes[lower] * votes[higher] < -0.04:
            disagreements.append(f"{lower}({votes[lower]:+.2f})≠{higher}({votes[higher]:+.2f})")

    if votes:
        aligned = sum(
            weight_by_name[name] for name, vote in votes.items()
            if vote * score > 0
        ) / total_weight
        conviction = abs(score) * aligned
    else:
        conviction = 0.0
    return CrossExam(
        score=round(max(-1.0, min(1.0, score)), 4),
        conviction=round(max(0.0, min(1.0, conviction)), 4),
        votes={name: round(vote, 4) for name, vote in votes.items()},
        boosts=tuple(boosts),
        vetoes=tuple(vetoes),
        disagreements=tuple(disagreements),
    )
