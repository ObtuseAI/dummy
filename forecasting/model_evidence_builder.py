"""Panel -> authority evidence on-ramp (measurement only; never promotion).

The model probability authority registry (forecasting/model_probability_
authority.py) grants a bounded (<=0.35) model weight to an exact scope ONLY
when a dossier promotion entry references a canonical forward-calibration
evidence artifact that passes every gate: >=300 independent event clusters,
receipt-bounded + point-in-time + forward, zero retro rows, Brier-edge CI95
lower bound > 0, freshness <= 7d.

This builder is the honest producer of that evidence artifact. It reads the
settled ``llm_debate`` aggregate rows (the bounded panel probability of
record), computes the per-scope forward stats the artifact requires, and:

  * writes the canonical evidence artifact (INERT: it grants nothing on its
    own -- authority requires a dossier promotion entry, which this builder
    deliberately never writes), and
  * writes an eligibility report showing how far each scope is from the 300-
    cluster / positive-CI bar.

Authoring the authority dossier remains an explicit governance action. This
gives arming the panel an observable purpose (accumulate forward evidence,
watch the eligibility report) without any path to self-granted authority.
"""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forecasting.model_probability_authority import (
    EXPECTED_PROVIDER_MODELS,
    MAX_MODEL_PROBABILITY_WEIGHT,
    MIN_INDEPENDENT_EVENT_CLUSTERS,
    MODEL_EVIDENCE_MODE,
    MODEL_EVIDENCE_SCHEMA,
    model_probability_scope,
)

DEBATE_SOURCE = "llm_debate"
EVIDENCE_ARTIFACT_PATH = Path("artifacts/dummy/model_probability_forward_calibration_v1.json")
ELIGIBILITY_REPORT_PATH = Path("runtime/autonomy/model_authority_eligibility.json")
BOOTSTRAP_ROUNDS = 1000


def _brier(prob: float, result_yes: bool) -> float:
    outcome = 1.0 if result_yes else 0.0
    return (prob - outcome) ** 2


def _parse_ts(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _cluster_ci95(
    diffs_by_cluster: dict[str, list[float]],
) -> tuple[float, float] | None:
    clusters = [values for values in diffs_by_cluster.values() if values]
    if len(clusters) < 2:
        return None
    rng = random.Random(20260723)
    means: list[float] = []
    for _ in range(BOOTSTRAP_ROUNDS):
        sample: list[float] = []
        for _ in range(len(clusters)):
            sample.extend(rng.choice(clusters))
        means.append(sum(sample) / len(sample))
    means.sort()
    return (
        round(means[int(0.025 * (len(means) - 1))], 8),
        round(means[int(0.975 * (len(means) - 1))], 8),
    )


def _scope_for_row(
    ticker: str, features: dict[str, Any], decision_at: datetime,
) -> str | None:
    title = str(features.get("title") or features.get("market_title") or "")
    category = str(features.get("market_category") or features.get("category") or "")
    expiration = _parse_ts(features.get("close_time") or features.get("expiration"))
    live_phase = features.get("live_phase")
    if not isinstance(live_phase, bool):
        live_phase = None
    try:
        return model_probability_scope(
            ticker=ticker, title=title, category=category,
            decision_at=decision_at, expiration=expiration, live_phase=live_phase,
        )
    except Exception:  # noqa: BLE001
        return None


def build_scope_evidence(
    conn: sqlite3.Connection, *, evidence_start: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Per authority-scope forward Brier-edge evidence from llm_debate rows."""
    from autonomy.retention import install_signal_history

    install_signal_history(conn)
    rows = conn.execute(
        """
        SELECT s.market_ticker, s.probability_yes, s.features, s.created_at,
               t.result_yes,
               (SELECT m.probability_yes FROM signal_history m
                WHERE m.market_ticker = s.market_ticker
                  AND m.source = 'market_prior'
                  AND m.created_at <= s.created_at
                ORDER BY m.created_at DESC LIMIT 1) AS market_prob
        FROM signal_history s
        JOIN settlements t ON t.market_ticker = s.market_ticker
        WHERE s.source = ? AND s.mode = 'live'
        """,
        (DEBATE_SOURCE,),
    ).fetchall()

    scopes: dict[str, dict[str, Any]] = {}
    for ticker, prob, features_json, created_at, result_yes, market_prob in rows:
        if market_prob is None:
            continue
        decision_at = _parse_ts(created_at)
        if decision_at is None:
            continue
        if evidence_start is not None and decision_at < evidence_start:
            continue
        try:
            features = json.loads(features_json) if features_json else {}
        except (TypeError, ValueError):
            features = {}
        if not isinstance(features, dict):
            features = {}
        scope = _scope_for_row(str(ticker), features, decision_at)
        if scope is None or scope.rsplit("|", 1)[-1] == "unknown":
            continue
        from autonomy.correlation import group_key

        cluster = group_key(str(ticker))
        edge = _brier(float(market_prob), bool(result_yes)) - _brier(
            float(prob), bool(result_yes),
        )
        bucket = scopes.setdefault(scope, {
            "edges_by_cluster": {},
            "received_through": decision_at,
        })
        bucket["edges_by_cluster"].setdefault(cluster, []).append(edge)
        if decision_at > bucket["received_through"]:
            bucket["received_through"] = decision_at
    return scopes


def _earned_weight(ci_low: float) -> str:
    """Conservative weight proposal, hard-capped. Only meaningful if a dossier
    ever references it AND the scope passes every gate; inert otherwise."""
    from decimal import Decimal

    proposal = min(Decimal(str(max(0.0, ci_low) * 4)), MAX_MODEL_PROBABILITY_WEIGHT)
    return str(proposal.quantize(Decimal("0.0001")))


def build_and_write(
    db_path: Path | str,
    *,
    evidence_start: datetime | None = None,
    now: datetime | None = None,
    artifact_path: Path | str = EVIDENCE_ARTIFACT_PATH,
    report_path: Path | str = ELIGIBILITY_REPORT_PATH,
) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        raw_scopes = build_scope_evidence(conn, evidence_start=evidence_start)
    finally:
        conn.close()

    artifact_scopes: dict[str, Any] = {}
    eligibility: list[dict[str, Any]] = []
    for scope, bucket in sorted(raw_scopes.items()):
        edges = bucket["edges_by_cluster"]
        cluster_ids = sorted(edges)
        n_clusters = len(cluster_ids)
        ci = _cluster_ci95(edges)
        ci_low, ci_high = (ci if ci is not None else (None, None))
        computed_at = now_utc.isoformat()
        received_through = bucket["received_through"].isoformat()
        row = {
            "forward_calibrated": True,
            "receipt_bounded": True,
            "point_in_time": True,
            "retro_rows_included": 0,
            "independent_event_clusters": n_clusters,
            "independent_event_cluster_ids": cluster_ids,
            "computed_at": computed_at,
            "received_through": received_through,
            "brier_edge_ci95": {
                "lower": ci_low if ci_low is not None else 0.0,
                "upper": ci_high if ci_high is not None else 0.0,
            },
            "earned_weight": _earned_weight(ci_low if ci_low is not None else 0.0),
        }
        artifact_scopes[scope] = row
        eligible = (
            n_clusters >= MIN_INDEPENDENT_EVENT_CLUSTERS
            and ci_low is not None and ci_low > 0.0
        )
        blockers = []
        if n_clusters < MIN_INDEPENDENT_EVENT_CLUSTERS:
            blockers.append(f"clusters_{n_clusters}_below_{MIN_INDEPENDENT_EVENT_CLUSTERS}")
        if ci_low is None or ci_low <= 0.0:
            blockers.append("brier_edge_ci95_lower_not_positive")
        eligibility.append({
            "scope": scope,
            "independent_event_clusters": n_clusters,
            "brier_edge_ci95_lower": ci_low,
            "governance_eligible": eligible,
            "blockers": blockers,
        })

    artifact = {
        "schema_version": MODEL_EVIDENCE_SCHEMA,
        "artifact_type": MODEL_EVIDENCE_SCHEMA,
        "evidence_mode": MODEL_EVIDENCE_MODE,
        "provider_models": sorted(EXPECTED_PROVIDER_MODELS),
        "generated_at": now_utc.isoformat(),
        "promotion_authority": False,
        "scopes": artifact_scopes,
    }
    artifact_target = Path(artifact_path)
    artifact_target.parent.mkdir(parents=True, exist_ok=True)
    artifact_bytes = json.dumps(artifact, indent=2, sort_keys=True).encode("utf-8")
    tmp = artifact_target.with_suffix(".tmp")
    tmp.write_bytes(artifact_bytes)
    tmp.replace(artifact_target)
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()

    report = {
        "report_version": "model_authority_eligibility_v1",
        "generated_at": now_utc.isoformat(),
        "evidence_artifact": str(artifact_target),
        "evidence_artifact_sha256": artifact_sha256,
        "dossier_authored": False,
        "authority_note": (
            "Evidence artifact is inert: model probability authority requires a "
            "separately, explicitly authored dossier promotion entry that "
            "references this artifact's sha256 AND passes every registry gate. "
            "This builder never authors that dossier."
        ),
        "scopes": sorted(eligibility, key=lambda item: -item["independent_event_clusters"]),
        "governance_eligible_scopes": [
            item["scope"] for item in eligibility if item["governance_eligible"]
        ],
    }
    report_target = Path(report_path)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_target.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(report_target)
    return report
