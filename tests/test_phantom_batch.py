"""Wave-43c: apply_settlement with pre-fetched signals == the per-market query.

_apply_phantom_settlements shares one batched calibration fetch across a
backlog of settlements instead of one query per market. This pins that passing
the batched signals produces identical weight updates to the query path, so the
backlog optimization can't change what the learner learns.
"""
from __future__ import annotations

from autonomy.ledger import AutonomyLedger
from autonomy.learner import Learner
from autonomy.ontology import Signal


def _sig(source, ticker, p, at):
    return Signal(source=source, market_ticker=ticker, probability_yes=p,
                  uncertainty=0.1, rationale="", created_at=at)


def _seed(led):
    led.record_signal(_sig("market_prior", "M", 0.5, "2026-01-01T00:00:01+00:00"))
    led.record_signal(_sig("s1", "M", 0.9, "2026-01-01T00:00:02+00:00"))
    led.record_signal(_sig("s2", "M", 0.3, "2026-01-01T00:00:03+00:00"))
    led.record_settlement("M", True)


def test_prefetched_signals_match_query(tmp_path):
    a = AutonomyLedger(db_path=tmp_path / "a.db")
    _seed(a)
    r_query = Learner(a).apply_settlement("M", True)   # queries per market
    a.close()

    b = AutonomyLedger(db_path=tmp_path / "b.db")
    _seed(b)
    prefetched = b.calibration_signals_for_settled(["M"])["M"]
    r_batch = Learner(b).apply_settlement("M", True, signals=prefetched)  # shared fetch
    b.close()

    assert r_query and r_query == r_batch


# --------------------------------------------------------------------------
# 2026-07-24 audit §8: "phantom grading coverage % is not emitted anywhere --
# 'grades every priced market' is unverifiable; <=3 pages/series can overflow
# on 50+ strike ladders. Emit a coverage ratio."
# --------------------------------------------------------------------------

from autonomy.brain import CycleReport, PredatorBrain          # noqa: E402
from autonomy.reconciler import PHANTOM_COVERAGE_VERSION, Reconciler  # noqa: E402


class _CoverageLedger:
    """Duck-typed ledger: just the two calls the phantom path makes."""

    def __init__(self, unsettled: list[str]) -> None:
        self._unsettled = list(unsettled)
        self.settled: list[tuple[str, bool]] = []

    def unsettled_forecast_markets(self, max_age_days: float = 7.0) -> list[str]:
        return list(self._unsettled)

    def record_settlement(self, ticker: str, result_yes: bool) -> None:
        self.settled.append((ticker, result_yes))


def _page(markets, cursor=None):
    return {"markets": markets, "cursor": cursor}


def test_coverage_ratio_emitted_for_a_complete_sweep():
    ledger = _CoverageLedger(["KXA-1", "KXA-2", "KXB-1", "KXB-2"])

    def fetch(series, min_close_ts, cursor):
        if series == "KXA":
            return _page([{"ticker": "KXA-1", "result": "yes"}])
        return _page([{"ticker": "KXB-2", "result": "no"}])

    graded = Reconciler(ledger, fetch_settled_page=fetch)
    settled = graded.reconcile_forecast_settlements(["KXA", "KXB"])

    assert sorted(settled) == [("KXA-1", True), ("KXB-2", False)]
    coverage = graded.last_forecast_coverage
    assert coverage["phantom_coverage_version"] == PHANTOM_COVERAGE_VERSION
    assert coverage["status"] == "SWEPT"
    assert coverage["eligible_unsettled_forecasts"] == 4
    assert coverage["attempted_eligible_forecasts"] == 4
    assert coverage["attempt_coverage_ratio"] == 1.0
    assert coverage["graded_this_pass"] == 2
    assert coverage["graded_coverage_ratio"] == 0.5
    assert coverage["pagination_truncated"] is False
    assert coverage["listing_errors"] is False
    assert coverage["complete"] is True


def test_pagination_overflow_is_an_explicit_flag_not_silent_partial_coverage():
    """A 50+ strike ladder that never exhausts its cursor must be disclosed."""
    ledger = _CoverageLedger(["KXLADDER-1", "KXLADDER-2", "KXOK-1"])

    def fetch(series, min_close_ts, cursor):
        if series == "KXLADDER":
            # Always another page: the <=3 page cap can never drain this series.
            return _page([{"ticker": "KXLADDER-1", "result": "yes"}], cursor="more")
        return _page([{"ticker": "KXOK-1", "result": "no"}])

    graded = Reconciler(ledger, fetch_settled_page=fetch)
    graded.reconcile_forecast_settlements(["KXLADDER", "KXOK"], max_pages_per_series=3)

    coverage = graded.last_forecast_coverage
    assert coverage["pagination_truncated"] is True
    assert coverage["series_truncated"] == ["KXLADDER"]
    assert coverage["complete"] is False
    # Only the fully-paged series' eligible tickers count as attempted.
    assert coverage["attempted_eligible_forecasts"] == 1
    assert coverage["attempt_coverage_ratio"] == round(1 / 3, 6)


def test_failed_listing_and_unrequested_series_are_not_counted_as_attempted():
    ledger = _CoverageLedger(["KXA-1", "KXDEAD-1", "KXNEVERASKED-1"])

    def fetch(series, min_close_ts, cursor):
        if series == "KXDEAD":
            raise RuntimeError("listing endpoint down")
        return _page([{"ticker": "KXA-1", "result": "yes"}])

    graded = Reconciler(ledger, fetch_settled_page=fetch)
    graded.reconcile_forecast_settlements(["KXA", "KXDEAD"])

    coverage = graded.last_forecast_coverage
    assert coverage["series_failed"] == ["KXDEAD"]
    assert coverage["listing_errors"] is True
    assert coverage["eligible_in_requested_series"] == 2
    assert coverage["eligible_outside_requested_series"] == 1
    assert coverage["attempted_eligible_forecasts"] == 1
    assert coverage["attempt_coverage_ratio"] == round(1 / 3, 6)
    assert coverage["complete"] is False


def test_coverage_receipt_exists_even_when_the_sweep_never_runs():
    ledger = _CoverageLedger(["KXA-1"])
    disabled = Reconciler(ledger)  # no listing endpoint injected
    assert disabled.reconcile_forecast_settlements(["KXA"]) == []
    coverage = disabled.last_forecast_coverage
    assert coverage["status"] == "NOT_ATTEMPTED_NO_LISTING_ENDPOINT"
    assert coverage["eligible_unsettled_forecasts"] is None
    assert coverage["attempt_coverage_ratio"] is None
    assert coverage["complete"] is False


class _Scanner:
    watchlist = ["KXA", "KXLADDER"]


class _Learner:
    def apply_settlement(self, ticker, result_yes, signals=None, cluster_weight=1.0):
        return {}


def _brain_with(reconciler) -> PredatorBrain:
    """A brain shell holding only what _apply_phantom_settlements touches."""
    brain = object.__new__(PredatorBrain)
    brain.reconciler = reconciler
    brain.scanner = _Scanner()
    brain.learner = _Learner()
    brain.ledger = object()
    return brain


def test_cycle_report_carries_the_coverage_receipt():
    ledger = _CoverageLedger(["KXA-1", "KXLADDER-1"])

    def fetch(series, min_close_ts, cursor):
        if series == "KXLADDER":
            return _page([], cursor="more")
        return _page([{"ticker": "KXA-1", "result": "yes"}])

    brain = _brain_with(Reconciler(ledger, fetch_settled_page=fetch))
    report = CycleReport(status="", mode="shadow", stage=1, bankroll_cents=0)
    brain._apply_phantom_settlements(report)

    assert report.phantom_settlements == 1
    coverage = report.phantom_coverage
    assert coverage["attempt_coverage_ratio"] == 0.5
    assert coverage["graded_coverage_ratio"] == 0.5
    assert coverage["pagination_truncated"] is True
    # The receipt travels to runtime/autonomy/cycles.jsonl via to_dict().
    assert report.to_dict()["phantom_coverage"] == coverage
    assert any(
        note.startswith("phantom_coverage_pagination_truncated:")
        for note in report.notes
    )


def test_failed_sweep_reports_zero_coverage_instead_of_silence():
    class _Boom:
        def reconcile_forecast_settlements(self, series_list):
            raise RuntimeError("ledger locked")

    brain = _brain_with(_Boom())
    report = CycleReport(status="", mode="shadow", stage=1, bankroll_cents=0)
    brain._apply_phantom_settlements(report)

    assert report.phantom_coverage["status"] == "SWEEP_FAILED"
    assert report.phantom_coverage["error"] == "RuntimeError"
    assert report.phantom_coverage["complete"] is False
    assert report.notes == ["phantom_sweep_failed:RuntimeError"]
