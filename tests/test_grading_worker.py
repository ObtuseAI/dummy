from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from autonomy.grading_worker import run_grading_pass
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _signal(source: str, ticker: str, probability: float) -> Signal:
    return Signal(
        source=source,
        market_ticker=ticker,
        probability_yes=probability,
        uncertainty=0.1,
        rationale="test",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _seed(ledger: AutonomyLedger, ticker: str) -> None:
    assert ledger.record_signal(_signal("market_prior", ticker, 0.5))
    assert ledger.record_signal(_signal("worker_challenger", ticker, 0.9))


def _receipt_digest(receipt: dict) -> str:
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    payload = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_worker_derives_series_grades_once_and_writes_atomic_receipt(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXWORKER-26JUL26-YES"
    _seed(ledger, ticker)

    def fetch(series, min_close_ts, cursor):
        assert series == "KXWORKER"
        assert cursor is None
        return {
            "markets": [{"ticker": ticker, "result": "yes"}],
            "cursor": None,
        }

    receipt_path = tmp_path / "grading.json"
    first = run_grading_pass(
        ledger,
        fetch_settled_page=fetch,
        receipt_path=receipt_path,
    )
    assert first.exit_code == 0
    assert first.receipt["status"] == "PASS"
    assert first.receipt["settlements_claimed_for_grading"] == 1
    assert first.receipt["coverage"]["attempt_coverage_ratio"] == 1.0
    assert first.receipt["execution_authority"] is False
    assert first.receipt["cancel_authority"] is False
    assert first.receipt["receipt_sha256"] == _receipt_digest(first.receipt)
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == first.receipt

    # The canonical settlement claim prevents a second trust update.
    second = run_grading_pass(
        ledger,
        fetch_settled_page=fetch,
        receipt_path=None,
    )
    assert second.exit_code == 0
    assert second.receipt["backlog_at_start"] == 0
    assert second.receipt["settlements_claimed_for_grading"] == 0
    ledger.close()


def test_worker_is_degraded_when_listing_pagination_is_truncated(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXLADDER-26JUL26-YES"
    _seed(ledger, ticker)

    def fetch(_series, _min_close_ts, _cursor):
        return {"markets": [], "cursor": "still-more"}

    result = run_grading_pass(
        ledger,
        fetch_settled_page=fetch,
        receipt_path=None,
        max_pages_per_series=2,
    )
    assert result.exit_code == 2
    assert result.receipt["status"] == "DEGRADED"
    assert result.receipt["coverage"]["pagination_truncated"] is True
    assert "settled_listing_pagination_truncated" in result.receipt["blockers"]
    ledger.close()
