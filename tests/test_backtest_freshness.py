"""Backtest summary freshness: stamped artifacts, fail-closed staleness checks.

Regression anchor: the authoritative latest_backtest_summary.json went 6 days
stale in the live runtime with no alarm while promotion machinery kept reading
it. Freshness is now stamped at write time and every check is fail-closed —
missing/unreadable/unstamped evidence IS stale.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.backtest import (
    SUMMARY_STALE_HOURS,
    backtest_summary_freshness,
    summarize_backtest,
    write_latest_backtest_summary,
)

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


def test_write_stamps_generated_at(tmp_path: Path):
    target = tmp_path / "latest_backtest_summary.json"
    write_latest_backtest_summary({"settled_markets": 5}, path=target, now=NOW)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["generated_at"] == NOW.isoformat()
    assert payload["settled_markets"] == 5


def test_fresh_summary_is_not_stale(tmp_path: Path):
    target = tmp_path / "latest_backtest_summary.json"
    write_latest_backtest_summary({}, path=target, now=NOW - timedelta(hours=2))
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is False
    assert abs(verdict["age_hours"] - 2.0) < 0.01
    assert verdict["reason"] is None


def test_summary_older_than_bound_is_stale(tmp_path: Path):
    target = tmp_path / "latest_backtest_summary.json"
    write_latest_backtest_summary(
        {}, path=target, now=NOW - timedelta(hours=SUMMARY_STALE_HOURS + 1),
    )
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is True
    assert verdict["reason"] == "stale"


def test_regression_six_day_old_summary_is_stale(tmp_path: Path):
    # The live artifact was 6 days old (written 07-10, read 07-16).
    target = tmp_path / "latest_backtest_summary.json"
    write_latest_backtest_summary({}, path=target, now=NOW - timedelta(days=6))
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is True
    assert verdict["age_hours"] > 5 * 24


def test_missing_summary_is_stale_fail_closed(tmp_path: Path):
    verdict = backtest_summary_freshness(path=tmp_path / "absent.json", now=NOW)
    assert verdict["is_stale"] is True
    assert verdict["reason"] == "missing"


def test_unreadable_summary_is_stale_fail_closed(tmp_path: Path):
    target = tmp_path / "latest_backtest_summary.json"
    target.write_text("{not json", encoding="utf-8")
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is True
    assert verdict["reason"] == "unreadable"


def test_unstamped_summary_is_stale_fail_closed(tmp_path: Path):
    target = tmp_path / "latest_backtest_summary.json"
    target.write_text(json.dumps({"settled_markets": 3}), encoding="utf-8")
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is True
    assert verdict["reason"] == "unstamped"


def test_bad_timestamp_is_stale_fail_closed(tmp_path: Path):
    target = tmp_path / "latest_backtest_summary.json"
    target.write_text(json.dumps({"generated_at": "not-a-time"}), encoding="utf-8")
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is True
    assert verdict["reason"] == "bad_timestamp"


def test_future_stamp_is_stale_fail_closed(tmp_path: Path):
    # A clock-skewed stamp from the future is not trustworthy evidence either.
    target = tmp_path / "latest_backtest_summary.json"
    write_latest_backtest_summary({}, path=target, now=NOW + timedelta(hours=5))
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is True


def test_legacy_created_at_stamp_is_honored(tmp_path: Path):
    # Pre-guard artifacts carry only created_at; freshness must still grade them.
    target = tmp_path / "latest_backtest_summary.json"
    target.write_text(json.dumps(
        {"created_at": (NOW - timedelta(hours=1)).isoformat()},
    ), encoding="utf-8")
    verdict = backtest_summary_freshness(path=target, now=NOW)
    assert verdict["is_stale"] is False


def test_summarize_backtest_carries_the_evidence_keys():
    report = {
        "report_name": "AUTONOMY_BACKTEST",
        "settled_markets": 7,
        "created_at": NOW.isoformat(),
        "weights_written": True,
        "weights_rejected_reasons": [],
        "sources": {"sharp": {"contested_n": 20}},
        "evidence_split": {"live_settled": 7, "retro_settled": 0},
        "bootstrapped_weights": {"sharp": 1.2},
        "decision_policy": {
            "settled_markets": 7,
            "ensemble_metrics": {"forecast_brier": 0.1},
            "walk_forward_threshold_selection": {
                "aggregate_out_of_sample": {"trades": 100}
            },
        },
    }
    summary = summarize_backtest(report)
    assert summary["report_name"] == "AUTONOMY_BACKTEST"
    assert summary["settled_markets"] == 7
    assert summary["weights_written"] is True
    assert summary["weights_rejected_reasons"] == []
    assert "decision_policy" in summary
    assert summary["sources"] == report["sources"]
    assert summary["evidence_split"] == report["evidence_split"]
    assert summary["bootstrapped_weights"] == {"sharp": 1.2}
    assert summary["decision_policy"]["ensemble_metrics"] == {
        "forecast_brier": 0.1
    }
    assert summary["decision_policy"]["walk_forward_threshold_selection"] == {
        "aggregate_out_of_sample": {"trades": 100}
    }
