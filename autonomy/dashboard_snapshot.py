"""Wave-42: decouple the web dashboard's heavy read from the live ledger.

The dashboard used to open the ledger and run a full backtest — a minutes-long
scan over ~10M rows — on every ``/api/autonomy`` poll. That read holds a SHARED
lock for its whole duration, which blocks the shadow brain's commit and surfaced
as the chronic "database is locked" (``CYCLE_ERROR``) contention. Raising the
writer's busy-timeout only makes the brain *wait out* each scan; it does not
remove the collision.

The brain's 6-hourly recalibration already computes the full backtest while it
holds the ledger in-process (so it never contends with itself). This module
lets that recalibration persist everything the dashboard needs into one
artifact, and a dedicated light task refreshes the cheap ledger summaries
between recals. The dashboard then reads a file instead of the ledger — matching
the rest of the dashboard, which already reads artifacts and never opens the
ledger.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.ledger import AutonomyLedger

LATEST_DASHBOARD_SNAPSHOT_PATH = Path("runtime/autonomy/latest_dashboard_snapshot.json")


def _json_default(o: Any) -> Any:
    """Coerce stray numpy/Decimal scalars so the artifact always serializes."""
    try:
        return float(o)
    except (TypeError, ValueError):
        return str(o)


def build_dashboard_snapshot(
    ledger: AutonomyLedger,
    report: dict[str, Any] | None = None,
    *,
    prior: dict[str, Any] | None = None,
    refresh_backtest: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assemble the dashboard's ledger-derived state from a live ledger.

    ``report`` is a precomputed backtest to reuse — the recalibration already
    has one, so it never pays for a second scan. When ``report`` is absent and
    ``refresh_backtest`` is True a fresh backtest runs; when it is False the
    heavy backtest and canary are carried over from ``prior`` (a previously
    written snapshot) so a light refresh updates only the cheap summaries.
    """
    from autonomy.backtest import run_backtest
    from autonomy.canary import evaluate_canary_readiness

    stamp = (now or datetime.now(timezone.utc)).isoformat()
    ledger_summary = ledger.performance_summary()
    statistics_intake = ledger.external_observation_summary()

    if report is None and refresh_backtest:
        report = run_backtest(ledger, bootstrap_weights=False)

    if report is None:
        # Light refresh: keep the last heavy backtest + canary verbatim.
        report = (prior or {}).get("backtest") or {}
        canary = (prior or {}).get("canary") or {}
        backtest_stamp = (prior or {}).get("backtest_generated_at") or stamp
    else:
        canary = evaluate_canary_readiness(ledger, backtest_report=report).to_dict()
        backtest_stamp = report.get("created_at") or stamp

    # Wave-51: per-scope (coin/league) analytics + the overview account block for
    # the redesigned dashboard. Computed here (the writer already holds the
    # ledger) so the dashboard never opens it. Fail-soft: a bug in the new
    # analytics must never break the snapshot the rest of the dashboard needs.
    overview: dict[str, Any] = {}
    scopes: dict[str, Any] = {}
    try:
        from autonomy.scope_analytics import (
            build_overview,
            build_scope_analytics,
            load_season_active,
        )

        overview = build_overview(ledger._conn, report)
        scopes = build_scope_analytics(ledger._conn, season_active=load_season_active())
    except Exception:  # noqa: BLE001 -- never let analytics sink the snapshot
        overview = (prior or {}).get("overview") or {}
        scopes = (prior or {}).get("scopes") or {}

    return {
        "generated_at": stamp,
        "backtest_generated_at": backtest_stamp,
        "ledger_summary": ledger_summary,
        "statistics_intake": statistics_intake,
        "backtest": report,
        "canary": canary,
        "overview": overview,
        "scopes": scopes,
    }


def write_dashboard_snapshot(
    snapshot: dict[str, Any],
    path: Path | None = None,
) -> Path:
    """Atomically write the snapshot so a reader never sees a partial file."""
    target = path or LATEST_DASHBOARD_SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(snapshot, sort_keys=True, default=_json_default), encoding="utf-8")
    tmp.replace(target)  # os.replace: atomic swap on the same volume
    return target


def read_dashboard_snapshot(path: Path | None = None) -> dict[str, Any] | None:
    """Return the persisted snapshot, or None if absent/unreadable."""
    target = path or LATEST_DASHBOARD_SNAPSHOT_PATH
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
