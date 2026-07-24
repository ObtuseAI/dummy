"""I/O orchestration for the AutoPromotionEngine — gather, decide, apply.

The engine (``autonomy/auto_promotion.py``) is pure: inputs in, decisions out.
This module owns everything with a side effect, in three phases:

  GATHER  rails inputs (kill file, heartbeat, source health, trust-weight
          saturation, exchange status, artifact staleness), settled evidence
          rows grouped by exact scope, eligibility (challenger-gated AND
          emission-stamped ``promotion_eligible``), CLV per scope, realized
          scope-attributed trade P&L (stage-2 fuel), mined-family sizes, and
          the emission tapes of already-fused sources (correlation guard).

  DECIDE  one deterministic ``AutoPromotionEngine.decide`` call.

  APPLY   registry files (promotions.json / auto_demotions.json), one
          hash-chained ledger record per action carrying the full evidence
          dossier, operator alerts, and the dashboard state artifact.

Fail-closed invariants:
  * any tripped rail aborts the ENTIRE run before a single decision is made
    (an ABORT record is chained + alerted so silence is impossible);
  * a broken promotion-ledger hash chain aborts the run (history that cannot
    be trusted must not authorize new risk);
  * this module has no live-trading authority — live_submit.json, the
    second-proof sequence, and session live auth are operator-gated elsewhere
    and are never read or written here.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from autonomy.auto_promotion import (
    ARTIFACT_STALE_HOURS,
    AutoPromotionEngine,
    DEFAULT_CONFIG,
    EngineResult,
    PromotionConfig,
    RailsInputs,
    evaluate_rails,
)
from autonomy.learner import WEIGHT_CEILING
from autonomy.promotion import PromotionRegistry
from autonomy.promotion_ledger import (
    ACTION_ABORT,
    ACTION_DEMOTE,
    ACTION_ESCALATE,
    ACTION_PROMOTE,
    PromotionLedger,
    PromotionLedgerError,
)
from autonomy.taxonomy import grading_scope, specialist_for

RUNTIME_DIR = Path("runtime/autonomy")
PROMOTION_LEDGER_PATH = RUNTIME_DIR / "promotion_ledger.jsonl"
STATE_PATH = RUNTIME_DIR / "auto_promotion_state.json"
MINED_FAMILIES_PATH = RUNTIME_DIR / "mined_scope_families.json"
FORWARD_REGISTRATIONS_PATH = RUNTIME_DIR / "promotion_forward_registrations.json"

# A trust weight pinned at the learner's multiplicative ceiling is the
# weight-saturation anomaly the forecaster's fused-uncertainty note warns
# about; promotion runs stand down until an operator (or the tuner) resolves it.
WEIGHT_SATURATION_EPS = 1e-9


def _valid_trust_key(key: str) -> bool:
    """True for keys the CURRENT trust schema can still update.

    Three live shapes: bare source (``crypto_spot_vol``), vertical-scoped
    (``crypto_spot_vol@CRYPTO``), and exact scope (``scope:`` + the 4-part
    ``source|subject|market_type|horizon_or_phase`` grading key). The stale
    2026-07 branch wrote 3-part ``scope:`` keys; those rows are orphaned —
    no code path updates them again — so a cap they froze at must not
    permanently trip the saturation rail. ``scripts/migrate_trust_keys.py``
    removes them; this filter is defense in depth until it runs.
    """
    if not key.startswith("scope:"):
        return True
    return key[len("scope:"):].count("|") == 3


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _parse_ts(text: Any) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    try:
        return parsed.timestamp()
    except (OSError, OverflowError, ValueError):
        return None


def _usable_optional_clv(
    runtime_dir: Path,
    now_ts: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return only fresh optional CLV evidence plus an auditable status.

    The promotion policy explicitly supports scopes without CLV by applying
    ``MIN_CLUSTERS_NO_CLV``. Therefore a missing or stale optional CLV report
    must behave as unavailable, not as a global promotion-run veto. Excluded
    CLV can never lower the no-CLV cluster threshold or satisfy the CLV gate.
    """
    raw = _load_json(runtime_dir / "clv_report.json")
    if not raw:
        return {}, {
            "status": "MISSING",
            "used": False,
            "generated_at": None,
            "age_hours": None,
            "max_age_hours": ARTIFACT_STALE_HOURS,
        }

    generated_at = raw.get("generated_at")
    generated_ts = _parse_ts(generated_at)
    if generated_ts is None:
        return {}, {
            "status": "INVALID_TIMESTAMP_EXCLUDED",
            "used": False,
            "generated_at": generated_at,
            "age_hours": None,
            "max_age_hours": ARTIFACT_STALE_HOURS,
        }

    signed_age_hours = (now_ts - generated_ts) / 3600.0
    if signed_age_hours < -(5.0 / 60.0):
        return {}, {
            "status": "FUTURE_TIMESTAMP_EXCLUDED",
            "used": False,
            "generated_at": generated_at,
            "age_hours": round(signed_age_hours, 3),
            "max_age_hours": ARTIFACT_STALE_HOURS,
        }

    age_hours = max(0.0, signed_age_hours)
    if age_hours > ARTIFACT_STALE_HOURS:
        return {}, {
            "status": "STALE_EXCLUDED",
            "used": False,
            "generated_at": generated_at,
            "age_hours": round(age_hours, 3),
            "max_age_hours": ARTIFACT_STALE_HOURS,
        }

    return raw, {
        "status": "FRESH",
        "used": True,
        "generated_at": generated_at,
        "age_hours": round(age_hours, 3),
        "max_age_hours": ARTIFACT_STALE_HOURS,
    }


def load_forward_registrations(path: Path) -> dict[str, dict[str, Any]]:
    """Load immutable candidate registrations required before forward scoring.

    A registration binds an exact scope to a SHA-256 candidate fingerprint and
    an aware UTC instant. Missing, malformed, or duplicate scopes are omitted;
    omission makes automatic promotion impossible but leaves diagnostics intact.
    """
    raw = _load_json(path)
    entries = raw.get("registrations") or []
    if not isinstance(entries, list):
        return {}
    found: dict[str, dict[str, Any]] = {}
    invalid: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "")
        fingerprint = str(entry.get("candidate_fingerprint") or "").lower()
        registered_at = entry.get("registered_at")
        if (
            len(scope.split("|")) != 4
            or any(not part.strip() for part in scope.split("|"))
            or len(fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in fingerprint)
            or _parse_ts(registered_at) is None
        ):
            continue
        if scope in found:
            invalid.add(scope)
            continue
        found[scope] = {
            "scope": scope,
            "candidate_fingerprint": fingerprint,
            "registered_at": str(registered_at),
        }
    for scope in invalid:
        found.pop(scope, None)
    return found


# --------------------------------------------------------------------------
# GATHER: rails.
# --------------------------------------------------------------------------

def _default_exchange_anomaly() -> bool:
    """True when the venue reports an anomaly OR its state cannot be fetched.

    Fail-closed by design: the daemon's per-cycle check treats unknown as NOT
    down (trading must not stall on a status blip), but a promotion run is
    adding risk with no urgency — unknown venue state simply defers promotion
    to the next scheduled run.
    """
    try:
        from autonomy.exchange_status import fetch_exchange_status

        status = fetch_exchange_status()
        return not (
            bool(status.get("exchange_active", False))
            and bool(status.get("trading_active", False))
        )
    except Exception:
        return True


def gather_rails_inputs(
    runtime_dir: Path,
    now_ts: float,
    *,
    weights: Mapping[str, float] | None = None,
    exchange_anomaly_check: Callable[[], bool] = _default_exchange_anomaly,
) -> RailsInputs:
    """Assemble every mandatory rail input from the runtime surface."""
    kill_present = (runtime_dir / "KILL").exists()

    heartbeat = _load_json(runtime_dir / "heartbeat.json")
    heartbeat_status = heartbeat.get("last_status")
    heartbeat_alive = bool(heartbeat.get("alive", False))

    # Source health: any source currently quarantined by the circuit breaker
    # is a health error — evidence accrual is degraded, so stand down.
    health = _load_json(runtime_dir / "source_health.json")
    health_error = any(
        int((entry or {}).get("quarantine", 0)) > 0
        for entry in health.values()
        if isinstance(entry, dict)
    )

    saturated = any(
        float(weight) >= WEIGHT_CEILING - WEIGHT_SATURATION_EPS
        for key, weight in (weights or {}).items()
        if _valid_trust_key(str(key))
    )

    # The heartbeat is the mandatory evidence pulse. Missing/unparseable or old
    # heartbeat data remains a hard, fail-closed global rail. CLV is optional by
    # policy and is freshness-filtered separately: stale CLV is excluded and the
    # stricter no-CLV cluster threshold applies.
    last_cycle = _parse_ts(heartbeat.get("last_cycle_at"))
    if last_cycle is None:
        artifact_age_hours = float("inf")
    else:
        artifact_age_hours = max(0.0, (now_ts - last_cycle) / 3600.0)

    last_success = _parse_ts(heartbeat.get("last_success_at"))
    last_success_age_hours = (
        None if last_success is None
        else max(0.0, (now_ts - last_success) / 3600.0)
    )

    return RailsInputs(
        kill_file_present=kill_present,
        heartbeat_status=heartbeat_status,
        heartbeat_alive=heartbeat_alive,
        health_error=health_error,
        weight_saturation_flagged=saturated,
        exchange_anomaly=bool(exchange_anomaly_check()),
        artifact_age_hours=artifact_age_hours,
        last_success_age_hours=last_success_age_hours,
    )


# --------------------------------------------------------------------------
# GATHER: evidence.
# --------------------------------------------------------------------------

def group_rows_by_scope(rows: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        if row.scope:
            grouped.setdefault(row.scope, []).append(row)
    return grouped


def eligible_scopes_from_rows(rows: list[Any]) -> set[str]:
    """Scopes whose emissions are challenger-gated AND promotion-eligible.

    Majority rule per scope, mirroring the readiness runner's challenger-gated
    test: a scope qualifies when most of its rows carry ``challenger_only``
    (promoting an already-fusing champion is a no-op) and most carry the
    emission-stamped ``promotion_eligible=True`` opt-in. Signals that still
    stamp ``promotion_eligible: False`` (or predate the stamp) stay out.
    """
    gated: dict[str, int] = {}
    eligible: dict[str, int] = {}
    total: dict[str, int] = {}
    for row in rows:
        scope = row.scope
        if not scope:
            continue
        features = row.features or {}
        total[scope] = total.get(scope, 0) + 1
        if bool(features.get("challenger_only")):
            gated[scope] = gated.get(scope, 0) + 1
        if bool(features.get("promotion_eligible")):
            eligible[scope] = eligible.get(scope, 0) + 1
    return {
        scope for scope, n in total.items()
        if gated.get(scope, 0) * 2 >= n and eligible.get(scope, 0) * 2 >= n
    }


def clv_by_exact_scope(
    clv_report: Mapping[str, Any], scopes: set[str],
) -> dict[str, dict[str, Any]]:
    """Map the CLV report's ``specialist|market_type`` grain onto exact scopes.

    CLV instrumentation grades per (specialist, market_type) — coarser than the
    exact promotion scope. Each exact scope inherits its specialist's CLV CI;
    scopes whose specialist/market_type pair has no graded clusters simply have
    no CLV evidence (and face the higher no-CLV cluster bar instead).
    """
    report_scopes = clv_report.get("scopes") or {}
    out: dict[str, dict[str, Any]] = {}
    for scope in scopes:
        parts = scope.split("|")
        if len(parts) != 4:
            continue
        source, _subject, market_type, _axis = parts
        entry = report_scopes.get(f"{specialist_for(source)}|{market_type}")
        if not isinstance(entry, dict):
            continue
        lower = entry.get("clv_bps_ci95_lower")
        if lower is None:
            continue
        out[scope] = {
            "mean": entry.get("clv_bps_mean"),
            "lower": lower,
            "upper": entry.get("clv_bps_ci95_upper"),
            "n_event_clusters": entry.get("n_event_clusters"),
            "grain": "specialist|market_type",
        }
    return out


def realized_attribution(
    conn: sqlite3.Connection,
    *,
    forward_registrations: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Receipt-bounded witnessed-fill P&L attributed to exact scopes.

    The top-level attribution remains a share-weighted diagnostic and stage-2
    input. ``forward_evidence`` is much stricter: the candidate must be the
    isolated decision source, its exact fingerprint must have been registered
    before both signal and decision, and one terminal net-P&L row must follow a
    positive fill witness. Only that nested lane can authorize stage 1.
    """
    from autonomy.retention import install_signal_history
    from autonomy.correlation import group_key

    install_signal_history(conn)
    registrations = dict(forward_registrations or {})
    rows = conn.execute(
        """
        SELECT d.decision_id,d.market_ticker,d.sources_used,d.created_at,
               o.pnl_cents,o.created_at,st.settled_at,
               (SELECT MIN(fill.created_at) FROM outcomes fill
                WHERE fill.decision_id=o.decision_id AND fill.id<o.id
                  AND fill.fill_count>0
                  AND fill.kind IN ('SHADOW','PARTIALLY_FILLED','FILLED')) AS fill_at
        FROM outcomes o JOIN decisions d USING(decision_id)
        JOIN settlements st ON st.market_ticker=d.market_ticker
        WHERE o.pnl_cents IS NOT NULL
          AND o.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          AND o.id=(
              SELECT MAX(terminal.id) FROM outcomes terminal
              WHERE terminal.decision_id=o.decision_id
                AND terminal.pnl_cents IS NOT NULL
                AND terminal.kind IN ('SETTLED_WIN','SETTLED_LOSS')
          )
          AND EXISTS (
              SELECT 1 FROM outcomes fill
              WHERE fill.decision_id = o.decision_id
                AND fill.id < o.id AND fill.fill_count > 0
                AND fill.kind IN ('SHADOW','PARTIALLY_FILLED','FILLED')
          )
        """
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for (
        _decision_id, ticker, sources_used_json, decided_at, pnl_cents,
        outcome_at, settled_at, fill_at,
    ) in rows:
        decision_ts = _parse_ts(decided_at)
        fill_ts = _parse_ts(fill_at)
        settlement_ts = _parse_ts(settled_at)
        outcome_ts = _parse_ts(outcome_at)
        if (
            None in {decision_ts, fill_ts, settlement_ts, outcome_ts}
            or not (
                float(decision_ts) <= float(fill_ts)
                <= float(settlement_ts) <= float(outcome_ts)
            )
        ):
            continue
        try:
            shares = json.loads(sources_used_json or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(shares, dict):
            continue
        parsed_shares: dict[str, float] = {}
        invalid_shares = False
        for source, raw_share in shares.items():
            try:
                share = float(raw_share)
            except (TypeError, ValueError):
                invalid_shares = True
                break
            if not math.isfinite(share) or share < 0.0 or share > 1.0:
                invalid_shares = True
                break
            if share > 0.0:
                parsed_shares[str(source)] = share
        if (
            invalid_shares
            or not parsed_shares
            or sum(parsed_shares.values()) > 1.0 + 1e-9
        ):
            continue
        cluster = group_key(str(ticker))
        pnl_dollars = float(pnl_cents) / 100.0
        for source, share in parsed_shares.items():
            feature_row = conn.execute(
                "SELECT features,created_at,ingested_at,mode FROM signal_history"
                " WHERE source=? AND market_ticker=? AND LOWER(mode)='live'"
                " AND julianday(created_at)<=julianday(?)"
                " AND julianday(ingested_at)<=julianday(?)"
                " ORDER BY julianday(created_at) DESC,id DESC LIMIT 1",
                (source, ticker, decided_at, decided_at),
            ).fetchone()
            if feature_row is None:
                continue
            try:
                features = json.loads(feature_row[0])
            except (TypeError, ValueError):
                features = {}
            if not isinstance(features, dict):
                features = {}
            signal_ts = _parse_ts(feature_row[1])
            receipt_ts = _parse_ts(feature_row[2])
            if (
                signal_ts is None or receipt_ts is None
                or signal_ts > decision_ts or receipt_ts > decision_ts
            ):
                continue
            scope = grading_scope(str(source), str(ticker), features)
            entry = out.setdefault(scope, {
                "n_trades": 0,
                "pnl_by_cluster": {},
                "evidence_origin": "ledger_verified",
                "receipt_bounded": True,
                "witnessed_fill_net_pnl": True,
            })
            entry["n_trades"] += 1
            entry["pnl_by_cluster"].setdefault(cluster, []).append(pnl_dollars * share)
            registration = registrations.get(scope)
            if not isinstance(registration, Mapping):
                continue
            registered_ts = _parse_ts(registration.get("registered_at"))
            fingerprint = str(registration.get("candidate_fingerprint") or "").lower()
            if (
                registered_ts is None
                or signal_ts <= registered_ts
                or receipt_ts <= registered_ts
                or decision_ts <= registered_ts
                or str(features.get("promotion_candidate_fingerprint") or "").lower()
                != fingerprint
                or len(parsed_shares) != 1
                or abs(share - 1.0) > 1e-9
            ):
                continue
            forward = entry.setdefault("forward_evidence", {
                "evidence_version": "promotion_forward_fill_v1",
                "evidence_origin": "ledger_verified",
                "receipt_bounded": True,
                "witnessed_fill_net_pnl": True,
                "out_of_sample_after_registration": True,
                "isolated_candidate_decisions": True,
                "registered_at": str(registration["registered_at"]),
                "candidate_fingerprint": fingerprint,
                "n_trades": 0,
                "pnl_by_cluster": {},
                "trade_timestamps": [],
                # Wave-83 honesty: isolated-challenger-lane rows ('chal-')
                # carry a MODELED conservative taker fill at the displayed
                # ask, not a shadow-book-witnessed fill. Any promotion review
                # of this dossier must see that provenance split.
                "fill_provenance": {"modeled_taker": 0, "book_witnessed": 0},
            })
            forward["n_trades"] += 1
            forward["pnl_by_cluster"].setdefault(cluster, []).append(pnl_dollars)
            forward["trade_timestamps"].append(str(decided_at))
            provenance = (
                "modeled_taker"
                if str(_decision_id).startswith("chal-")
                else "book_witnessed"
            )
            forward["fill_provenance"][provenance] += 1
    # Wave-86: make the boolean tell the truth. It was hardcoded True above,
    # so a dossier built entirely from MODELED challenger-lane taker fills
    # still asserted witnessed_fill_net_pnl -- contradicting its own
    # fill_provenance counter two keys away. The flag is the one the promotion
    # gate reads, so the disclosure was decorative. A dossier is witnessed only
    # if every counted fill was book-witnessed.
    for entry in out.values():
        forward = entry.get("forward_evidence")
        if not isinstance(forward, dict):
            continue
        split = forward.get("fill_provenance") or {}
        modeled = int(split.get("modeled_taker", 0))
        witnessed = int(split.get("book_witnessed", 0))
        forward["witnessed_fill_net_pnl"] = modeled == 0 and witnessed > 0
        forward["fill_provenance_grade"] = (
            "book_witnessed" if modeled == 0 and witnessed > 0
            else "modeled_taker" if witnessed == 0
            else "mixed"
        )
    return out


def fused_probs_by_source(
    rows: list[Any], promoted_sources: set[str],
) -> dict[str, dict[str, float]]:
    """Ticker -> mean emitted probability for every source already in fusion.

    Fused = champion (majority of its rows NOT challenger-gated) or the source
    of an actively promoted scope. This is the tape the correlation guard
    compares a candidate against.
    """
    gated: dict[str, int] = {}
    total: dict[str, int] = {}
    tape: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        source = str(row.source)
        total[source] = total.get(source, 0) + 1
        if bool((row.features or {}).get("challenger_only")):
            gated[source] = gated.get(source, 0) + 1
        tape.setdefault(source, {}).setdefault(str(row.ticker), []).append(
            float(row.probability_yes)
        )
    fused_sources = {
        source for source, n in total.items()
        if gated.get(source, 0) * 2 < n  # champions
    } | promoted_sources
    return {
        source: {
            ticker: sum(values) / len(values)
            for ticker, values in tape[source].items()
        }
        for source in fused_sources if source in tape
    }


def load_mined_family_sizes(path: Path) -> dict[str, int]:
    """Scope -> strategy-miner family size (multiple-testing disclosure).

    Written at rule-adoption time (a mined rule shipping as a challenger must
    record ``rules_tested`` for its scope here). Missing file or scope means
    family size 1 — but a scope adopted from mining WITHOUT this record would
    dodge its Bonferroni haircut, so adoption tooling must treat this file as
    mandatory. Values are clamped to >= 1.
    """
    raw = _load_json(path)
    out: dict[str, int] = {}
    for scope, size in raw.items():
        try:
            out[str(scope)] = max(1, int(size))
        except (TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------------
# APPLY.
# --------------------------------------------------------------------------

def _scope_parts(scope: str) -> dict[str, str] | None:
    parts = scope.split("|")
    if len(parts) != 4 or any(not p.strip() for p in parts):
        return None
    return {
        "source": parts[0], "subject": parts[1],
        "market_type": parts[2], "horizon": parts[3],
    }


def apply_result(
    result: EngineResult,
    *,
    promotions_path: Path,
    ledger_path: Path,
    now_iso: str,
    config: PromotionConfig = DEFAULT_CONFIG,
    alert_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Persist decisions: registry file, hash-chained records, alerts.

    Demotions are recorded in the chain and alerted here; the authoritative
    demotion file merge stays with the readiness runner's existing
    ``auto_demotions.json`` path (demotions never un-stick without a human).
    Returns a summary for the dashboard state artifact.
    """
    if alert_fn is None:
        from autonomy.alerts import emit_alert as alert_fn  # pragma: no cover

    ledger = PromotionLedger(ledger_path)
    doc = _load_json(promotions_path)
    entries = [e for e in (doc.get("promotions") or []) if isinstance(e, dict)]
    by_scope: dict[str, dict[str, Any]] = {}
    for entry in entries:
        parts = (entry.get("source"), entry.get("subject"),
                 entry.get("market_type"), entry.get("horizon"))
        if all(parts):
            by_scope["|".join(str(p) for p in parts)] = entry

    applied = {"promoted": [], "escalated": [], "demoted": [],
               "replacement_candidates": [], "human_review_candidates": [],
               "deferred": []}

    for decision in result.promotions:
        parts = _scope_parts(decision.scope)
        if parts is None:
            continue
        record = ledger.append(
            action=ACTION_PROMOTE, scope=decision.scope, at=now_iso,
            payload={"stage": decision.stage,
                     "weight_fraction": decision.weight_fraction,
                     "reason": decision.reason,
                     "thresholds": config.as_dict(),
                     "dossier": decision.dossier},
        )
        by_scope[decision.scope] = {
            **parts,
            "stage": decision.stage,
            "weight_fraction": decision.weight_fraction,
            "promoted_at": now_iso,
            "promoted_by": "auto_promotion_engine",
            "evidence_ref": record.entry_hash,
        }
        alert_fn("AUTO_PROMOTION",
                 f"stage-1 promotion (probation {decision.weight_fraction:.0%}): "
                 f"{decision.scope}",
                 {"scope": decision.scope, "ledger_hash": record.entry_hash}, now_iso)
        applied["promoted"].append(decision.scope)

    for decision in result.escalations:
        record = ledger.append(
            action=ACTION_ESCALATE, scope=decision.scope, at=now_iso,
            payload={"stage": decision.stage,
                     "weight_fraction": decision.weight_fraction,
                     "reason": decision.reason,
                     "thresholds": config.as_dict(),
                     "dossier": decision.dossier},
        )
        entry = by_scope.get(decision.scope)
        if entry is not None:
            entry["stage"] = decision.stage
            entry["weight_fraction"] = decision.weight_fraction
            entry["escalated_at"] = now_iso
            entry["escalation_evidence_ref"] = record.entry_hash
        alert_fn("AUTO_ESCALATION",
                 f"stage-2 escalation (full weight): {decision.scope}",
                 {"scope": decision.scope, "ledger_hash": record.entry_hash}, now_iso)
        applied["escalated"].append(decision.scope)

    for decision in result.demotions:
        record = ledger.append(
            action=ACTION_DEMOTE, scope=decision.scope, at=now_iso,
            payload={"reason": decision.reason,
                     "thresholds": config.as_dict(),
                     "dossier": decision.dossier},
        )
        alert_fn("AUTO_DEMOTION",
                 f"auto-demotion: {decision.scope} ({decision.reason})",
                 {"scope": decision.scope, "ledger_hash": record.entry_hash}, now_iso)
        applied["demoted"].append(decision.scope)

    applied["replacement_candidates"] = [
        d.scope for d in result.replacement_candidates]
    applied["human_review_candidates"] = [
        d.scope for d in result.human_review_candidates]
    applied["deferred"] = [d.scope for d in result.deferred]

    if applied["promoted"] or applied["escalated"]:
        _write_json(promotions_path, {
            "version": 2,
            "promotions": sorted(
                by_scope.values(),
                key=lambda e: (e["source"], e["subject"], e["market_type"], e["horizon"]),
            ),
            "updated_at": now_iso,
        })
    return applied


# --------------------------------------------------------------------------
# The daily run.
# --------------------------------------------------------------------------

def run_auto_promotion(
    db_path: Path,
    *,
    runtime_dir: Path = RUNTIME_DIR,
    now_ts: float | None = None,
    now_iso: str | None = None,
    config: PromotionConfig = DEFAULT_CONFIG,
    exchange_anomaly_check: Callable[[], bool] = _default_exchange_anomaly,
    alert_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """One full gather -> decide -> apply pass. Returns the state summary.

    Every early exit writes the state artifact and (when the chain permits)
    an ABORT record, so a skipped run is always visible on the dashboard.
    """
    if now_ts is None or now_iso is None:
        now = datetime.now(timezone.utc)
        now_ts, now_iso = now.timestamp(), now.isoformat()
    if alert_fn is None:
        from autonomy.alerts import emit_alert as alert_fn

    clv_report, clv_evidence = _usable_optional_clv(runtime_dir, now_ts)

    ledger_path = runtime_dir / "promotion_ledger.jsonl"
    state_path = runtime_dir / "auto_promotion_state.json"
    # Same file the PromotionRegistry defaults to when runtime_dir is the
    # standard runtime/autonomy (DEFAULT_PROMOTIONS_PATH).
    promotions_path = runtime_dir / "promotions.json"

    def _finish(state: dict[str, Any]) -> dict[str, Any]:
        state = {
            "report_name": "AUTO_PROMOTION",
            "generated_at": now_iso,
            "thresholds": config.as_dict(),
            "live_trading_authority": "OPERATOR_ONLY_UNAFFECTED",
            "optional_evidence": {"clv": clv_evidence},
            **state,
        }
        _write_json(state_path, state)
        return state

    # Rail 0: the hash chain itself. Untrustworthy history cannot authorize
    # new risk, and the daily cap cannot be counted against a broken chain.
    ledger = PromotionLedger(ledger_path)
    try:
        used_today = sum(
            1 for entry in ledger.entries_on_date(now_iso)
            if entry.action in (ACTION_PROMOTE, ACTION_ESCALATE)
        )
    except PromotionLedgerError as exc:
        alert_fn("PROMOTION_RUN_ABORTED",
                 f"promotion ledger chain failed verification: {exc}",
                 {"ledger": str(ledger_path)}, now_iso)
        return _finish({"status": "ABORTED", "reasons": ["promotion_ledger_broken"]})

    # Rails 1..n: kill file, heartbeat, health, saturation, exchange, staleness.
    weights: dict[str, float] = {}
    if Path(db_path).exists():
        try:
            from autonomy.ledger import AutonomyLedger

            autonomy_ledger = AutonomyLedger(db_path=db_path)
            try:
                weights = autonomy_ledger.all_weights()
            finally:
                autonomy_ledger.close()
        except Exception:
            weights = {}
    rails_inputs = gather_rails_inputs(
        runtime_dir, now_ts, weights=weights,
        exchange_anomaly_check=exchange_anomaly_check,
    )
    rails = evaluate_rails(rails_inputs)
    if rails.abort:
        ledger.append(action=ACTION_ABORT, scope="*", at=now_iso,
                      payload={"rails": rails.to_dict()})
        alert_fn("PROMOTION_RUN_ABORTED",
                 "promotion run aborted on rails: " + ", ".join(rails.reasons),
                 rails.to_dict(), now_iso)
        return _finish({"status": "ABORTED", "reasons": rails.reasons})

    if not Path(db_path).exists():
        return _finish({"status": "NO_DB", "db": str(db_path)})

    # GATHER evidence.
    from autonomy.strategy_miner import load_settled_rows

    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    try:
        rows = load_settled_rows(conn)
        forward_registrations = load_forward_registrations(
            runtime_dir / FORWARD_REGISTRATIONS_PATH.name
        )
        realized = realized_attribution(
            conn, forward_registrations=forward_registrations,
        )
    finally:
        conn.close()

    scope_rows = group_rows_by_scope(rows)
    eligible = eligible_scopes_from_rows(rows)
    clv = clv_by_exact_scope(clv_report, set(scope_rows))
    mined_families = load_mined_family_sizes(runtime_dir / "mined_scope_families.json")

    registry = PromotionRegistry(promotions_path, runtime_dir / "auto_demotions.json")
    snapshot = registry.snapshot()
    promoted = {
        scope: {"stage": snapshot["stages"].get(scope, 2)}
        for scope in snapshot["active"]
    }
    promoted_sources = {scope.split("|", 1)[0] for scope in promoted}
    fused_tape = fused_probs_by_source(rows, promoted_sources)

    # DECIDE.
    engine = AutoPromotionEngine(config)
    result = engine.decide(
        scope_rows=scope_rows,
        promoted=promoted,
        now_ts=now_ts,
        now_iso=now_iso,
        rails=rails,
        promotions_used_today=used_today,
        clv_by_scope=clv,
        realized_by_scope=realized,
        eligible_scopes=eligible,
        mined_family_sizes=mined_families,
        fused_probs_by_source=fused_tape,
    )

    # APPLY.
    applied = apply_result(
        result,
        promotions_path=promotions_path,
        ledger_path=ledger_path,
        now_iso=now_iso,
        config=config,
        alert_fn=alert_fn,
    )
    # Wave-19: declined-but-eligible scopes keep their FULL dossiers in a
    # dedicated artifact (dashboard/forensics readable; not the hash chain --
    # declines are evidence snapshots, not risk actions) and a compact
    # {scope, reason} list rides the state summary. Diagnosing "why didn't X
    # promote" is now a file read, not an evening of re-derivation.
    _write_json(runtime_dir / "promotion_declines.json", {
        "generated_at": now_iso,
        "declined": [d.to_dict() for d in result.declined],
    })
    applied["declined"] = [
        {"scope": d.scope, "reason": d.reason} for d in result.declined
    ]
    _write_json(runtime_dir / "promotion_human_review_candidates.json", {
        "generated_at": now_iso,
        "automatic_promotion_authority": False,
        "candidates": [d.to_dict() for d in result.human_review_candidates],
    })
    applied["human_review_candidates"] = [
        {"scope": d.scope, "reason": d.reason}
        for d in result.human_review_candidates
    ]
    # Engine demotions also land in the sticky auto_demotions.json file the
    # registry honors (same merge discipline as the readiness runner: a
    # demotion never un-sticks without a human).
    if applied["demoted"]:
        demotions_path = runtime_dir / "auto_demotions.json"
        existing = _load_json(demotions_path)
        merged: dict[str, dict[str, Any]] = {}
        for entry in (existing.get("demotions") or []):
            if isinstance(entry, dict) and entry.get("scope"):
                merged[str(entry["scope"])] = entry
        for scope in applied["demoted"]:
            merged.setdefault(scope, {
                "scope": scope, "detected_at": now_iso,
                "reason": "auto_promotion_engine trailing CI breach",
            })
        _write_json(demotions_path, {
            "demotions": sorted(merged.values(), key=lambda e: e["scope"]),
            "generated_at": now_iso,
        })

    return _finish({
        "status": "OK",
        "scopes_evaluated": len(scope_rows),
        "eligible_scopes": len(eligible),
        "forward_registrations": len(forward_registrations),
        "promotions_used_today_before_run": used_today,
        **applied,
    })


__all__ = [
    "gather_rails_inputs",
    "group_rows_by_scope",
    "eligible_scopes_from_rows",
    "clv_by_exact_scope",
    "load_forward_registrations",
    "realized_attribution",
    "fused_probs_by_source",
    "load_mined_family_sizes",
    "apply_result",
    "run_auto_promotion",
    "PROMOTION_LEDGER_PATH",
    "STATE_PATH",
    "MINED_FAMILIES_PATH",
]
