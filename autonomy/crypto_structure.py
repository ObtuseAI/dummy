"""Multi-timeframe market structure: supports, resistances, trend channels.

Operator directive 2026-07-12: crypto should be elite at identifying
support/resistance levels and trend channels across timeframes and playing
the swings when the rest of the technicals confirm the direction.

This module is pure computation over close series the CryptoDataHub already
carries (minute, hourly, 4h/daily aggregates) -- no network, no state, fully
deterministic and unit-testable:

  * ``swing_points``    -- k-bar-confirmed local extrema.
  * ``cluster_levels``  -- extrema clustered into S/R levels; strength =
                           touches weighted by recency.
  * ``trend_channel``   -- regression channel: slope (bps/bar), r-squared,
                           and where price sits inside the residual band.
  * ``structure_state`` -- per-timeframe nearest support/resistance +
                           channel, plus a cross-timeframe alignment score.
  * ``swing_setup``     -- bounded confluence score in [-1, 1] with explicit
                           reasons; nonzero ONLY when structure and at least
                           one actively confirming technical agree, and an
                           adversarial order book vetoes outright.

Everything degrades to "no opinion" on thin data: too few bars means no
swings, no levels, no channel, a zero setup score -- fail-closed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Bars each side that must be lower/higher for an extremum to confirm.
SWING_CONFIRM_BARS = 3
# Price proximity (bps) under which extrema merge into one level.
LEVEL_CLUSTER_BPS = 35.0
# Recency half-life (in bars) for level-touch strength.
LEVEL_RECENCY_HALFLIFE_BARS = 96.0
# A level within this many bps of spot counts as "at structure".
AT_LEVEL_BPS = 60.0
# Minimum bars for any structure computation on a series.
MIN_BARS = 24


@dataclass(frozen=True)
class Level:
    price: float
    kind: str  # "support" | "resistance"
    touches: int
    strength: float  # recency-weighted touch mass, >= 0
    last_touch_age_bars: int


@dataclass(frozen=True)
class Channel:
    slope_bps_per_bar: float
    r_squared: float
    position: float  # -1 (band bottom) .. +1 (band top), clipped
    band_width_bps: float


@dataclass(frozen=True)
class TimeframeStructure:
    timeframe: str
    support: Level | None
    resistance: Level | None
    channel: Channel | None
    spot: float


@dataclass(frozen=True)
class SwingSetup:
    score: float  # -1 .. +1; sign is direction, 0 = no setup
    reasons: list[str] = field(default_factory=list)


def swing_points(closes: list[float], confirm: int = SWING_CONFIRM_BARS) -> list[tuple[int, float, str]]:
    """K-bar-confirmed local extrema as (index, price, 'high'|'low')."""
    n = len(closes)
    if n < 2 * confirm + 1:
        return []
    points: list[tuple[int, float, str]] = []
    for index in range(confirm, n - confirm):
        window_left = closes[index - confirm:index]
        window_right = closes[index + 1:index + 1 + confirm]
        value = closes[index]
        if all(value > w for w in window_left) and all(value >= w for w in window_right):
            points.append((index, value, "high"))
        elif all(value < w for w in window_left) and all(value <= w for w in window_right):
            points.append((index, value, "low"))
    return points


def cluster_levels(
    swings: list[tuple[int, float, str]],
    series_length: int,
    tolerance_bps: float = LEVEL_CLUSTER_BPS,
    halflife_bars: float = LEVEL_RECENCY_HALFLIFE_BARS,
) -> list[Level]:
    """Cluster swing extrema into S/R levels, strongest first.

    A level's kind is decided by its most recent touch: an old ceiling that
    price now sits above has usually flipped into a floor.
    """
    if not swings:
        return []
    ordered = sorted(swings, key=lambda item: item[1])
    clusters: list[list[tuple[int, float, str]]] = []
    for swing in ordered:
        if clusters:
            anchor = clusters[-1][0][1]
            if anchor > 0 and abs(swing[1] - anchor) / anchor * 10_000.0 <= tolerance_bps:
                clusters[-1].append(swing)
                continue
        clusters.append([swing])
    levels: list[Level] = []
    for cluster in clusters:
        strength = 0.0
        for index, _price, _kind in cluster:
            age = max(0, series_length - 1 - index)
            strength += 0.5 ** (age / max(1.0, halflife_bars))
        newest = max(cluster, key=lambda item: item[0])
        price = sum(item[1] for item in cluster) / len(cluster)
        kind = "resistance" if newest[2] == "high" else "support"
        levels.append(Level(
            price=price, kind=kind, touches=len(cluster), strength=strength,
            last_touch_age_bars=max(0, series_length - 1 - newest[0]),
        ))
    levels.sort(key=lambda level: level.strength, reverse=True)
    return levels


def trend_channel(closes: list[float]) -> Channel | None:
    """Least-squares regression channel over the series."""
    n = len(closes)
    if n < MIN_BARS:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(closes) / n
    var_x = sum((index - mean_x) ** 2 for index in range(n))
    if var_x <= 0 or mean_y <= 0:
        return None
    cov = sum((index - mean_x) * (closes[index] - mean_y) for index in range(n))
    slope = cov / var_x
    intercept = mean_y - slope * mean_x
    residuals = [closes[index] - (intercept + slope * index) for index in range(n)]
    ss_res = sum(value ** 2 for value in residuals)
    ss_tot = sum((value - mean_y) ** 2 for value in closes)
    r_squared = 0.0 if ss_tot <= 0 else max(0.0, 1.0 - ss_res / ss_tot)
    resid_std = math.sqrt(ss_res / n) if n else 0.0
    fitted_last = intercept + slope * (n - 1)
    if resid_std > 0:
        position = (closes[-1] - fitted_last) / (2.0 * resid_std)
    else:
        position = 0.0
    return Channel(
        slope_bps_per_bar=slope / mean_y * 10_000.0,
        r_squared=r_squared,
        position=max(-1.0, min(1.0, position)),
        band_width_bps=4.0 * resid_std / mean_y * 10_000.0,
    )


def aggregate_closes(closes: list[float], factor: int) -> list[float]:
    """Downsample a close series by taking every ``factor``-th close.

    Aligned from the end so the latest aggregated bar is the latest close.
    """
    if factor <= 1:
        return list(closes)
    out = list(reversed(closes[::-factor]))
    return out


def _nearest_levels(levels: list[Level], spot: float) -> tuple[Level | None, Level | None]:
    supports = [level for level in levels if level.price <= spot]
    resistances = [level for level in levels if level.price > spot]
    support = max(supports, key=lambda level: level.price) if supports else None
    resistance = min(resistances, key=lambda level: level.price) if resistances else None
    return support, resistance


def timeframe_structure(timeframe: str, closes: list[float], spot: float) -> TimeframeStructure | None:
    """Structure snapshot for one timeframe; None when the series is thin."""
    if spot <= 0 or len(closes) < MIN_BARS:
        return None
    swings = swing_points(closes)
    levels = cluster_levels(swings, len(closes))
    support, resistance = _nearest_levels(levels, spot)
    return TimeframeStructure(
        timeframe=timeframe, support=support, resistance=resistance,
        channel=trend_channel(closes), spot=spot,
    )


def structure_state(state: dict[str, Any]) -> dict[str, TimeframeStructure]:
    """Multi-timeframe structure from a CryptoDataHub state dict.

    Timeframes: 1m (minute closes), 1h (hourly closes), 4h (aggregated
    hourly), 1d (daily closes when the hub carries them, else aggregated
    hourly at 24x). Thin series simply drop out of the result.
    """
    spot = float(state.get("spot") or 0.0)
    minute = [float(v) for v in state.get("minute_closes") or []]
    hourly = [float(v) for v in state.get("hourly_closes") or []]
    daily = [float(v) for v in state.get("daily_closes") or []]
    if not daily and hourly:
        daily = aggregate_closes(hourly, 24)
    frames = {
        "1m": minute,
        "1h": hourly,
        "4h": aggregate_closes(hourly, 4),
        "1d": daily,
    }
    result: dict[str, TimeframeStructure] = {}
    for timeframe, closes in frames.items():
        snapshot = timeframe_structure(timeframe, closes, spot)
        if snapshot is not None:
            result[timeframe] = snapshot
    return result


def mtf_alignment(structures: dict[str, TimeframeStructure]) -> float:
    """Cross-timeframe trend agreement in [-1, 1] over 1h/4h/1d channels.

    Each frame votes its channel slope sign weighted by r-squared; a frame
    without a channel abstains. No votes -> 0 (no opinion).
    """
    votes: list[float] = []
    for timeframe in ("1h", "4h", "1d"):
        snapshot = structures.get(timeframe)
        if snapshot is None or snapshot.channel is None:
            continue
        channel = snapshot.channel
        if abs(channel.slope_bps_per_bar) < 0.5:
            votes.append(0.0)
        else:
            votes.append(math.copysign(channel.r_squared, channel.slope_bps_per_bar))
    if not votes:
        return 0.0
    return max(-1.0, min(1.0, sum(votes) / len(votes)))


def _distance_bps(spot: float, price: float) -> float:
    return abs(spot - price) / spot * 10_000.0


def swing_setup(
    structures: dict[str, TimeframeStructure],
    indicators: dict[str, Any] | None = None,
) -> SwingSetup:
    """Bounded confluence score: structure plus confirming technicals.

    Long setup: price at/near strong 1h or 4h support, multi-timeframe trend
    not against it, and the confirming technicals (order-book imbalance,
    volume surge, microprice basis) not contradicting. Symmetric for shorts
    at resistance. Anything ambiguous scores 0 -- the signal layer treats
    that as abstain.
    """
    indicators = indicators or {}
    anchor = structures.get("1h") or structures.get("4h")
    if anchor is None:
        return SwingSetup(0.0, ["no structure"])
    alignment = mtf_alignment(structures)
    reasons: list[str] = []
    direction = 0.0
    level_conviction = 0.0

    support, resistance = anchor.support, anchor.resistance
    at_support = (
        support is not None
        and _distance_bps(anchor.spot, support.price) <= AT_LEVEL_BPS
        and support.touches >= 2
    )
    at_resistance = (
        resistance is not None
        and _distance_bps(anchor.spot, resistance.price) <= AT_LEVEL_BPS
        and resistance.touches >= 2
    )
    if at_support and not at_resistance and alignment >= -0.1:
        direction = 1.0
        level_conviction = min(1.0, support.strength / 3.0)
        reasons.append(
            f"at support {support.price:.0f} (touches={support.touches}, "
            f"strength={support.strength:.2f})")
    elif at_resistance and not at_support and alignment <= 0.1:
        direction = -1.0
        level_conviction = min(1.0, resistance.strength / 3.0)
        reasons.append(
            f"at resistance {resistance.price:.0f} (touches={resistance.touches}, "
            f"strength={resistance.strength:.2f})")
    else:
        return SwingSetup(0.0, ["no actionable level"])

    trend_term = max(0.0, alignment * direction)  # only credit agreement
    if trend_term > 0:
        reasons.append(f"mtf alignment {alignment:+.2f}")

    # Confirming technicals under the canonical _indicator_features keys
    # (top_book_imbalance / microprice_basis_bps / volume_surge_15m) -- the
    # same names _technical_score consumes, so the integrated signal path
    # and these checks can never drift apart again.
    confirm = 0.0
    confirm_max = 0.0
    book_imbalance = indicators.get("top_book_imbalance")
    if book_imbalance is not None:
        confirm_max += 1.0
        value = max(-1.0, min(1.0, float(book_imbalance))) * direction
        if value > 0.05:
            confirm += min(1.0, value * 2.0)
            reasons.append(f"book imbalance {float(book_imbalance):+.2f}")
        elif value < -0.25:
            return SwingSetup(0.0, reasons + ["order book contradicts"])
    microprice = indicators.get("microprice_basis_bps")
    if microprice is not None:
        confirm_max += 1.0
        value = float(microprice) * direction
        if value > 0.5:
            confirm += min(1.0, value / 5.0)
            reasons.append(f"microprice basis {float(microprice):+.1f}bps")
    volume_surge = indicators.get("volume_surge_15m")
    if volume_surge is not None:
        confirm_max += 1.0
        # Volume is non-directional: it AMPLIFIES a directional confirmation
        # (book or microprice) but can never be the sole green light for a
        # direction on its own.
        if float(volume_surge) > 1.5 and confirm > 0:
            confirm += 0.5
            reasons.append(f"volume surge x{float(volume_surge):.1f}")

    # The operator directive is explicit: play the swing when the REST of the
    # technicals support the direction. Structure alone -- however clean --
    # is not a setup; at least one technical must actively confirm.
    if confirm <= 0.0:
        return SwingSetup(0.0, reasons + ["no confirming technicals"])
    confirmation = confirm / confirm_max if confirm_max > 0 else 0.0
    score = direction * min(
        1.0,
        0.45 * level_conviction + 0.35 * trend_term + 0.20 * confirmation,
    )
    return SwingSetup(round(score, 4), reasons)
