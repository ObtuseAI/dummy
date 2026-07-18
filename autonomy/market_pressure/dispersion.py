"""Book dispersion and soft-line detection.

Across many books the same side has one honest consensus number and, often,
one book lagging it -- a stale or deliberately soft line. That outlier is
where the beatable price lives. This reads the CURRENT per-book value for one
(event, market, side) and reports the trimmed consensus, how tightly the
books agree, and the most off-consensus book with its signed offset.

Fail-closed: fewer than three books -> no read (you cannot call one book of
two the outlier).
"""
from __future__ import annotations

from dataclasses import dataclass

from autonomy.market_pressure.line_movement import SideSeries

DEFAULT_MIN_BOOKS = 3
# An outlier this far off the trimmed consensus is a soft line worth naming:
#   devig_prob -> 2 probability points, point -> half a point of line.
DEFAULT_SOFT_THRESHOLDS: dict[str, float] = {"devig_prob": 0.02, "point": 0.5}


@dataclass(frozen=True)
class DispersionRead:
    has_read: bool
    consensus: float | None            # trimmed mean of the primary quantity
    spread: float | None               # max - min across books
    n_books: int
    outlier_book: str | None
    outlier_offset: float | None       # outlier value - consensus (signed)
    is_soft_outlier: bool = False      # offset beyond threshold AND clearly detached
    quantity: str = "devig_prob"

    def as_dict(self) -> dict:
        return {
            "has_read": self.has_read,
            "consensus": self.consensus,
            "spread": self.spread,
            "n_books": self.n_books,
            "outlier_book": self.outlier_book,
            "outlier_offset": self.outlier_offset,
            "is_soft_outlier": self.is_soft_outlier,
            "quantity": self.quantity,
        }


_NO_READ = DispersionRead(False, None, None, 0, None, None)


def _trimmed_mean(values: list[float]) -> float:
    """Mean after dropping the single lowest and highest (>=4 values), else
    the plain mean."""
    if len(values) >= 4:
        ordered = sorted(values)[1:-1]
    else:
        ordered = values
    return sum(ordered) / len(ordered)


def detect_dispersion(
    book_series: list[SideSeries],
    *,
    min_books: int = DEFAULT_MIN_BOOKS,
    soft_threshold: float | None = None,
) -> DispersionRead:
    """Dispersion across ``book_series`` (all for the same event/market/side),
    using each book's current value in the primary quantity."""
    current = [(s.book, s.current()) for s in book_series]
    priced = [(book, value) for (book, value) in current if value is not None]
    if len(priced) < min_books:
        return _NO_READ

    quantity = book_series[0].quantity
    thr = soft_threshold if soft_threshold is not None else DEFAULT_SOFT_THRESHOLDS.get(quantity, 0.02)

    values = [value for (_book, value) in priced]
    consensus = _trimmed_mean(values)
    spread = max(values) - min(values)

    book, offset = max(
        ((book, value - consensus) for (book, value) in priced),
        key=lambda pair: abs(pair[1]),
    )
    # "Soft" only when the gap is both material AND detached: the outlier's
    # distance is at least twice the next-largest offset (one book off on its
    # own, not the whole board spread wide).
    others = sorted((abs(value - consensus) for (b, value) in priced if b != book), reverse=True)
    detached = (not others) or (abs(offset) >= 2.0 * others[0]) if others else True
    is_soft = abs(offset) >= thr and detached

    return DispersionRead(
        has_read=True,
        consensus=consensus,
        spread=spread,
        n_books=len(priced),
        outlier_book=book,
        outlier_offset=offset,
        is_soft_outlier=is_soft,
        quantity=quantity,
    )
