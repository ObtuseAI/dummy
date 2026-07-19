"""Wave-49: the daily runtime-telemetry rotation. The load-bearing property is
*restraint* -- it must bound logs and the two verified tail-only tapes while
never touching organism state, open positions, the audit trail, or the CLV
order-book tape. These tests pin that boundary.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "run_dummy_log_rotation", ROOT / "scripts" / "run_dummy_log_rotation.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["run_dummy_log_rotation"] = mod
spec.loader.exec_module(mod)


def _cfg(**over):
    base = dict(
        log_keep_bytes=4 * 1024,
        log_max_bytes=16 * 1024,
        jsonl_keep_lines=100,
        jsonl_max_lines=150,
        book_tape_keep_days=None,
    )
    base.update(over)
    return mod.Config(**base)


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


# --- logs -------------------------------------------------------------------

def test_oversized_log_truncated_to_tail(tmp_path):
    rd = tmp_path
    log = rd / "daemon_stdout.log"
    lines = [f"line {i:06d} " + "x" * 80 for i in range(2000)]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = log.stat().st_size
    assert before > 16 * 1024

    results = mod.run_rotation(rd, _cfg(), NOW)

    after = log.stat().st_size
    assert after < before
    assert after <= 4 * 1024 + 200          # ~keep_bytes, allow snap slack
    text = log.read_text(encoding="utf-8")
    assert text.startswith("line ")          # snapped to a whole first line
    assert text.rstrip().endswith("x" * 80)   # newest line preserved
    assert "line 001999" in text
    r = next(x for x in results if x.name == "daemon_stdout.log")
    assert r.action == "rotated"


def test_small_log_untouched(tmp_path):
    rd = tmp_path
    log = rd / "healer_stdout.log"
    log.write_bytes(b"tiny\n" * 10)
    original = log.read_bytes()

    mod.run_rotation(rd, _cfg(), NOW)

    assert log.read_bytes() == original


def test_self_log_never_touched(tmp_path):
    rd = tmp_path
    selflog = rd / mod.SELF_LOG
    selflog.write_text("z\n" * 100_000, encoding="utf-8")   # huge, > max
    original = selflog.read_bytes()

    results = mod.run_rotation(rd, _cfg(), NOW)

    assert selflog.read_bytes() == original                 # skipped by name
    assert all(r.name != mod.SELF_LOG for r in results)


# --- tapes ------------------------------------------------------------------

def test_tape_line_capped_and_parse_safe(tmp_path):
    rd = tmp_path
    tape = rd / "cycles.jsonl"
    rows = [json.dumps({"i": i, "status": "CYCLE_OK"}) for i in range(500)]
    tape.write_text("\n".join(rows) + "\n", encoding="utf-8")

    mod.run_rotation(rd, _cfg(), NOW)

    kept = tape.read_text(encoding="utf-8").strip().splitlines()
    assert len(kept) == 100                                  # keep_lines
    parsed = [json.loads(x) for x in kept]                   # every line valid
    assert parsed[-1]["i"] == 499                            # newest preserved
    assert parsed[0]["i"] == 400                             # exactly the tail


def test_tape_under_threshold_untouched(tmp_path):
    rd = tmp_path
    tape = rd / "live_events.jsonl"
    rows = [json.dumps({"i": i}) for i in range(120)]        # < max_lines 150
    tape.write_text("\n".join(rows) + "\n", encoding="utf-8")
    original = tape.read_bytes()

    mod.run_rotation(rd, _cfg(), NOW)

    assert tape.read_bytes() == original


# --- the restraint boundary: state/audit files are never touched ------------

def test_state_and_audit_files_never_touched(tmp_path):
    rd = tmp_path
    # Every one of these is state or an audit trail, NOT disposable telemetry.
    state = {
        "vnext_pending.jsonl": [{"episode": i} for i in range(5000)],
        "vnext_episodes.jsonl": [{"episode": i} for i in range(5000)],
        "paper_entries.jsonl": [{"entry": i} for i in range(5000)],
        "promotion_ledger.jsonl": [{"promotion": i} for i in range(5000)],
        "preregistrations.jsonl": [{"prereg": i} for i in range(5000)],
        "use_outcomes.jsonl": [{"outcome": i} for i in range(5000)],
        "sports_evolution_history.jsonl": [{"gen": i} for i in range(5000)],
        "alerts.jsonl": [{"alert": i} for i in range(5000)],
    }
    originals = {}
    for name, rows in state.items():
        p = rd / name
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        originals[name] = p.read_bytes()

    results = mod.run_rotation(rd, _cfg(), NOW)   # book_tape disarmed

    for name, original in originals.items():
        assert (rd / name).read_bytes() == original, f"{name} was modified!"
    # None of them appear as a rotated result.
    assert all(r.name not in state or r.action == "ok" for r in results)


def test_book_tape_untouched_when_disarmed(tmp_path):
    rd = tmp_path
    book = rd / "book_tape.jsonl"
    old = (NOW - timedelta(days=400)).isoformat()
    rows = [{"ts": old, "ticker": f"T{i}", "kalshi_mid": 0.5} for i in range(5000)]
    book.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    original = book.read_bytes()

    mod.run_rotation(rd, _cfg(book_tape_keep_days=None), NOW)  # disarmed

    assert book.read_bytes() == original


# --- book_tape armed --------------------------------------------------------

def test_book_tape_age_bound_when_armed(tmp_path):
    rd = tmp_path
    book = rd / "book_tape.jsonl"
    recent = (NOW - timedelta(days=5)).isoformat()
    old = (NOW - timedelta(days=60)).isoformat()
    rows = (
        [{"ts": recent, "ticker": "NEW"} for _ in range(50)]
        + [{"ts": old, "ticker": "OLD"} for _ in range(50)]
        + [{"ticker": "NO_TS"} for _ in range(10)]           # missing ts -> keep
        + [{"ts": "not-a-date", "ticker": "BAD_TS"}]          # unparseable -> keep
    )
    book.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    mod.run_rotation(rd, _cfg(book_tape_keep_days=30.0), NOW)

    kept = [json.loads(x) for x in book.read_text().strip().splitlines()]
    tickers = [r.get("ticker") for r in kept]
    assert tickers.count("NEW") == 50
    assert tickers.count("OLD") == 0                          # aged out
    assert tickers.count("NO_TS") == 10                       # kept (fail-safe)
    assert tickers.count("BAD_TS") == 1                       # kept (fail-safe)


# --- robustness -------------------------------------------------------------

def test_missing_runtime_dir_is_noop(tmp_path):
    results = mod.run_rotation(tmp_path / "does-not-exist", _cfg(), NOW)
    assert results == []


def test_missing_tape_reported_not_fatal(tmp_path):
    rd = tmp_path
    (rd / "some.log").write_bytes(b"ok\n")
    results = mod.run_rotation(rd, _cfg(), NOW)
    tape_results = {r.name: r.action for r in results if r.kind == "tape"}
    assert tape_results["cycles.jsonl"] == "skipped-missing"
    assert tape_results["live_events.jsonl"] == "skipped-missing"


def test_env_clamps_max_to_keep(monkeypatch):
    monkeypatch.setenv("DUMMY_LOG_KEEP_MIB", "8")
    monkeypatch.setenv("DUMMY_LOG_MAX_MIB", "2")   # below keep
    c = mod.config_from_env()
    assert c.log_max_bytes >= c.log_keep_bytes      # clamped
