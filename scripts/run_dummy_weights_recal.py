"""Out-of-band trust-weight recalibration (Wave-81).

The daemon's in-cycle recal (``daemon._maybe_recalibrate``) is deferred once the
ledger is large, because a full backtest bootstrap cannot finish inside the
13-min cycle watchdog. This task runs that same weights-only bootstrap + the
market-debias curve refit STANDALONE -- no watchdog -- so trust weights keep
refreshing on a large ledger. It is the ONLY reliable weight refresher in that
regime (the daemon defers; ``run_dummy_backtest_report.py`` uses
bootstrap_weights=False).

Fail-soft and idempotent: honors the same 6h interval stamp the daemon uses
(skips when weights are fresh), uses a generous ledger busy_timeout (it has no
watchdog, so waiting out a concurrent cycle's chunked write is fine), and never
raises -- a scheduled run must not alarm on a transient lock.

Fail-soft is not the same as silent. The stamp records what the run actually
achieved, and the exit code distinguishes a completed refresh from a failed one
(see EXIT_* below), so the launcher can report a failure instead of returning 0
over it. Weights themselves land in the ledger inside ``run_backtest``; the
stamp is written as soon as that succeeds, because the market-debias curve is a
separate artifact whose failure must not discard the record of a completed
refresh.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Out-of-band: no watchdog, so wait out concurrent chunked writes rather than
# fail. Set before importing the ledger module (busy_timeout is read at import).
#
# OVERRIDE, never setdefault. DUMMY_LEDGER_BUSY_TIMEOUT_S is set to 60 at User
# scope for the cycles, which a 13-minute watchdog bounds and which must fail
# fast. This job is the opposite and wants to wait. setdefault never overrides
# an existing value, so from the moment that User-scope variable was introduced
# this job silently ran with the fleet's 60s -- the exact timeout it exists to
# escape -- and died on "database is locked" against a concurrent cycle instead
# of waiting it out. Tunable via DUMMY_RECAL_LEDGER_BUSY_TIMEOUT_S.
os.environ["DUMMY_LEDGER_BUSY_TIMEOUT_S"] = os.environ.get(
    "DUMMY_RECAL_LEDGER_BUSY_TIMEOUT_S", "600"
)

RUNTIME = Path("runtime/autonomy")
STAMP = RUNTIME / "last_recalibration.json"
INTERVAL_HOURS = 6.0

EXIT_OK = 0
EXIT_RECAL_FAILED = 1
EXIT_WEIGHTS_REJECTED = 2


def _due(now: datetime) -> bool:
    try:
        stamp = json.loads(STAMP.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(str(stamp.get("at")))
        return (now - last).total_seconds() / 3600.0 >= INTERVAL_HOURS
    except (OSError, ValueError, TypeError):
        return True  # missing/unreadable stamp -> recalibrate now


def _write_stamp(summary: dict[str, object]) -> None:
    """Record the refresh atomically, so a crash mid-write cannot corrupt it."""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    tmp = STAMP.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STAMP)


def main() -> int:
    now = datetime.now(timezone.utc)
    if "--force" not in sys.argv and not _due(now):
        print("weights fresh (< 6h) -- skipping")
        return EXIT_OK
    from autonomy.backtest import run_backtest
    from autonomy.ledger import AutonomyLedger
    from autonomy.signals.market_debias import fit_curve, ledger_samples, write_curve

    t0 = time.perf_counter()
    curve_error: str | None = None
    try:
        ledger = AutonomyLedger()
        try:
            report = run_backtest(ledger, bootstrap_weights=True, include_diagnostics=False)
            if not report.get("weights_written"):
                # Fail-closed: the ledger keeps its previous weights, so the
                # stamp must NOT advance. Advancing it would make _due() skip
                # for six hours on weights that were never written.
                reasons = report.get("weights_rejected_reasons") or []
                print("RECAL_WEIGHTS_REJECTED reasons=" + ",".join(map(str, reasons)))
                return EXIT_WEIGHTS_REJECTED
            # Weights are in the ledger now. Stamp before the debias curve: a
            # lock on that separate artifact used to discard this record, so the
            # watchdog alarmed on weights that were in fact current and the next
            # run redid the entire pass.
            dur = time.perf_counter() - t0
            try:
                write_curve(fit_curve(ledger_samples(ledger)))
            except Exception as exc:  # noqa: BLE001 -- side artifact, not the refresh
                curve_error = type(exc).__name__
                print(f"DEBIAS_CURVE_ERROR {curve_error}: {str(exc)[:200]}")
        finally:
            ledger.close()
    except Exception as exc:  # noqa: BLE001 -- a scheduled run must not raise
        print(f"RECAL_ERROR {type(exc).__name__}: {str(exc)[:200]}")
        return EXIT_RECAL_FAILED
    summary = {
        "at": now.isoformat(),
        "duration_seconds": round(dur, 1),
        "settled_markets": report.get("settled_markets"),
        "derived_weights": report.get("derived_weights"),
        "exact_scope_weights": len(report.get("sources_by_scope") or {}),
        "out_of_band": True,
        "weights_written": True,
        "debias_curve_error": curve_error,
    }
    _write_stamp(summary)
    print(f"RECAL_DONE duration={dur:.0f}s settled={report.get('settled_markets')} "
          f"scopes={len(report.get('sources_by_scope') or {})}"
          + (f" debias_curve_error={curve_error}" if curve_error else ""))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
