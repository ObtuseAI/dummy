"""Forward-paper issuance and grading for frozen autoresearch candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomy.correlation import group_key
from dummy.genome import ForecastGenome
from dummy.world_model.models import digest_json

from .candidate_replay import (
    GenomeReplayPolicy,
    measure_genome_complexity,
    replay_task,
)
from .experiment_ledger import ExperimentLedger
from .external_evaluator import evaluate_external_generalization
from .ledger_pipeline import connect_ledger_readonly, load_ledger_evidence
from .models import EvaluationPartition, iso, utc


@dataclass(frozen=True, slots=True)
class ForwardDecisionInput:
    decision_id: str
    market_ticker: str
    event_cluster_id: str
    decision_at: datetime
    incumbent_probability: float
    market_prior_probability: float
    forecast_uncertainty: float
    action: str
    side: str
    price_cents: int
    count: int
    source_family_ids: tuple[str, ...]
    input_digest: str


_UNSETTLED_QUERY = """
WITH ranked AS (
    SELECT d.*,
           ROW_NUMBER() OVER (
               PARTITION BY d.market_ticker
               ORDER BY d.created_at,d.decision_id
           ) AS row_number
    FROM decisions d
    LEFT JOIN settlements s USING(market_ticker)
    WHERE s.market_ticker IS NULL
      AND d.market_implied_yes IS NOT NULL
      AND d.market_ticker LIKE ?
      AND d.created_at>?
)
SELECT * FROM ranked WHERE row_number=1 ORDER BY created_at,decision_id
"""


def load_unsettled_forward_inputs(
    ledger_path: Path,
    *,
    ticker_prefix: str,
    epoch_started_at: datetime,
    issued_at: datetime,
) -> tuple[ForwardDecisionInput, ...]:
    connection = connect_ledger_readonly(ledger_path)
    try:
        records = connection.execute(
            _UNSETTLED_QUERY,
            (f"{ticker_prefix.upper()}%", iso(epoch_started_at)),
        ).fetchall()
    finally:
        connection.close()
    issued = utc(issued_at)
    rows: list[ForwardDecisionInput] = []
    for record in records:
        try:
            decision_at = utc(record["created_at"])
            incumbent = float(record["probability_yes"])
            market = float(record["market_implied_yes"])
            uncertainty = float(record["forecast_uncertainty"])
            sources = json.loads(record["sources_used"] or "{}")
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if decision_at > issued or not (0.0 < incumbent < 1.0 and 0.0 < market < 1.0):
            continue
        if not isinstance(sources, dict) or not sources:
            continue
        source_families = tuple(sorted(str(key) for key in sources if str(key)))
        input_payload = {
            "decision_id": str(record["decision_id"]),
            "market_ticker": str(record["market_ticker"]),
            "decision_at": iso(decision_at),
            "incumbent_probability": incumbent,
            "market_prior_probability": market,
            "forecast_uncertainty": uncertainty,
            "action": str(record["action"]),
            "side": str(record["side"]),
            "price_cents": int(record["price_cents"]),
            "count": int(record["count"]),
            "source_family_ids": list(source_families),
        }
        rows.append(
            ForwardDecisionInput(
                decision_id=str(record["decision_id"]),
                market_ticker=str(record["market_ticker"]),
                event_cluster_id=group_key(str(record["market_ticker"])),
                decision_at=decision_at,
                incumbent_probability=incumbent,
                market_prior_probability=market,
                forecast_uncertainty=uncertainty,
                action=str(record["action"]),
                side=str(record["side"]),
                price_cents=int(record["price_cents"]),
                count=int(record["count"]),
                source_family_ids=source_families,
                input_digest=digest_json(input_payload),
            )
        )
    return tuple(rows)


def build_forward_registry(
    campaign: dict[str, Any],
    *,
    base_genome: ForecastGenome,
    ticker_prefix: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if existing and existing.get("active_candidate"):
        return existing
    best_id = campaign.get("best_forward_candidate_id")
    selected = next(
        (
            item
            for item in campaign.get("candidates", [])
            if (item.get("candidate_genome") or {}).get("genome_id") == best_id
            and item.get("forward_paper_eligible") is True
        ),
        None,
    )
    active = None
    if selected is not None:
        candidate = ForecastGenome.from_dict(selected["candidate_genome"])
        policy = GenomeReplayPolicy.from_genomes(
            candidate=candidate,
            base=base_genome,
            lineage_id=str(selected["lineage_id"]),
        )
        active = {
            "candidate_genome": candidate.to_dict(),
            "base_genome": base_genome.to_dict(),
            "lineage_id": selected["lineage_id"],
            "policy": policy.semantic_dict(),
            "epoch_started_at": campaign["evidence_cutoff"],
            "source_campaign_id": campaign["campaign_id"],
            "ticker_prefix": ticker_prefix,
            "scope": campaign["scope"],
        }
    body: dict[str, Any] = {
        "schema_version": 1,
        "status": (
            "ACTIVE_FORWARD_PAPER_OBSERVATION"
            if active is not None
            else "NO_ELIGIBLE_CANDIDATE"
        ),
        "active_candidate": active,
        "candidate_rotation": "STICKY_UNTIL_HUMAN_REVIEW_OR_DIVERSE_FAILURE",
        "orders_placed": False,
        "broker_contact": False,
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "execution_authority": False,
        "capital_authority": False,
    }
    body["registry_id"] = digest_json(body)
    return body


def issue_forward_observations(
    registry: dict[str, Any],
    *,
    ledger_path: Path,
    observation_ledger_path: Path,
    issued_at: datetime,
) -> dict[str, Any]:
    active = registry.get("active_candidate")
    if not active:
        return {
            "registry_id": registry["registry_id"],
            "status": "NO_ELIGIBLE_CANDIDATE",
            "new_observations": 0,
            "total_observations": 0,
            "orders_placed": False,
            "execution_authority": False,
        }
    candidate = ForecastGenome.from_dict(active["candidate_genome"])
    base = ForecastGenome.from_dict(active["base_genome"])
    policy = GenomeReplayPolicy.from_genomes(
        candidate=candidate,
        base=base,
        lineage_id=str(active["lineage_id"]),
    )
    rows = load_unsettled_forward_inputs(
        ledger_path,
        ticker_prefix=str(active["ticker_prefix"]),
        epoch_started_at=utc(active["epoch_started_at"]),
        issued_at=issued_at,
    )
    ledger = ExperimentLedger(observation_ledger_path)
    existing = ledger.read_verified()
    seen_decisions = {
        str(entry.payload.get("decision_id")) for entry in existing
    }
    appended = 0
    for row in rows:
        if row.decision_id in seen_decisions:
            continue
        candidate_probability, abstain_reason = policy.decision(row)  # type: ignore[arg-type]
        payload = {
            "schema_version": 1,
            "registry_id": registry["registry_id"],
            "source_campaign_id": active["source_campaign_id"],
            "candidate_genome_id": candidate.genome_id,
            "lineage_id": active["lineage_id"],
            "decision_id": row.decision_id,
            "market_ticker": row.market_ticker,
            "event_cluster_id": row.event_cluster_id,
            "decision_at": iso(row.decision_at),
            "issued_at": iso(issued_at),
            "input_digest": row.input_digest,
            "candidate_probability": candidate_probability,
            "candidate_abstained": candidate_probability is None,
            "abstain_reason": abstain_reason,
            "settlement_known_at_issue": False,
            "result_known_at_issue": False,
            "order_proposed": False,
            "order_placed": False,
            "execution_authority": False,
        }
        observation_id = digest_json(payload)
        ledger.append(observation_id, payload)
        seen_decisions.add(row.decision_id)
        appended += 1
    total = len(ledger.read_verified())
    return {
        "registry_id": registry["registry_id"],
        "status": "FORWARD_OBSERVATIONS_ISSUED",
        "issued_at": iso(issued_at),
        "new_observations": appended,
        "total_observations": total,
        "orders_placed": False,
        "broker_contact": False,
        "execution_authority": False,
    }


def grade_forward_observations(
    registry: dict[str, Any],
    *,
    ledger_path: Path,
    observation_ledger_path: Path,
) -> dict[str, Any]:
    active = registry.get("active_candidate")
    if not active or not observation_ledger_path.exists():
        return {
            "registry_id": registry["registry_id"],
            "status": "ACCUMULATING_FORWARD_EVIDENCE",
            "issued_observations": 0,
            "forward_paper_candidate_settlements": 0,
            "event_clusters": 0,
            "verified_settled_fills": 0,
            "external_evaluation": None,
            "ready_for_human_promotion_review": False,
            "performance_claim_supported": False,
            "execution_authority": False,
        }
    candidate = ForecastGenome.from_dict(active["candidate_genome"])
    base = ForecastGenome.from_dict(active["base_genome"])
    policy = GenomeReplayPolicy.from_genomes(
        candidate=candidate,
        base=base,
        lineage_id=str(active["lineage_id"]),
    )
    observations = ExperimentLedger(observation_ledger_path).read_verified()
    by_decision = {
        str(entry.payload["decision_id"]): entry.payload for entry in observations
    }
    settled_rows = load_ledger_evidence(
        ledger_path,
        ticker_prefix=str(active["ticker_prefix"]),
        decision_after=utc(active["epoch_started_at"]),
    )
    tasks = []
    invalid_after_settlement = 0
    replay_mismatches = 0
    for row in settled_rows:
        observation = by_decision.get(row.decision_id)
        if observation is None:
            continue
        if utc(observation["issued_at"]) >= row.settlement_received_at:
            invalid_after_settlement += 1
            continue
        task = replay_task(
            row,
            partition=EvaluationPartition.EXTERNAL_GENERALIZATION,
            policy=policy,
        )
        if (
            task.candidate_probability != observation.get("candidate_probability")
            or task.candidate_abstained is not observation.get("candidate_abstained")
        ):
            replay_mismatches += 1
            continue
        tasks.append(task)
    external = None
    if tasks:
        external = evaluate_external_generalization(
            candidate.genome_id,
            tuple(tasks),
            complexity_profile=measure_genome_complexity(base, candidate),
        )
    clusters = len({task.event_cluster_id for task in tasks})
    fills = sum(task.candidate_fill_verified for task in tasks)
    ready = bool(
        external
        and external.accepted
        and len(tasks) >= 100
        and clusters >= 10
        and fills >= 5
        and invalid_after_settlement == 0
        and replay_mismatches == 0
    )
    return {
        "registry_id": registry["registry_id"],
        "status": (
            "READY_FOR_HUMAN_PROMOTION_REVIEW"
            if ready
            else "ACCUMULATING_FORWARD_EVIDENCE"
        ),
        "issued_observations": len(observations),
        "forward_paper_candidate_settlements": len(tasks),
        "event_clusters": clusters,
        "verified_settled_fills": fills,
        "invalid_observations_issued_after_settlement": invalid_after_settlement,
        "deterministic_replay_mismatches": replay_mismatches,
        "external_evaluation": external.to_dict() if external else None,
        "minimums": {
            "settled_observations": 100,
            "event_clusters": 10,
            "verified_settled_fills": 5,
            "positive_external_gates": True,
        },
        "ready_for_human_promotion_review": ready,
        "performance_claim_supported": ready,
        "orders_placed": False,
        "broker_contact": False,
        "automatic_promotion": False,
        "execution_authority": False,
        "capital_authority": False,
    }


def write_forward_artifact(value: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


__all__ = [
    "ForwardDecisionInput",
    "build_forward_registry",
    "grade_forward_observations",
    "issue_forward_observations",
    "load_unsettled_forward_inputs",
    "write_forward_artifact",
]
