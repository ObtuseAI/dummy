"""Operator alerts: surface the few events that change what the operator does.

An unattended predator needs to shout only when it matters — it self-stopped,
it de-risked on drawdown, the evidence gate finally went green, or cycles are
erroring in a streak. Alerts are appended to a JSONL log and the latest is
mirrored to a small JSON file a dashboard or notifier can poll. De-duplicated
so the same standing condition does not spam every cycle.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class _WatchdogCheckSkipped(Exception):
    """Internal: the watchdog-staleness check is disabled for this run."""

RUNTIME_DIR = Path("runtime/autonomy")
ALERTS_LOG = RUNTIME_DIR / "alerts.jsonl"
ALERTS_LATEST = RUNTIME_DIR / "alerts_latest.json"
ALERT_STATE = RUNTIME_DIR / "alert_state.json"
CRITICAL_ALERTS_ENABLED_ENV = "DUMMY_CRITICAL_ALERTS_ENABLED"
CRITICAL_ALERT_WEBHOOK_URL_ENV = "DUMMY_CRITICAL_ALERT_WEBHOOK_URL"
CRITICAL_ALERT_ALLOWED_HOSTS_ENV = "DUMMY_CRITICAL_ALERT_ALLOWED_HOSTS"
CRITICAL_ALERT_TIMEOUT_SECONDS = 3.0

ExternalAlertTransport = Callable[[str, dict[str, str], float], int]

SEVERITY = {
    "SELF_STOP": "critical",
    "DRAWDOWN_LADDER": "warning",
    "GATE_GREEN": "info",
    "GATE_REGRESSION": "warning",
    "CYCLE_ERROR_STREAK": "warning",
    "SIGNAL_QUALITY_REJECTION": "warning",
    # A recalibration produced a degenerate trust vector and was rejected.
    "RECAL_REJECTED": "critical",
    # The authoritative backtest summary is older than the freshness bound;
    # downstream evaluation is fail-closed until it refreshes.
    "BACKTEST_STALE": "warning",
    # The ledger database is bloated or a read-only health probe failed.
    "LEDGER_HEALTH": "warning",
    # Ops watchdog (autonomy/watchdog.py): a scheduled task went silent, cycles
    # are erroring in a streak, the ledger crossed its size ceiling, an operator
    # kill file is present, or free disk fell below the floor.
    "WATCHDOG_TASK_STALE": "critical",
    "WATCHDOG_JOB_REFUSED": "critical",
    "WATCHDOG_CYCLE_ERROR_STREAK": "warning",
    "WATCHDOG_LEDGER_SIZE": "critical",
    "WATCHDOG_KILL_FILE": "critical",
    "WATCHDOG_DISK_FLOOR": "critical",
    "RESEARCH_STALL": "critical",
    # Execution-policy tournament (WS-A2/F2): a challenger cohort accrued enough
    # witnessed fill clusters to clear the evidence gate and become eligible for
    # a promotion-ladder review. Evidence only -- never an automatic policy
    # switch.
    "EXECUTION_TOURNAMENT_GATE": "info",
    # Autonomous thresholded promotion (fusion-membership governance only;
    # live trading authorization remains operator-gated elsewhere).
    "AUTO_PROMOTION": "info",
    "AUTO_ESCALATION": "info",
    "AUTO_DEMOTION": "warning",
    "PROMOTION_RUN_ABORTED": "warning",
    # Deployed-code drift (autonomy/code_drift.py): the running checkout is
    # behind origin/main, so a healthy-looking daemon may be executing stale
    # logic. Severity escalates to critical when far behind.
    "CODE_DRIFT": "warning",
    # Negative-control battery (autonomy/negative_controls.py): a source's
    # "edge" survived a scrambled world — contamination, not skill. The
    # evidence feeding trust/promotion for that source is suspect.
    "NEGATIVE_CONTROL_FLAG": "warning",
}


def _load_state() -> dict[str, Any]:
    if ALERT_STATE.exists():
        try:
            return json.loads(ALERT_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_STATE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _default_external_transport(
    endpoint: str,
    payload: dict[str, str],
    timeout_seconds: float,
) -> int:
    """POST one alert without following redirects; return the HTTP status."""
    from urllib.request import HTTPRedirectHandler, Request, build_opener

    class _NoRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
            return None

    request = Request(
        endpoint,
        data=json.dumps(payload, sort_keys=True).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Dummy-Critical-Alert/1",
        },
        method="POST",
    )
    with build_opener(_NoRedirects).open(request, timeout=timeout_seconds) as response:
        return int(response.status)


def _endpoint_refusal(endpoint: str, allowed_hosts: set[str]) -> str | None:
    """Return a stable refusal code without ever echoing the secret-bearing URL."""
    try:
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or "").casefold().rstrip(".")
    except ValueError:
        return "malformed_endpoint"
    if parsed.scheme.casefold() != "https":
        return "https_required"
    if not host:
        return "missing_endpoint_host"
    if parsed.username is not None or parsed.password is not None:
        return "userinfo_forbidden"
    if parsed.fragment:
        return "fragment_forbidden"
    try:
        if parsed.port not in (None, 443):
            return "nonstandard_port_forbidden"
    except ValueError:
        return "malformed_endpoint"
    if not allowed_hosts:
        return "missing_host_allowlist"
    if host not in allowed_hosts:
        return "host_not_allowlisted"
    if host == "localhost":
        return "local_endpoint_forbidden"
    try:
        address = ip_address(host)
    except ValueError:
        return None
    if not address.is_global:
        return "non_public_endpoint_forbidden"
    return None


def _external_delivery(
    record: Mapping[str, Any],
    *,
    external_transport: ExternalAlertTransport | None,
    environ: Mapping[str, str],
) -> dict[str, str]:
    """Attempt an explicitly enabled critical-only delivery, fail closed."""
    if record["severity"] != "critical":
        return {"status": "NOT_CRITICAL"}
    if external_transport is None and "PYTEST_CURRENT_TEST" in environ:
        return {"status": "REFUSED", "reason": "test_environment"}
    if environ.get(CRITICAL_ALERTS_ENABLED_ENV) != "1":
        return {"status": "DISABLED"}
    endpoint = str(environ.get(CRITICAL_ALERT_WEBHOOK_URL_ENV) or "").strip()
    allowed_hosts = {
        item.strip().casefold().rstrip(".")
        for item in str(environ.get(CRITICAL_ALERT_ALLOWED_HOSTS_ENV) or "").split(",")
        if item.strip()
    }
    refusal = _endpoint_refusal(endpoint, allowed_hosts)
    if refusal is not None:
        return {"status": "REFUSED", "reason": refusal}

    # Deliberately exclude ``detail``: it can contain paths, raw exceptions, or
    # other operational data that belongs only in the local evidence log.
    from core.secret_guard import redact_text

    safe_message = " ".join(redact_text(str(record["message"])).split())[:512]
    payload = {
        "kind": str(record["kind"]),
        "severity": str(record["severity"]),
        "message": safe_message,
        "at": str(record["at"]),
    }
    transport = external_transport or _default_external_transport
    try:
        response_status = int(
            transport(
                endpoint,
                payload,
                CRITICAL_ALERT_TIMEOUT_SECONDS,
            )
        )
    except Exception as exc:
        # Exception messages from HTTP clients commonly include the full URL.
        # Persist only the exception type so webhook credentials never land in
        # alerts.jsonl or the dashboard mirror.
        return {
            "status": "FAILED",
            "reason": f"transport_error:{type(exc).__name__}",
        }
    if not 200 <= response_status < 300:
        return {
            "status": "FAILED",
            "reason": f"http_status:{response_status}",
        }
    return {"status": "DELIVERED"}


def emit_alert(
    kind: str,
    message: str,
    detail: dict[str, Any] | None = None,
    now_iso: str | None = None,
    *,
    external_transport: ExternalAlertTransport | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Append + mirror one alert and optionally deliver critical alerts."""
    from core.secret_guard import redact, redact_text

    record = {
        "kind": kind,
        "severity": SEVERITY.get(kind, "info"),
        "message": redact_text(message),
        "detail": redact(detail or {}),
        "at": now_iso or datetime.now(timezone.utc).isoformat(),
    }
    record["external_delivery"] = _external_delivery(
        record,
        external_transport=external_transport,
        environ=os.environ if environ is None else environ,
    )
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with ALERTS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    ALERTS_LATEST.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def evaluate_alerts(cycle_record: dict[str, Any], risk_state: dict[str, Any] | None,
                    gate_ready: bool, now_iso: str | None = None,
                    *, ledger_health: dict[str, Any] | None = None,
                    backtest_freshness: dict[str, Any] | None = None,
                    tournament_summary: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Decide which alerts to emit this cycle, de-duplicated against prior state."""
    state = _load_state()
    fired: list[dict[str, Any]] = []

    status = str(cycle_record.get("status", ""))

    # Self-stop: fire once per stop episode.
    if status.startswith("HALTED_SELF_STOP"):
        if not state.get("self_stopped"):
            fired.append(emit_alert("SELF_STOP", status, {"cycle": cycle_record}, now_iso))
            state["self_stopped"] = True
    else:
        state["self_stopped"] = False

    # Drawdown ladder: fire when the ladder rung deepens.
    if risk_state:
        peak = risk_state.get("equity_peak_cents") or 0
        bankroll = risk_state.get("bankroll_cents") or 0
        dd = (1.0 - bankroll / peak) if peak else 0.0
        rung = 0
        for threshold in (0.10, 0.20, 0.30):
            if dd >= threshold - 1e-9:
                rung += 1
        if rung > int(state.get("drawdown_rung", 0)):
            fired.append(emit_alert("DRAWDOWN_LADDER", f"drawdown {dd:.1%} reached rung {rung}",
                                    {"drawdown": round(dd, 4), "rung": rung}, now_iso))
        state["drawdown_rung"] = rung

    # Explicit controlled-live authority edges. Paper/shadow evidence is
    # retired and never feeds this signal.
    if gate_ready and not state.get("gate_green"):
        fired.append(emit_alert(
            "GATE_GREEN",
            "controlled live authority contract is READY",
            {"paper_results_authority": "RETIRED_NON_AUTHORITATIVE"},
            now_iso,
        ))
    elif not gate_ready and state.get("gate_green"):
        fired.append(emit_alert(
            "GATE_REGRESSION",
            "controlled live authority contract returned to BLOCKED",
            {"paper_results_authority": "RETIRED_NON_AUTHORITATIVE"},
            now_iso,
        ))
    state["gate_green"] = bool(gate_ready)

    # Cycle-error streak.
    if status.startswith("CYCLE_ERROR"):
        streak = int(state.get("error_streak", 0)) + 1
        state["error_streak"] = streak
        if streak >= 3 and streak != int(state.get("last_error_alert_streak", 0)):
            fired.append(emit_alert("CYCLE_ERROR_STREAK", f"{streak} consecutive cycle errors",
                                    {"status": status}, now_iso))
            state["last_error_alert_streak"] = streak
    else:
        state["error_streak"] = 0

    # Malformed model statistics are quarantined by the ledger. Alert on the
    # start of an episode so silent source/schema drift is still operator-visible.
    rejected = int(cycle_record.get("signals_rejected") or 0)
    if rejected > 0 and not state.get("signal_rejection_active"):
        fired.append(emit_alert(
            "SIGNAL_QUALITY_REJECTION",
            f"{rejected} signal observations failed intake validation",
            {"signals_rejected": rejected},
            now_iso,
        ))
    state["signal_rejection_active"] = rejected > 0

    # Ledger health: bloat or a failed read-only probe. Fire once per episode
    # so a persistent condition does not spam every cycle.
    if ledger_health:
        unhealthy = bool(ledger_health.get("bloat_warn")) or bool(
            ledger_health.get("probe_error")
        )
        if unhealthy and not state.get("ledger_health_alert_active"):
            fired.append(emit_alert(
                "LEDGER_HEALTH",
                "ledger health degraded: "
                + ("bloat " if ledger_health.get("bloat_warn") else "")
                + (f"probe_error={ledger_health.get('probe_error')}"
                   if ledger_health.get("probe_error") else "")
                + f"size={ledger_health.get('size_gib')}GiB",
                ledger_health, now_iso,
            ))
        state["ledger_health_alert_active"] = unhealthy

    # Watchdog liveness: the watchdog watches the fleet, so only the cycle can
    # watch the watchdog. Its status file went 3 days stale unnoticed once
    # (task never registered). Rising-edge alert on staleness/absence.
    try:
        import os as _os
        from pathlib import Path as _Path

        if _os.environ.get("DUMMY_WATCHDOG_STALE_ALERT", "1") != "1":
            raise _WatchdogCheckSkipped
        wd_path = _Path("runtime/autonomy/watchdog_status.json")
        wd_stale_s = float(_os.environ.get("DUMMY_WATCHDOG_STALE_S", "1800"))
        if wd_path.exists():
            wd = json.loads(wd_path.read_text(encoding="utf-8"))
            wd_at = datetime.fromisoformat(str(wd.get("generated_at")))
            wd_age = (datetime.now(timezone.utc) - wd_at).total_seconds()
            wd_stale = wd_age > wd_stale_s
        else:
            wd_age = None
            wd_stale = True
        if wd_stale and not state.get("watchdog_stale_alert_active"):
            fired.append(emit_alert(
                "WATCHDOG_STALE",
                "watchdog_status.json is "
                + (f"{round(wd_age)}s old" if wd_age is not None else "missing")
                + f" (threshold {round(wd_stale_s)}s) — the fleet monitor itself is down",
                {"age_seconds": wd_age, "threshold_seconds": wd_stale_s}, now_iso,
            ))
        state["watchdog_stale_alert_active"] = wd_stale
    except _WatchdogCheckSkipped:
        pass  # disabled (hermetic test runs)
    except Exception:
        pass  # a malformed status file must never break cycle alerting

    # Backtest evidence staleness: the authoritative summary went 6 days stale
    # once with no alarm. Fire on the rising edge of the stale episode.
    if backtest_freshness is not None:
        stale = bool(backtest_freshness.get("is_stale"))
        if stale and not state.get("backtest_stale_alert_active"):
            fired.append(emit_alert(
                "BACKTEST_STALE",
                "authoritative backtest summary is stale "
                f"(age_hours={backtest_freshness.get('age_hours')}, "
                f"reason={backtest_freshness.get('reason')}); "
                "research diagnostics are stale; live authority is unaffected",
                backtest_freshness, now_iso,
            ))
        state["backtest_stale_alert_active"] = stale

    # Execution tournament: sample volume alone is never promotion authority.
    # Fire only for a future lane that explicitly carries promotion readiness
    # and witnessed broker-fill backing. Missing/legacy labels fail closed.
    if tournament_summary:
        gated = {
            str(row.get("cohort"))
            for row in (tournament_summary.get("ranking") or [])
            if row.get("gate_met") is True
            and row.get("promotion_review_eligible") is True
            and row.get("counts_toward_promotion_readiness") is True
            and row.get("witnessed_broker_fill_backing") is True
            and row.get("counts_toward_policy_switch") is False
            and str(row.get("cohort")) != "C0"
        }
        already = set(state.get("tournament_gated_cohorts") or [])
        newly = sorted(gated - already)
        if newly:
            fired.append(emit_alert(
                "EXECUTION_TOURNAMENT_GATE",
                f"execution cohort(s) {', '.join(newly)} carry an explicit "
                "witnessed-fill promotion-review qualification",
                {"newly_gated_cohorts": newly,
                 "headline": tournament_summary.get("headline", {})},
                now_iso,
            ))
        state["tournament_gated_cohorts"] = sorted(gated | already)

    _save_state(state)
    return fired


def recent_alerts(limit: int = 20) -> list[dict[str, Any]]:
    if not ALERTS_LOG.exists():
        return []
    try:
        lines = ALERTS_LOG.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
