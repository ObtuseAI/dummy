"""A blocked trade must say WHY it was blocked.

fresh_best_quote swallowed every exception into a bare ``return None``, which
the executor surfaces as ``taker_no_fresh_book``. Between 2026-07-19 and 07-21
that reason blocked 893 champion decisions -- 1,416 counting
stale_market_snapshot -- and nothing recorded whether the cause was a rate
limit, a timeout, a delisted ticker, or a parse error. The exception was
destroyed at the point of failure, so three days of lost trading had no
attributable cause.

Same silent-swallow class Wave-84 removed from the report writers, still live
in the execution path. The quote must still fail CLOSED; only the diagnosis is
preserved.
"""
from __future__ import annotations

import json

import pytest

from autonomy.live_book import fresh_best_quote, record_book_fetch_failure


def test_fetch_failure_still_fails_closed(tmp_path, monkeypatch):
    """Fail-closed is the safety property and must not change."""
    monkeypatch.setattr(
        "autonomy.live_book.BOOK_FETCH_FAILURES_PATH",
        str(tmp_path / "book_fetch_failures.json"),
    )

    def boom(_ticker):
        raise TimeoutError("read timed out")

    assert fresh_best_quote("KXBTCD-X", fetch_orderbook=boom) is None


def test_failure_kind_is_recorded(tmp_path):
    path = tmp_path / "failures.json"
    record_book_fetch_failure("KXBTCD-X", TimeoutError("read timed out"), path=str(path))
    record_book_fetch_failure("KXBTCD-Y", TimeoutError("read timed out"), path=str(path))
    record_book_fetch_failure("KXETHD-Z", ValueError("bad json"), path=str(path))

    blob = json.loads(path.read_text(encoding="utf-8"))
    assert blob["by_kind"] == {"TimeoutError": 2, "ValueError": 1}
    assert blob["total"] == 3
    # A rate-limit storm must be distinguishable from a parse bug.
    kinds = {row["kind"] for row in blob["recent"]}
    assert kinds == {"TimeoutError", "ValueError"}
    assert blob["recent"][-1]["ticker"] == "KXETHD-Z"


def test_recent_list_is_bounded_but_counts_are_not(tmp_path):
    """A storm must not grow the artifact without bound."""
    path = tmp_path / "failures.json"
    for i in range(120):
        record_book_fetch_failure(f"T{i}", TimeoutError("x"), path=str(path))
    blob = json.loads(path.read_text(encoding="utf-8"))
    assert len(blob["recent"]) == 50
    assert blob["total"] == 120                      # the count is authoritative
    assert blob["by_kind"]["TimeoutError"] == 120


def test_recorder_never_raises(tmp_path):
    """Diagnostics must never be able to break order submission."""
    # Unwritable path: the recorder must swallow its OWN failure.
    record_book_fetch_failure("T", RuntimeError("x"), path=str(tmp_path))
    # Corrupt existing artifact: must recover rather than propagate.
    path = tmp_path / "corrupt.json"
    path.write_text("{not json", encoding="utf-8")
    record_book_fetch_failure("T", RuntimeError("x"), path=str(path))
    assert json.loads(path.read_text(encoding="utf-8"))["total"] == 1


@pytest.mark.parametrize("exc", [
    TimeoutError("timeout"),
    ConnectionError("refused"),
    ValueError("bad json"),
    KeyError("missing"),
])
def test_every_failure_kind_is_attributed_not_collapsed(tmp_path, exc):
    path = tmp_path / "f.json"
    record_book_fetch_failure("KXBTCD-X", exc, path=str(path))
    blob = json.loads(path.read_text(encoding="utf-8"))
    assert type(exc).__name__ in blob["by_kind"]
