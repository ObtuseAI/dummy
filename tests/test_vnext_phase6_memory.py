from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from dummy.memory import (
    EvidenceReality,
    InMemoryMemoryLedger,
    JsonlMemoryLedger,
    MemoryKind,
    MemoryRecord,
    MemoryValidationError,
    theory_memory,
)


NOW = datetime(2026, 7, 15, 2, 0, tzinfo=timezone.utc)


def _record(
    entity: str,
    *,
    recorded_at: datetime = NOW,
    parents: tuple[str, ...] = (),
) -> MemoryRecord:
    return MemoryRecord.create(
        kind=MemoryKind.OBSERVATION,
        entity_id=entity,
        event_cluster_id="cluster-1",
        observed_at=NOW - timedelta(seconds=2),
        received_at=NOW - timedelta(seconds=1),
        recorded_at=recorded_at,
        source="public-test-source",
        source_reference=f"fixture://{entity}",
        evidence_reality=EvidenceReality.PUBLIC_OBSERVATION,
        provenance_verified=True,
        causal_parent_ids=parents,
        evidence_ids=(f"evidence-{entity}",),
        payload={"value": entity},
    )


def test_memory_is_content_addressed_immutable_and_round_trips() -> None:
    record = _record("observation-1")
    assert len(record.memory_id) == 64
    assert MemoryRecord.from_dict(record.to_dict()) == record
    assert MemoryRecord.create(
        kind=record.kind,
        entity_id=record.entity_id,
        event_cluster_id=record.event_cluster_id,
        observed_at=record.observed_at,
        received_at=record.received_at,
        recorded_at=record.recorded_at,
        source=record.source,
        source_reference=record.source_reference,
        evidence_reality=record.evidence_reality,
        provenance_verified=record.provenance_verified,
        causal_parent_ids=record.causal_parent_ids,
        evidence_ids=record.evidence_ids,
        payload=record.payload,
    ) == record
    tampered = record.to_dict()
    tampered["payload"]["value"] = "rewritten"
    with pytest.raises(MemoryValidationError, match="memory_id"):
        MemoryRecord.from_dict(tampered)


def test_hash_chain_is_idempotent_causal_and_time_monotonic() -> None:
    ledger = InMemoryMemoryLedger()
    first = _record("first")
    second = _record(
        "second",
        recorded_at=NOW + timedelta(seconds=1),
        parents=(first.memory_id,),
    )
    assert ledger.append(first) == first.memory_id
    assert ledger.append(first) == first.memory_id
    assert ledger.append(second) == second.memory_id
    assert len(ledger.entries()) == 2
    assert ledger.entries()[1].previous_entry_hash == ledger.entries()[0].entry_hash
    with pytest.raises(MemoryValidationError, match="unknown causal"):
        InMemoryMemoryLedger().append(second)
    backwards = _record(
        "backwards",
        recorded_at=NOW - timedelta(milliseconds=1),
    )
    with pytest.raises(MemoryValidationError, match="backwards"):
        ledger.append(backwards)


def test_jsonl_memory_detects_noncanonical_or_tampered_rows(tmp_path: Path) -> None:
    path = tmp_path / "memory.jsonl"
    ledger = JsonlMemoryLedger(path)
    record = _record("persisted")
    ledger.append(record)
    assert ledger.get(record.memory_id) == record
    row = json.loads(path.read_text(encoding="utf-8"))
    row["record"]["payload"]["value"] = "tampered"
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(MemoryValidationError, match="invalid memory ledger row"):
        ledger.entries()


def test_realized_truth_cannot_use_unverified_provenance() -> None:
    with pytest.raises(MemoryValidationError, match="verified provenance"):
        MemoryRecord.create(
            kind=MemoryKind.FILL,
            entity_id="fake-fill",
            event_cluster_id="cluster",
            observed_at=NOW,
            received_at=NOW,
            recorded_at=NOW,
            source="fake",
            source_reference="fixture://fake",
            evidence_reality=EvidenceReality.WITNESSED_FILL,
            provenance_verified=False,
            causal_parent_ids=(),
            evidence_ids=("fake",),
            payload={"witnessed": False},
        )


def test_theory_memory_never_turns_repetition_into_promotion() -> None:
    theory = theory_memory(
        theory_id="weekend-liquidity",
        statement="Weekend liquidity may widen forecast uncertainty.",
        proposed_at=NOW,
        recorded_at=NOW,
        event_cluster_ids=("cluster-a", "cluster-b"),
        evidence_ids=("evidence-a", "evidence-b"),
        causal_parent_ids=(),
    )
    assert theory.evidence_reality is EvidenceReality.DERIVED
    assert theory.payload["support_state"] == "REPEATED_EVIDENCE_NOT_CAUSAL_PROOF"
    assert theory.payload["promotion_eligible"] is False
