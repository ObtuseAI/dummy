"""Deterministically project one dissolved organism episode into layered memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dummy.organisms.models import (
    EpisodeArtifact,
    PointInTimeEvidence,
    VerifiedSettlement,
    parse_iso,
)

from .calibration import calibration_memory
from .episodes import episode_memory
from .failures import FailureKind, failure_memory
from .fills import FillOutcome, fill_memory
from .observations import observation_memory
from .schema import MemoryRecord
from .settlements import settlement_memory
from .store import MemorySink
from .strategies import strategy_memory


@dataclass(frozen=True, slots=True)
class EpisodeMemoryBundle:
    episode_id: str
    records: tuple[MemoryRecord, ...]

    @property
    def memory_ids(self) -> tuple[str, ...]:
        return tuple(record.memory_id for record in self.records)


def episode_memory_bundle(
    artifact: EpisodeArtifact,
    *,
    recorded_at: datetime,
) -> EpisodeMemoryBundle:
    payload = artifact.to_dict()
    issue = payload["issue_request"]
    cluster = str(payload["event_cluster_id"])
    observations = tuple(
        observation_memory(
            PointInTimeEvidence.from_dict(item),
            recorded_at=parse_iso(payload["decision_at"]),
            event_cluster_id=cluster,
        )
        for item in issue["evidence"]
    )
    observation_ids = tuple(item.memory_id for item in observations)
    settlement = VerifiedSettlement.from_dict(payload["settlement"])
    settled = settlement_memory(
        settlement,
        recorded_at=recorded_at,
        causal_parent_ids=observation_ids,
    )
    execution = payload["shadow_execution"]
    fill_count = int(execution["fill_count"])
    requested = int(execution["requested_count"])
    outcome = (
        FillOutcome.ORDER_UNFILLED
        if fill_count == 0
        else FillOutcome.ORDER_FILLED
        if fill_count == requested
        else FillOutcome.ORDER_PARTIALLY_FILLED
    )
    decision = payload["decision"]
    fill = fill_memory(
        fill_id=f"{artifact.episode_id}:shadow-fill",
        event_cluster_id=cluster,
        observed_at=parse_iso(payload["decision_at"]),
        received_at=parse_iso(payload["decision_at"]),
        recorded_at=recorded_at,
        source="dummy-vnext-shadow-execution",
        source_reference=f"episode://{artifact.episode_id}/shadow-fill",
        outcome=outcome,
        witnessed=False,
        simulated=True,
        quantity=fill_count,
        price_cents=(
            int(execution["price_cents"]) if fill_count > 0 else None
        ),
        fee_cents=int(execution["fee_cents"]),
        slippage_cents=None,
        evidence_ids=tuple(decision["message"]["evidence_ids"]),
        causal_parent_ids=observation_ids,
        details={
            **execution,
            "settlement_grade": payload["settlement"]["shadow_fill_grade"],
        },
    )
    episode = episode_memory(
        artifact,
        recorded_at=recorded_at,
        causal_parent_ids=(*observation_ids, settled.memory_id, fill.memory_id),
    )
    probability = float(decision["candidate_probability"])
    calibration = calibration_memory(
        calibration_id=f"{artifact.episode_id}:calibration",
        event_cluster_id=cluster,
        probability_yes=probability,
        result_yes=settlement.result_yes,
        model_version=str(decision["message"]["model_version"]),
        calibration_version=str(payload["policy_version"]),
        settled_at=settlement.settled_at,
        received_at=settlement.received_at,
        recorded_at=recorded_at,
        settlement_source_reference=settlement.source_reference,
        evidence_ids=(artifact.episode_id, settlement.source_reference),
        causal_parent_ids=(episode.memory_id, settled.memory_id),
    )
    market_probability = float(decision["market_prior_probability"])
    outcome_value = float(settlement.result_yes)
    strategy = strategy_memory(
        strategy_id=str(payload["template"]["template_id"]),
        vertical=str(payload["vertical"]),
        market_type=str(payload["market_type"]),
        regime=str(payload["clock_domain"]),
        evaluated_at=settlement.settled_at,
        recorded_at=recorded_at,
        settled_event_clusters=1,
        metrics={
            "candidate_brier": round((probability - outcome_value) ** 2, 12),
            "market_prior_brier": round(
                (market_probability - outcome_value) ** 2,
                12,
            ),
        },
        claim_supported=False,
        evidence_ids=(artifact.episode_id, settlement.source_reference),
        causal_parent_ids=(episode.memory_id, calibration.memory_id),
    )
    records: list[MemoryRecord] = [
        *observations,
        settled,
        fill,
        episode,
        calibration,
    ]
    decision_kind = str(decision["decision_kind"])
    forecast_correct = (
        decision_kind == "FORECAST_YES" and settlement.result_yes
    ) or (decision_kind == "FORECAST_NO" and not settlement.result_yes)
    if decision_kind.startswith("FORECAST_") and not forecast_correct:
        records.append(
            failure_memory(
                failure_id=f"{artifact.episode_id}:forecast-error",
                event_cluster_id=cluster,
                occurred_at=settlement.settled_at,
                recorded_at=recorded_at,
                kind=FailureKind.FORECAST_ERROR,
                reason="issued_forecast_did_not_match_verified_settlement",
                source_reference=settlement.source_reference,
                evidence_ids=(artifact.episode_id, settlement.source_reference),
                causal_parent_ids=(episode.memory_id, calibration.memory_id),
                reversible=True,
                details={"decision_kind": decision_kind},
            )
        )
    records.append(strategy)
    return EpisodeMemoryBundle(
        episode_id=artifact.episode_id,
        records=tuple(records),
    )


def archive_episode_memories(
    artifact: EpisodeArtifact,
    *,
    recorded_at: datetime,
    ledger: MemorySink,
) -> EpisodeMemoryBundle:
    bundle = episode_memory_bundle(artifact, recorded_at=recorded_at)
    for record in bundle.records:
        if ledger.append(record) != record.memory_id:
            raise RuntimeError("memory ledger returned a mismatched record ID")
    return bundle


__all__ = [
    "EpisodeMemoryBundle",
    "archive_episode_memories",
    "episode_memory_bundle",
]
