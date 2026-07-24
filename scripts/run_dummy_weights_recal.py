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
os.environ.setdefault("DUMMY_LEDGER_BUSY_TIMEOUT_S", "600")

RUNTIME = Path("runtime/autonomy")
STAMP = RUNTIME / "last_recalibration.json"
INTERVAL_HOURS = 6.0


def _due(now: datetime) -> bool:
    try:
        stamp = json.loads(STAMP.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(str(stamp.get("at")))
        return (now - last).total_seconds() / 3600.0 >= INTERVAL_HOURS
    except (OSError, ValueError, TypeError):
        return True  # missing/unreadable stamp -> recalibrate now


def main() -> int:
    now = datetime.now(timezone.utc)
    if "--force" not in sys.argv and not _due(now):
        print("weights fresh (< 6h) -- skipping")
        return 0
    from autonomy.backtest import run_backtest
    from autonomy.ledger import AutonomyLedger
    from autonomy.signals.market_debias import fit_curve, ledger_samples, write_curve

    t0 = time.perf_counter()
    try:
        ledger = AutonomyLedger()
        try:
            report = run_backtest(ledger, bootstrap_weights=True, include_diagnostics=False)
            write_curve(fit_curve(ledger_samples(ledger)))
        finally:
            ledger.close()
    except Exception as exc:  # noqa: BLE001 -- a scheduled run must not alarm
        print(f"RECAL_ERROR {type(exc).__name__}: {str(exc)[:200]}")
        return 0
    dur = time.perf_counter() - t0
    summary = {
        "at": now.isoformat(),
        "duration_seconds": round(dur, 1),
        "settled_markets": report.get("settled_markets"),
        "derived_weights": report.get("derived_weights"),
        "exact_scope_weights": len(report.get("sources_by_scope") or {}),
        "out_of_band": True,
    }
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"RECAL_DONE duration={dur:.0f}s settled={report.get('settled_markets')} "
          f"scopes={len(report.get('sources_by_scope') or {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
