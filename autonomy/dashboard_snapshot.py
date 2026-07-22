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

_RETIRED_PAPER_OVERVIEW_FIELDS = {
    "paper",
    "paper_account_as_of",
    "bankroll_cents",
    "base_bankroll_cents",
    "exposure_cents",
    "stage",
    "account_roi",
    "realized_pnl_cents",
    "realized_trade_statistics",
    "balance_curve",
    "promoted",
    "close_to_promotion",
    "performance_evidence_as_of",
}


def sanitize_primary_overview(value: dict[str, Any] | None) -> dict[str, Any]:
    """Remove legacy paper-result fields at the primary artifact boundary."""
    result = dict(value or {})
    for key in _RETIRED_PAPER_OVERVIEW_FIELDS:
        result.pop(key, None)
    result.update({
        "overview_schema_version": 2,
        "primary_account": "live_kalshi",
        "paper_results_status": "RETIRED_NON_AUTHORITATIVE",
        "paper_results_can_enable_live": False,
        "paper_results_can_block_live": False,
        "paper_history_preserved_for_audit": True,
        "live_authority_source": "explicit_live_control_contracts_only",
    })
    return result


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
    block_status: dict[str, str] = {}
    block_errors: dict[str, str] = {}
    tier_performance_stamp: str | None = None

    if report is None and refresh_backtest:
        report = run_backtest(ledger, bootstrap_weights=False)

    if report is None:
        # Light refresh: keep the last heavy backtest + historical paper audit
        # verbatim.  It remains non-authoritative.
        report = dict((prior or {}).get("backtest") or {})
        paper_audit = (prior or {}).get("paper_evidence_audit") or {}
        historical_canary = paper_audit.get("canary") or {}
        backtest_stamp = (prior or {}).get("backtest_generated_at") or stamp
        try:
            from autonomy.tier_performance import tier_performance_report

            report["tier_performance"] = tier_performance_report(ledger._conn)
            tier_performance_stamp = stamp
            block_status["tier_performance"] = "REFRESHED_LIGHT"
        except Exception as exc:  # noqa: BLE001 -- carry prior evidence honestly
            tier_performance_stamp = (
                (prior or {}).get("tier_performance_generated_at")
                or (backtest_stamp if report.get("tier_performance") else None)
            )
            block_status["tier_performance"] = (
                "CARRIED_AFTER_ERROR"
                if report.get("tier_performance")
                else "UNAVAILABLE"
            )
            block_errors["tier_performance"] = (
                f"{type(exc).__name__}: {exc}"[:200]
            )
    else:
        historical_canary = evaluate_canary_readiness(
            ledger,
            backtest_report=report,
        ).to_dict()
        backtest_stamp = report.get("created_at") or stamp
        if isinstance(report.get("tier_performance"), dict):
            tier_performance_stamp = str(backtest_stamp)
            block_status["tier_performance"] = "REFRESHED_WITH_BACKTEST"
        else:
            block_status["tier_performance"] = "UNAVAILABLE"

    canary = {
        "status": "RETIRED_NON_AUTHORITATIVE",
        "ready": False,
        "execution_authority": False,
        "can_enable_live": False,
        "can_block_live": False,
        "historical_research_ready": bool(historical_canary.get("ready")),
    }

    # The account overview is cheap and is refreshed on every light pass. Scope
    # analytics scan the large signal/settlement tables, so they are refreshed
    # only with the heavy backtest and are otherwise carried forward. Keep a
    # separate timestamp/status for each block: the artifact write time must not
    # make carried or failed analytics appear fresh.
    prior = prior or {}

    def _prior_block_stamp(key: str) -> str | None:
        explicit = prior.get(f"{key}_generated_at")
        if explicit:
            return str(explicit)
        if prior.get(key) and prior.get("generated_at"):
            # Backwards compatibility for schema-v1 snapshots.
            return str(prior["generated_at"])
        return None

    overview: dict[str, Any]
    overview_stamp: str | None
    try:
        from autonomy.scope_analytics import build_overview

        overview = sanitize_primary_overview(build_overview(ledger._conn, report))
        overview_stamp = stamp
        block_status["overview"] = "REFRESHED"
    except Exception as exc:  # noqa: BLE001 -- never let analytics sink snapshot
        overview = sanitize_primary_overview(prior.get("overview") or {})
        overview_stamp = _prior_block_stamp("overview")
        block_status["overview"] = (
            "CARRIED_AFTER_ERROR" if overview else "UNAVAILABLE"
        )
        block_errors["overview"] = f"{type(exc).__name__}: {exc}"[:200]

    scopes: dict[str, Any]
    scopes_stamp: str | None
    if not refresh_backtest:
        scopes = prior.get("scopes") or {}
        scopes_stamp = _prior_block_stamp("scopes")
        block_status["scopes"] = (
            "CARRIED_LIGHT_REFRESH" if scopes else "UNAVAILABLE"
        )
    else:
        try:
            from autonomy.scope_analytics import build_scope_analytics, load_season_active

            scopes = build_scope_analytics(
                ledger._conn,
                season_active=load_season_active(),
            )
            scopes_stamp = stamp
            block_status["scopes"] = "REFRESHED"
        except Exception as exc:  # noqa: BLE001 -- fail-soft with truthful age
            scopes = prior.get("scopes") or {}
            scopes_stamp = _prior_block_stamp("scopes")
            block_status["scopes"] = (
                "CARRIED_AFTER_ERROR" if scopes else "UNAVAILABLE"
            )
            block_errors["scopes"] = f"{type(exc).__name__}: {exc}"[:200]

    return {
        "snapshot_schema_version": 2,
        "generated_at": stamp,
        "backtest_generated_at": backtest_stamp,
        "tier_performance_generated_at": tier_performance_stamp,
        "overview_generated_at": overview_stamp,
        "scopes_generated_at": scopes_stamp,
        "block_status": block_status,
        "block_errors": block_errors,
        "ledger_summary": ledger_summary,
        "statistics_intake": statistics_intake,
        "backtest": report,
        "canary": canary,
        "paper_evidence_audit": {
            "status": "RETIRED_NON_AUTHORITATIVE",
            "execution_authority": False,
            "raw_history_preserved": True,
            "canary": historical_canary,
        },
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
