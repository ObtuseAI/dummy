"""Movement featurizer: reconstruct a game's multi-book line-movement time
series from the Wave-12 odds archive.

The archive (``autonomy.odds_api_budget``) appends every paid Odds API fetch
as ``{ts, key, remaining, payload}`` to a monthly gzip JSONL shard. The
``odds|<sport>|h2h,totals,spreads|us`` fetches each carry a full multi-book
slate snapshot; a shard therefore holds a longitudinal record of how every
book's number moved. This module reads those snapshots back and turns them
into per (event, book, market, side) series.

Two quantities matter, one per market family:

  * moneyline (``h2h``): the de-vigged win probability -- comparable across
    books and over time, so movement lives in probability space.
  * spreads / totals: the POSTED LINE (the point). Different books quote
    different points and a de-vig at 8.5 is not the same event as one at
    9.0, so the honest movement quantity is the point itself; the de-vig
    price-probability at that point rides along as secondary colour.

Pure functions only: ``read_archive_window`` does the I/O, ``movement_series``
is a pure transform over already-loaded snapshots so it is trivially
testable. Only PRE-commence snapshots are used -- once a game starts the book
flips to a live number that is a different regime (verified in the archive).
"""
from __future__ import annotations

import glob
import gzip
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from autonomy.signals.sportsbook import devig_two_way

# The market families the archive carries and their primary movement quantity.
PRIMARY_QUANTITY: dict[str, str] = {
    "h2h": "devig_prob",
    "totals": "point",
    "spreads": "point",
}

# Default look-back for "recent" movement (steam) in hours.
DEFAULT_LOOKBACK_HOURS = 24.0


def _parse_iso(value: Any) -> float | None:
    """ISO-8601 -> epoch seconds (UTC), tolerant of a trailing Z."""
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class Quote:
    """One book's number for one side of one market at one instant."""

    ts: float
    price: int | None            # american odds
    point: float | None          # posted line (spreads/totals); None for h2h
    devig_prob: float | None     # de-vigged P(side) at this book/instant


@dataclass
class SideSeries:
    """The time-ordered quotes for one (event, book, market, side), plus the
    movement features an analyst reads off them."""

    event_id: str
    book: str
    market: str
    side: str
    commence: float | None
    quotes: list[Quote] = field(default_factory=list)

    @property
    def quantity(self) -> str:
        return PRIMARY_QUANTITY.get(self.market, "devig_prob")

    def primary_value(self, quote: Quote) -> float | None:
        """This quote's value in the market's primary quantity (de-vig
        probability for moneyline, the posted point for spreads/totals).
        Public: steam and dispersion read it across books."""
        return quote.point if self.quantity == "point" else quote.devig_prob

    def opener(self) -> float | None:
        for quote in self.quotes:
            value = self.primary_value(quote)
            if value is not None:
                return value
        return None

    def current(self) -> float | None:
        for quote in reversed(self.quotes):
            value = self.primary_value(quote)
            if value is not None:
                return value
        return None

    def total_move(self) -> float | None:
        """Signed opener -> current move in the primary quantity."""
        opener, current = self.opener(), self.current()
        if opener is None or current is None:
            return None
        return current - opener

    def recent_move(self, now: float, window_hours: float) -> float | None:
        """Signed move over the last ``window_hours`` (earliest in-window
        value -> latest)."""
        if self.commence is None or window_hours <= 0.0:
            return None
        cutoff = now - window_hours * 3600.0
        in_window = [
            q
            for q in self.quotes
            if cutoff <= q.ts <= now
            and q.ts < self.commence
            and self.primary_value(q) is not None
        ]
        if len(in_window) < 2:
            return None
        return self.primary_value(in_window[-1]) - self.primary_value(in_window[0])  # type: ignore[operator]

    def velocity(self, now: float, window_hours: float) -> float | None:
        """Primary-quantity change per actual elapsed hour (0 if flat)."""
        if self.commence is None or window_hours <= 0.0:
            return None
        cutoff = now - window_hours * 3600.0
        in_window = [
            q
            for q in self.quotes
            if cutoff <= q.ts <= now
            and q.ts < self.commence
            and self.primary_value(q) is not None
        ]
        if len(in_window) < 2:
            return None
        elapsed_hours = (in_window[-1].ts - in_window[0].ts) / 3600.0
        if elapsed_hours <= 0.0:
            return None
        first = self.primary_value(in_window[0])
        last = self.primary_value(in_window[-1])
        if first is None or last is None:
            return None
        return (last - first) / elapsed_hours

    def total_travel(self) -> float:
        """Sum of absolute step-to-step moves -- distinguishes a line that
        drifted straight from one that whipsawed to the same place."""
        values = [self.primary_value(q) for q in self.quotes if self.primary_value(q) is not None]
        return sum(abs(b - a) for a, b in zip(values, values[1:]))

    def features(self, now: float, window_hours: float = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "book": self.book,
            "market": self.market,
            "side": self.side,
            "quantity": self.quantity,
            "opener": self.opener(),
            "current": self.current(),
            "total_move": self.total_move(),
            "recent_move": self.recent_move(now, window_hours),
            "velocity_per_hour": self.velocity(now, window_hours),
            "total_travel": self.total_travel(),
            "n_snapshots": len(self.quotes),
            "first_seen": self.quotes[0].ts if self.quotes else None,
            "last_seen": self.quotes[-1].ts if self.quotes else None,
        }


def _iter_shard(path: str) -> Iterable[dict[str, Any]]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (ValueError, TypeError):
                    continue
    except OSError:
        return


def read_archive_window(
    archive_dir: str | Path | None,
    *,
    sport_keys: Iterable[str] | None = None,
    now: float | None = None,
    lookback_hours: float = DEFAULT_LOOKBACK_HOURS,
) -> list[tuple[float, dict[str, Any]]]:
    """Read (ts, event) pairs from the game-line archive shards.

    Only ``odds|<sport>|...`` records (the multi-book slate snapshots) are
    read; ``props|`` and ``sports`` records are skipped. Events are kept only
    while still PRE-commence at the snapshot instant. Snapshot time provenance
    fails closed: future rows and rows with a missing or non-pregame commence
    relationship are discarded. Shard read errors yield fewer rows, never an
    exception."""
    directory = Path(
        archive_dir if archive_dir is not None
        else os.environ.get("DUMMY_ODDS_ARCHIVE_DIR")
        or "runtime/autonomy/odds_api_archive"
    )
    reference = now if now is not None else datetime.now(timezone.utc).timestamp()
    cutoff = reference - lookback_hours * 3600.0
    wanted = set(sport_keys) if sport_keys else None

    out: list[tuple[float, dict[str, Any]]] = []
    for shard in sorted(glob.glob(str(directory / "*.jsonl.gz"))):
        for record in _iter_shard(shard):
            key = str(record.get("key", ""))
            if not key.startswith("odds|"):
                continue
            ts = record.get("ts")
            if (
                isinstance(ts, bool)
                or not isinstance(ts, (int, float))
                or ts < cutoff
                or ts > reference
            ):
                continue
            payload = record.get("payload")
            if not isinstance(payload, list):
                continue
            for event in payload:
                if not isinstance(event, dict):
                    continue
                if wanted is not None and str(event.get("sport_key")) not in wanted:
                    continue
                commence = _parse_iso(event.get("commence_time"))
                # Pre-commence snapshots only -- a started game's book is live.
                if commence is None or ts >= commence:
                    continue
                out.append((float(ts), event))
    out.sort(key=lambda pair: pair[0])
    return out


def _devig_for_market(market_key: str, outcomes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map side -> {price, point, devig_prob} for one book's market. Two-way
    only (moneyline home/away, totals Over/Under, spread two sides); anything
    else de-vigs to None."""
    priced = [(str(o.get("name")), o.get("price"), o.get("point")) for o in outcomes]
    priced = [(n, p, pt) for (n, p, pt) in priced if isinstance(p, (int, float))]
    result: dict[str, dict[str, Any]] = {}
    if len(priced) == 2:
        (n0, p0, pt0), (n1, p1, pt1) = priced
        d0 = devig_two_way(int(p0), int(p1))
        d1 = devig_two_way(int(p1), int(p0))
        result[n0] = {"price": int(p0), "point": pt0, "devig_prob": d0}
        result[n1] = {"price": int(p1), "point": pt1, "devig_prob": d1}
    else:
        for (name, price, point) in priced:
            result[name] = {"price": int(price), "point": point, "devig_prob": None}
    return result


def movement_series(
    snapshots: list[tuple[float, dict[str, Any]]],
    *,
    markets: Iterable[str] = ("h2h", "totals", "spreads"),
    now: float | None = None,
) -> dict[tuple[str, str, str, str], SideSeries]:
    """Pure transform: (ts, event) snapshots -> per (event, book, market,
    side) :class:`SideSeries`, quotes time-ordered and de-duplicated by
    instant. The transform independently rechecks the pregame and future-time
    boundaries so bypassing :func:`read_archive_window` cannot introduce
    look-ahead evidence."""
    wanted = set(markets)
    series: dict[tuple[str, str, str, str], SideSeries] = {}
    seen_ts: dict[tuple[str, str, str, str], set[float]] = {}
    reference = now if now is not None else datetime.now(timezone.utc).timestamp()

    ordered = sorted(snapshots, key=lambda pair: pair[0])
    for ts, event in ordered:
        if (
            isinstance(ts, bool)
            or not isinstance(ts, (int, float))
            or ts > reference
        ):
            continue
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        commence = _parse_iso(event.get("commence_time"))
        if commence is None or ts >= commence:
            continue
        for book in event.get("bookmakers", []) or []:
            if not isinstance(book, dict):
                continue
            book_key = str(book.get("key") or "")
            for market in book.get("markets", []) or []:
                if not isinstance(market, dict):
                    continue
                market_key = str(market.get("key") or "")
                if market_key not in wanted:
                    continue
                sides = _devig_for_market(market_key, market.get("outcomes", []) or [])
                for side, quote in sides.items():
                    identity = (event_id, book_key, market_key, side)
                    bucket = series.get(identity)
                    if bucket is None:
                        bucket = SideSeries(event_id, book_key, market_key, side, commence)
                        series[identity] = bucket
                        seen_ts[identity] = set()
                    if ts in seen_ts[identity]:
                        continue
                    seen_ts[identity].add(ts)
                    bucket.quotes.append(
                        Quote(ts=ts, price=quote["price"], point=quote["point"],
                              devig_prob=quote["devig_prob"]))
    for bucket in series.values():
        bucket.quotes.sort(key=lambda q: q.ts)
    return series
