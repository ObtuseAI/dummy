"""CLV (closing-line-value) grading -- spec section 3.2.

Settlements are slow and noisy feedback: a market can take days or weeks to
settle. The sharp book's *closing line* is the industry-standard truth proxy
and converges roughly 10x faster -- a specialist that consistently beats the
close surfaces promotion evidence long before its settlement-backed record
is dense enough to trust on its own.

CLV IS EVIDENCE FOR REVIEW, NEVER A PROMOTION GATE. Settlement-backed
contested Brier (``autonomy/backtest.py``, already phase/horizon-keyed via
``autonomy.taxonomy.grading_scope`` from WS-15) remains the sole promotion
gate. Nothing in this module writes to the weights table or feeds a gating
decision; it only produces a JSON-able report for human review.

Three focused pieces:
  * Book tape (``append_tape_rows`` / ``load_tape_rows``): one row per
    assessed market per monitor pass, deduped when unchanged from that
    ticker's prior row.
  * Close selection (``select_close``): the tape row nearest ``close_time``
    within ``CLOSE_WINDOW_MINUTES`` IS the close. Nothing within the window
    means no grade -- fail-closed; a stale or missing tape must never
    invent a close.
  * CLV math + aggregation (``grade_entries`` / ``aggregate_clv`` /
    ``build_clv_report``): ``clv_bps`` per graded entry, aggregated per
    ``(specialist, market_type)`` with per-event-cluster means feeding
    ``autonomy.stats.mean_ci95`` -- never per-row CIs. Correlated
    same-event entries (sibling strikes, a locked opportunist candidate
    re-observed pass after pass) would shrink a per-row interval
    dishonestly; this mirrors ``autonomy/strategy_miner.py``'s identical
    cluster rule exactly.

A run with no gradeable entries (cold start, a tape gap, an all-miss
window) produces an empty-but-valid, byte-identical-on-repeat report --
never raises, never partially grades.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomy.stats import mean_ci95
from autonomy.taxonomy import specialist_for

# Close selection window: a tape row must land within this many minutes of
# the market's close_time to stand in as the close print. Outside the
# window there is no reliable close evidence -- fail-closed, no grade.
CLOSE_WINDOW_MINUTES = 30.0

# Tape rotation threshold -- a nice-to-have per the WS-8 brief (simplicity
# and auditability over a full log-rotation scheme). This module does not
# rotate on its own; a caller may check the file size against this constant
# and roll a dated backup if it ever matters in practice.
TAPE_ROTATE_BYTES = 50 * 1024 * 1024


def _parse_ts(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# -- book tape -------------------------------------------------------------------

def _tape_dedup_key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    """Everything except ``ts`` -- the dedup rule is 'unchanged from last row'."""
    return (row.get("book_prob"), row.get("kalshi_mid"), row.get("close_time"))


def load_last_by_ticker(path: Path) -> dict[str, dict[str, Any]]:
    """Build the last-row-per-ticker index from an existing tape file.

    Cheap, one-time read intended for process start; carry the dict this
    returns across passes via ``append_tape_rows``'s return value instead
    of re-reading the whole file every pass.
    """
    last: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return last
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ticker = row.get("ticker")
            if ticker:
                last[ticker] = row
    return last


def append_tape_rows(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    last_by_ticker: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Append book-tape rows, skipping any unchanged from the ticker's last row.

    ``rows`` are ``{ticker, ts, book_prob, kalshi_mid, close_time}`` dicts,
    normally one per market assessed in a monitor pass. Returns the updated
    last-row-per-ticker index so a long-running caller (the ``--loop``
    monitor daemon) can carry it into the next pass without re-reading the
    file; a one-shot invocation just omits ``last_by_ticker`` and this reads
    the file fresh.
    """
    if last_by_ticker is None:
        last_by_ticker = load_last_by_ticker(path)
    to_write: list[dict[str, Any]] = []
    for row in rows:
        ticker = row.get("ticker")
        if not ticker:
            continue
        clean = {
            "ticker": ticker,
            "ts": row.get("ts"),
            "book_prob": row.get("book_prob"),
            "kalshi_mid": row.get("kalshi_mid"),
            "close_time": row.get("close_time"),
        }
        prior = last_by_ticker.get(ticker)
        if prior is not None and _tape_dedup_key(prior) == _tape_dedup_key(clean):
            continue
        to_write.append(clean)
        last_by_ticker[ticker] = clean
    if to_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in to_write:
                handle.write(json.dumps(row, sort_keys=True))
                handle.write("\n")
    return last_by_ticker


def load_tape_rows(path: Path) -> list[dict[str, Any]]:
    """All tape rows in file order; malformed lines are skipped (fail-open on read)."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# -- close selection ---------------------------------------------------------------

def select_close(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The tape row nearest ``close_time`` within ``CLOSE_WINDOW_MINUTES``; else None.

    Fail-closed: a ticker whose tape never landed within the window (thin
    coverage, a monitor gap, a market that closed faster than the sweep
    cadence) grades nothing rather than guessing at a close.
    """
    best: dict[str, Any] | None = None
    best_delta: float | None = None
    for row in rows:
        close_time = _parse_ts(row.get("close_time"))
        ts = _parse_ts(row.get("ts"))
        if close_time is None or ts is None:
            continue
        delta = abs(ts - close_time)
        if delta > CLOSE_WINDOW_MINUTES * 60.0:
            continue
        if best_delta is None or delta < best_delta:
            best, best_delta = row, delta
    return best


# -- CLV math ------------------------------------------------------------------------

def clv_bps(side: str, entry_kalshi_prob: float, close_book_prob: float) -> float:
    """``10_000 * side_sign * (close_book_prob - entry_kalshi_prob)``.

    ``side_sign`` is +1 for YES, -1 for NO -- hand-verified against
    concrete good/bad trades in tests/test_autonomy_clv.py. A YES entry
    wants the close to have moved UP from the entry price (the market
    confirming P(YES) was underpriced); a NO entry wants the close to have
    moved DOWN (P(YES) was overpriced), so NO flips the sign of the raw
    ``close_book_prob - entry_kalshi_prob`` delta:

      YES @ entry 0.30, close 0.45 (price rose, confirming YES) -> +1500 bps
      NO  @ entry 0.70, close 0.55 (price fell, confirming NO)  -> +1500 bps
    """
    sign = 1.0 if str(side).upper() == "YES" else -1.0
    return 10_000.0 * sign * (float(close_book_prob) - float(entry_kalshi_prob))


def _event_cluster(ticker: str) -> str:
    """The ticker's event prefix -- same rule as autonomy/strategy_miner.py."""
    return str(ticker).rsplit("-", 1)[0]


# -- grading + aggregation ------------------------------------------------------------

def grade_entries(
    entries: list[dict[str, Any]],
    tape_by_ticker: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Grade each entry against its ticker's tape close; ungradeable entries drop.

    Fail-closed at every step: an entry missing ``entry_kalshi_prob`` or a
    real YES/NO side is skipped; a ticker with no close within the window
    (``select_close`` returns None) is skipped; a close row with no
    ``book_prob`` is skipped. Nothing here ever grades on a guess.
    """
    graded: list[dict[str, Any]] = []
    for entry in entries:
        ticker = entry.get("ticker")
        side = entry.get("side")
        entry_prob = entry.get("entry_kalshi_prob")
        if not ticker or side not in ("YES", "NO") or entry_prob is None:
            continue
        rows = tape_by_ticker.get(ticker) or []
        close = select_close(rows)
        if close is None:
            continue
        close_book_prob = close.get("book_prob")
        if close_book_prob is None:
            continue
        try:
            entry_prob = float(entry_prob)
            close_book_prob = float(close_book_prob)
        except (TypeError, ValueError):
            continue  # malformed persisted row -- skip, never crash a nightly pass
        bps = clv_bps(side, entry_prob, close_book_prob)
        source = str(entry.get("source") or "")
        graded.append({
            "ticker": ticker,
            "side": side,
            "source": source,
            "specialist": specialist_for(source),
            "market_type": entry.get("market_type") or "na",
            "entry_kalshi_prob": round(float(entry_prob), 6),
            "close_book_prob": round(float(close_book_prob), 6),
            "clv_bps": round(bps, 3),
            "event_cluster": _event_cluster(ticker),
        })
    return graded


def aggregate_clv(graded: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-(specialist, market_type) CLV aggregation with per-event-cluster CIs.

    Never a per-row CI: correlated same-event entries (sibling strikes, a
    locked opportunist candidate re-observed pass after pass) would shrink
    the interval dishonestly. Mirrors autonomy/strategy_miner.py's cluster
    rule exactly -- one mean clv_bps per event cluster feeds
    autonomy.stats.mean_ci95, never the raw per-entry values.

    EVIDENCE ONLY -- see module docstring. This never feeds a promotion
    decision; settlement-backed contested Brier (autonomy/backtest.py)
    remains the sole gate.
    """
    groups: dict[tuple[str, str], dict[str, list[float]]] = {}
    for row in graded:
        key = (row["specialist"], row["market_type"])
        clusters = groups.setdefault(key, {})
        clusters.setdefault(row["event_cluster"], []).append(row["clv_bps"])

    scopes: dict[str, Any] = {}
    for (specialist, market_type), clusters in groups.items():
        cluster_means = [sum(values) / len(values) for values in clusters.values()]
        stats = mean_ci95(cluster_means) or {}
        n_entries = sum(len(values) for values in clusters.values())
        scopes[f"{specialist}|{market_type}"] = {
            "specialist": specialist,
            "market_type": market_type,
            "n_entries": n_entries,
            "n_event_clusters": len(clusters),
            "clv_bps_mean": stats.get("mean"),
            "clv_bps_ci95_lower": stats.get("lower"),
            "clv_bps_ci95_upper": stats.get("upper"),
        }
    return {
        "scopes": scopes,
        "graded_entries": len(graded),
        "graded_event_clusters": len({row["event_cluster"] for row in graded}),
        "note": (
            "CLV is evidence for review, not a promotion gate -- "
            "settlement-backed contested Brier (autonomy/backtest.py) "
            "remains the sole promotion gate. Aggregation uses "
            "per-event-cluster means, never per-row CIs (correlated "
            "same-event entries would shrink the interval dishonestly)."
        ),
    }


def build_clv_report(
    entries: list[dict[str, Any]],
    tape_rows: list[dict[str, Any]],
    *,
    now_iso: str,
) -> dict[str, Any]:
    """One full grading pass: entries x tape -> the CLV report artifact.

    A run with no gradeable entries returns an empty-but-valid report --
    idempotent (byte-identical downstream) on a repeat run with unchanged
    inputs, never raises, never partially grades.
    """
    tape_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in tape_rows:
        ticker = row.get("ticker")
        if ticker:
            tape_by_ticker.setdefault(ticker, []).append(row)
    graded = grade_entries(entries, tape_by_ticker)
    aggregated = aggregate_clv(graded)
    return {
        "report_name": "AUTONOMY_CLV",
        "generated_at": now_iso,
        "entries_considered": len(entries),
        **aggregated,
    }
