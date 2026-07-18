"""Cross-book steam detection.

A single book nudging its number is noise; the same move landing across many
books inside a short window is a coordinated (usually sharp / syndicate)
push -- "steam". This reads a set of per-book :class:`SideSeries` for ONE
(event, market, side) and reports whether the books moved together, how far,
which book moved FIRST (the originator the rest chased), and how tightly the
move was clustered in time.

Fail-closed: fewer than two books with a usable recent move -> no steam.
"""
from __future__ import annotations

from dataclasses import dataclass

from autonomy.market_pressure.line_movement import SideSeries

# Minimum move to count a book as "moved", by primary quantity:
#   devig_prob (moneyline) -> 1.5 probability points
#   point (spreads/totals) -> half a point of line
DEFAULT_THRESHOLDS: dict[str, float] = {"devig_prob": 0.015, "point": 0.5}
DEFAULT_MIN_BOOKS = 3
DEFAULT_WINDOW_HOURS = 6.0


@dataclass(frozen=True)
class SteamRead:
    is_steam: bool
    direction: int                 # +1 up, -1 down, 0 none (in primary quantity)
    magnitude: float               # median signed move of the books that moved
    n_books_moved: int
    n_books_total: int
    originator: str | None         # book that crossed threshold earliest
    followers: tuple[str, ...] = ()
    synchrony_seconds: float | None = None  # spread first->last crossing; tighter = sharper
    quantity: str = "devig_prob"

    def as_dict(self) -> dict:
        return {
            "is_steam": self.is_steam,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "n_books_moved": self.n_books_moved,
            "n_books_total": self.n_books_total,
            "originator": self.originator,
            "followers": list(self.followers),
            "synchrony_seconds": self.synchrony_seconds,
            "quantity": self.quantity,
        }


_NO_STEAM = SteamRead(False, 0, 0.0, 0, 0, None)


def _crossing_ts(series: SideSeries, threshold: float, now: float, window_hours: float) -> float | None:
    """Earliest timestamp at which this book's move FROM the window's first
    in-window value first reached ``threshold`` in magnitude."""
    cutoff = now - window_hours * 3600.0
    values = [(q.ts, series.primary_value(q)) for q in series.quotes
              if q.ts >= cutoff and series.primary_value(q) is not None]
    if len(values) < 2:
        return None
    base = values[0][1]
    for ts, value in values[1:]:
        if abs(value - base) >= threshold:  # type: ignore[operator]
            return ts
    return None


def detect_steam(
    book_series: list[SideSeries],
    *,
    now: float,
    window_hours: float = DEFAULT_WINDOW_HOURS,
    min_books: int = DEFAULT_MIN_BOOKS,
    threshold: float | None = None,
) -> SteamRead:
    """Steam across ``book_series`` (all for the same event/market/side)."""
    usable = [s for s in book_series if s.recent_move(now, window_hours) is not None]
    if len(usable) < 2:
        return _NO_STEAM

    quantity = usable[0].quantity
    thr = threshold if threshold is not None else DEFAULT_THRESHOLDS.get(quantity, 0.015)

    moves = [(s, s.recent_move(now, window_hours)) for s in usable]
    up = [(s, m) for (s, m) in moves if m is not None and m >= thr]
    down = [(s, m) for (s, m) in moves if m is not None and m <= -thr]
    winner, direction = (up, 1) if len(up) >= len(down) else (down, -1)

    if len(winner) < min_books:
        return SteamRead(False, 0, 0.0, len(winner), len(usable), None, quantity=quantity)

    signed = sorted(m for (_s, m) in winner)
    mid = len(signed) // 2
    magnitude = signed[mid] if len(signed) % 2 else (signed[mid - 1] + signed[mid]) / 2.0

    crossings = [(s.book, _crossing_ts(s, thr, now, window_hours)) for (s, _m) in winner]
    timed = sorted([(ts, book) for (book, ts) in crossings if ts is not None])
    originator = timed[0][1] if timed else None
    followers = tuple(book for (_ts, book) in timed[1:]) if len(timed) > 1 else ()
    synchrony = (timed[-1][0] - timed[0][0]) if len(timed) >= 2 else None

    return SteamRead(
        is_steam=True,
        direction=direction,
        magnitude=magnitude,
        n_books_moved=len(winner),
        n_books_total=len(usable),
        originator=originator,
        followers=followers,
        synchrony_seconds=synchrony,
        quantity=quantity,
    )
