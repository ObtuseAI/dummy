"""CLV (closing-line-value) grading -- WS-8, spec section 3.2.

CLV is evidence for review, never a promotion gate (settlement-backed
contested Brier in autonomy/backtest.py stays the sole gate -- see that
module's ``sources_by_scope``, already phase/horizon-keyed via
autonomy.taxonomy.grading_scope from WS-15).

Zero network: everything here is synthesized in-memory or in tmp_path.
"""
from __future__ import annotations

import json

import pytest

from autonomy.clv import (
    CLOSE_WINDOW_MINUTES,
    aggregate_clv,
    append_tape_rows,
    build_clv_report,
    clv_bps,
    grade_entries,
    load_tape_rows,
    select_close,
)


# -- tape dedup ----------------------------------------------------------------

def test_append_tape_rows_writes_new_rows(tmp_path):
    path = tmp_path / "book_tape.jsonl"
    rows = [
        {"ticker": "A", "ts": "2026-07-12T00:00:00+00:00", "book_prob": 0.40,
         "kalshi_mid": 0.38, "close_time": "2026-07-12T04:00:00+00:00"},
        {"ticker": "B", "ts": "2026-07-12T00:00:00+00:00", "book_prob": 0.60,
         "kalshi_mid": 0.55, "close_time": "2026-07-12T04:00:00+00:00"},
    ]
    append_tape_rows(path, rows)
    written = load_tape_rows(path)
    assert len(written) == 2
    assert {r["ticker"] for r in written} == {"A", "B"}


def test_append_tape_rows_skips_when_unchanged_from_last_row_for_ticker(tmp_path):
    path = tmp_path / "book_tape.jsonl"
    row1 = {"ticker": "A", "ts": "2026-07-12T00:00:00+00:00", "book_prob": 0.40,
            "kalshi_mid": 0.38, "close_time": "2026-07-12T04:00:00+00:00"}
    # Same ticker, same book_prob/kalshi_mid/close_time, only ts differs.
    row2 = {"ticker": "A", "ts": "2026-07-12T00:01:30+00:00", "book_prob": 0.40,
            "kalshi_mid": 0.38, "close_time": "2026-07-12T04:00:00+00:00"}
    append_tape_rows(path, [row1])
    append_tape_rows(path, [row2])
    written = load_tape_rows(path)
    assert len(written) == 1  # row2 deduped -- unchanged from row1
    assert written[0]["ts"] == "2026-07-12T00:00:00+00:00"


def test_append_tape_rows_writes_when_book_prob_actually_moves(tmp_path):
    path = tmp_path / "book_tape.jsonl"
    row1 = {"ticker": "A", "ts": "2026-07-12T00:00:00+00:00", "book_prob": 0.40,
            "kalshi_mid": 0.38, "close_time": "2026-07-12T04:00:00+00:00"}
    row2 = {"ticker": "A", "ts": "2026-07-12T00:01:30+00:00", "book_prob": 0.45,
            "kalshi_mid": 0.38, "close_time": "2026-07-12T04:00:00+00:00"}
    append_tape_rows(path, [row1])
    append_tape_rows(path, [row2])
    written = load_tape_rows(path)
    assert len(written) == 2


def test_append_tape_rows_dedups_per_ticker_independently(tmp_path):
    path = tmp_path / "book_tape.jsonl"
    a1 = {"ticker": "A", "ts": "t0", "book_prob": 0.40, "kalshi_mid": 0.38, "close_time": "c"}
    b1 = {"ticker": "B", "ts": "t0", "book_prob": 0.60, "kalshi_mid": 0.55, "close_time": "c"}
    a2 = {"ticker": "A", "ts": "t1", "book_prob": 0.40, "kalshi_mid": 0.38, "close_time": "c"}  # dup
    b2 = {"ticker": "B", "ts": "t1", "book_prob": 0.62, "kalshi_mid": 0.55, "close_time": "c"}  # changed
    last = append_tape_rows(path, [a1, b1])
    append_tape_rows(path, [a2, b2], last_by_ticker=last)
    written = load_tape_rows(path)
    assert len(written) == 3  # a2 skipped, b2 kept


def test_append_tape_rows_returns_index_usable_across_calls_without_reread(tmp_path):
    path = tmp_path / "book_tape.jsonl"
    row1 = {"ticker": "A", "ts": "t0", "book_prob": 0.40, "kalshi_mid": 0.38, "close_time": "c"}
    last = append_tape_rows(path, [row1])
    assert "A" in last
    # Passing the returned index back in avoids re-reading the file; the dup
    # is still caught.
    append_tape_rows(path, [row1], last_by_ticker=last)
    assert len(load_tape_rows(path)) == 1


# -- close selection: nearest within window, else fail-closed ------------------

def test_select_close_picks_row_nearest_close_time_within_window():
    close_time = "2026-07-12T04:00:00+00:00"
    rows = [
        {"ticker": "A", "ts": "2026-07-12T03:20:00+00:00", "book_prob": 0.30,
         "kalshi_mid": 0.29, "close_time": close_time},
        {"ticker": "A", "ts": "2026-07-12T03:55:00+00:00", "book_prob": 0.45,
         "kalshi_mid": 0.44, "close_time": close_time},  # 5 min from close -- nearest
        {"ticker": "A", "ts": "2026-07-12T04:25:00+00:00", "book_prob": 0.50,
         "kalshi_mid": 0.49, "close_time": close_time},  # 25 min from close
    ]
    close = select_close(rows)
    assert close is not None
    assert close["book_prob"] == 0.45


def test_select_close_returns_none_when_nothing_within_thirty_minutes():
    close_time = "2026-07-12T04:00:00+00:00"
    rows = [
        {"ticker": "A", "ts": "2026-07-12T02:00:00+00:00", "book_prob": 0.30,
         "kalshi_mid": 0.29, "close_time": close_time},  # 2 hours out
    ]
    assert select_close(rows) is None


def test_select_close_boundary_at_exactly_thirty_minutes_counts():
    assert CLOSE_WINDOW_MINUTES == 30.0
    close_time = "2026-07-12T04:00:00+00:00"
    rows = [
        {"ticker": "A", "ts": "2026-07-12T03:30:00+00:00", "book_prob": 0.30,
         "kalshi_mid": 0.29, "close_time": close_time},  # exactly 30 min
    ]
    close = select_close(rows)
    assert close is not None
    assert close["book_prob"] == 0.30


def test_select_close_returns_none_for_empty_or_malformed_rows():
    assert select_close([]) is None
    assert select_close([{"ticker": "A", "ts": None, "book_prob": 0.4,
                           "kalshi_mid": 0.4, "close_time": "2026-07-12T04:00:00+00:00"}]) is None
    assert select_close([{"ticker": "A", "ts": "2026-07-12T03:55:00+00:00",
                           "book_prob": 0.4, "kalshi_mid": 0.4,
                           "close_time": None}]) is None


# -- CLV sign: hand-verified for YES vs NO --------------------------------------

def test_clv_bps_positive_for_yes_when_close_confirms_the_bet():
    # Entered YES cheap at 0.30; close (true prob) rose to 0.45 -- good trade.
    bps = clv_bps("YES", entry_kalshi_prob=0.30, close_book_prob=0.45)
    assert bps == pytest.approx(1500.0)


def test_clv_bps_negative_for_yes_when_close_moves_against_the_bet():
    bps = clv_bps("YES", entry_kalshi_prob=0.30, close_book_prob=0.20)
    assert bps == pytest.approx(-1000.0)


def test_clv_bps_positive_for_no_when_close_confirms_the_bet():
    # Entered NO when kalshi implied 0.70 YES; close (true prob) fell to
    # 0.55 -- the market moved toward NO, confirming the bet -- good trade,
    # so clv_bps must be POSITIVE even though (close - entry) is negative.
    bps = clv_bps("NO", entry_kalshi_prob=0.70, close_book_prob=0.55)
    assert bps == pytest.approx(1500.0)


def test_clv_bps_negative_for_no_when_close_moves_against_the_bet():
    # Entered NO at 0.70 implied YES; close rose to 0.85 -- bad trade.
    bps = clv_bps("NO", entry_kalshi_prob=0.70, close_book_prob=0.85)
    assert bps == pytest.approx(-1500.0)


def test_clv_bps_zero_when_close_equals_entry():
    assert clv_bps("YES", 0.5, 0.5) == pytest.approx(0.0)
    assert clv_bps("NO", 0.5, 0.5) == pytest.approx(0.0)


# -- grade_entries: fail-closed on missing close / missing book_prob -----------

def _tape(ticker, book_prob, kalshi_mid, ts, close_time):
    return {"ticker": ticker, "ts": ts, "book_prob": book_prob,
            "kalshi_mid": kalshi_mid, "close_time": close_time}


def test_grade_entries_grades_when_a_close_is_found():
    entries = [{"ticker": "KXMLBGAME-26JUL10HOU-HOU", "side": "YES",
                "entry_kalshi_prob": 0.30, "source": "mlb", "market_type": "winner"}]
    tape = {
        "KXMLBGAME-26JUL10HOU-HOU": [
            _tape("KXMLBGAME-26JUL10HOU-HOU", 0.45, 0.44,
                  "2026-07-12T03:55:00+00:00", "2026-07-12T04:00:00+00:00"),
        ],
    }
    graded = grade_entries(entries, tape)
    assert len(graded) == 1
    assert graded[0]["clv_bps"] == 1500.0
    assert graded[0]["specialist"] == "mlb"


def test_grade_entries_skips_when_no_close_within_window():
    entries = [{"ticker": "A", "side": "YES", "entry_kalshi_prob": 0.30,
                "source": "mlb", "market_type": "winner"}]
    tape = {"A": [_tape("A", 0.45, 0.44, "2026-07-12T00:00:00+00:00",
                         "2026-07-12T04:00:00+00:00")]}  # 4 hours out
    assert grade_entries(entries, tape) == []


def test_grade_entries_skips_when_ticker_has_no_tape_at_all():
    entries = [{"ticker": "NOPE", "side": "YES", "entry_kalshi_prob": 0.30,
                "source": "mlb", "market_type": "winner"}]
    assert grade_entries(entries, {}) == []


def test_grade_entries_skips_when_close_row_has_no_book_prob():
    entries = [{"ticker": "A", "side": "YES", "entry_kalshi_prob": 0.30,
                "source": "mlb", "market_type": "winner"}]
    tape = {"A": [_tape("A", None, 0.44, "2026-07-12T03:55:00+00:00",
                         "2026-07-12T04:00:00+00:00")]}
    assert grade_entries(entries, tape) == []


def test_grade_entries_skips_malformed_numeric_fields_without_crashing():
    entries = [
        {"ticker": "A", "side": "YES", "entry_kalshi_prob": "not-a-number",
         "source": "mlb", "market_type": "winner"},
        {"ticker": "A", "side": "YES", "entry_kalshi_prob": 0.30,
         "source": "mlb", "market_type": "winner"},  # this one grades fine
    ]
    tape = {"A": [_tape("A", 0.45, 0.44, "2026-07-12T03:55:00+00:00",
                         "2026-07-12T04:00:00+00:00")]}
    graded = grade_entries(entries, tape)
    assert len(graded) == 1
    assert graded[0]["clv_bps"] == 1500.0


def test_grade_entries_skips_entry_missing_entry_kalshi_prob():
    entries = [{"ticker": "A", "side": "YES", "entry_kalshi_prob": None,
                "source": "mlb", "market_type": "winner"}]
    tape = {"A": [_tape("A", 0.45, 0.44, "2026-07-12T03:55:00+00:00",
                         "2026-07-12T04:00:00+00:00")]}
    assert grade_entries(entries, tape) == []


# -- aggregation: per-event-cluster CIs, never per-row --------------------------

def _entry(ticker, source, market_type, side="YES", prob=0.30):
    return {"ticker": ticker, "side": side, "entry_kalshi_prob": prob,
            "source": source, "market_type": market_type}


def test_aggregate_clv_uses_cluster_means_not_per_row():
    # Two events (event clusters), 3 correlated entries in event A, 1 in
    # event B. A per-row CI would treat this as n=4 (falsely narrow); the
    # honest CI is computed over 2 cluster means (n=2).
    entries = [
        _entry("KXMLBGAME-26JUL10HOU-HOU", "mlb", "winner", prob=0.30),
        _entry("KXMLBGAME-26JUL10HOU-AWY", "mlb", "winner", prob=0.30),  # same event cluster
        _entry("KXMLBGAME-26JUL10HOU-XYZ", "mlb", "winner", prob=0.30),  # same event cluster
        _entry("KXMLBGAME-26JUL11SEA-SEA", "mlb", "winner", prob=0.30),  # different event
    ]
    tape = {
        e["ticker"]: [_tape(e["ticker"], 0.45, 0.44, "2026-07-12T03:55:00+00:00",
                             "2026-07-12T04:00:00+00:00")]
        for e in entries
    }
    graded = grade_entries(entries, tape)
    assert len(graded) == 4  # all four entries graded...
    aggregated = aggregate_clv(graded)
    scope = aggregated["scopes"]["mlb|winner"]
    assert scope["n_entries"] == 4
    assert scope["n_event_clusters"] == 2  # ...but only 2 independent clusters
    assert scope["clv_bps_mean"] == 1500.0  # every graded row is identical


def test_aggregate_clv_separates_by_specialist_and_market_type():
    entries = [
        _entry("KXMLBGAME-26JUL10HOU-HOU", "mlb", "winner", prob=0.30),
        _entry("KXMLBSPREAD-26JUL10HOU-HOU2", "mlb", "spread", prob=0.30),
        _entry("KXBTCD-26JUL10-T71000", "crypto", "ladder", prob=0.30),
    ]
    tape = {
        e["ticker"]: [_tape(e["ticker"], 0.45, 0.44, "2026-07-12T03:55:00+00:00",
                             "2026-07-12T04:00:00+00:00")]
        for e in entries
    }
    graded = grade_entries(entries, tape)
    aggregated = aggregate_clv(graded)
    assert set(aggregated["scopes"].keys()) == {"mlb|winner", "mlb|spread", "crypto|ladder"}


def test_aggregate_clv_note_discloses_evidence_only_status():
    aggregated = aggregate_clv([])
    assert aggregated["scopes"] == {}
    assert "not a promotion gate" in aggregated["note"] or "evidence" in aggregated["note"].lower()


# -- build_clv_report: end to end, idempotent on empty input --------------------

def test_build_clv_report_end_to_end():
    entries = [_entry("KXMLBGAME-26JUL10HOU-HOU", "mlb", "winner", side="NO", prob=0.70)]
    tape_rows = [_tape("KXMLBGAME-26JUL10HOU-HOU", 0.55, 0.54,
                        "2026-07-12T03:55:00+00:00", "2026-07-12T04:00:00+00:00")]
    report = build_clv_report(entries, tape_rows, now_iso="2026-07-12T05:00:00+00:00")
    assert report["report_name"] == "AUTONOMY_CLV"
    assert report["entries_considered"] == 1
    assert report["graded_entries"] == 1
    scope = report["scopes"]["mlb|winner"]
    assert scope["clv_bps_mean"] == 1500.0


def test_build_clv_report_empty_input_is_valid_and_idempotent():
    report1 = build_clv_report([], [], now_iso="2026-07-12T05:00:00+00:00")
    report2 = build_clv_report([], [], now_iso="2026-07-12T05:00:00+00:00")
    assert report1 == report2
    assert report1["graded_entries"] == 0
    assert report1["scopes"] == {}


def test_build_clv_report_is_json_serializable():
    entries = [_entry("KXMLBGAME-26JUL10HOU-HOU", "mlb", "winner")]
    tape_rows = [_tape("KXMLBGAME-26JUL10HOU-HOU", 0.45, 0.44,
                        "2026-07-12T03:55:00+00:00", "2026-07-12T04:00:00+00:00")]
    report = build_clv_report(entries, tape_rows, now_iso="2026-07-12T05:00:00+00:00")
    json.dumps(report)  # must not raise
