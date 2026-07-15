from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dummy.protocols import MessageEnvelope, MessageType
from dummy.shadows import GuardAction, GuardContext, review_context


NOW = datetime(2026, 7, 15, 1, 0, tzinfo=timezone.utc)
MARKET = "KXBTC15M-PHASE5"
VERSION = "world-state-v1"


def _message(
    sender: str,
    role: str,
    family: str,
    probability: float,
    *,
    message_type: MessageType = MessageType.FORECAST,
    issued_at: datetime = NOW,
    extra: dict[str, object] | None = None,
) -> MessageEnvelope:
    payload: dict[str, object] = {
        "probability": probability,
        "uncertainty": 0.10,
        "organism_role": role,
        "source_family": family,
        "world_state_version": VERSION,
    }
    payload.update(extra or {})
    return MessageEnvelope.create(
        message_type=message_type,
        sender=sender,
        market_id=MARKET,
        issued_at=issued_at,
        effective_time=NOW,
        received_at=issued_at,
        model_version="phase5-test-v1",
        policy_version="phase5-test-policy",
        evidence_ids=(f"evidence-{sender}",),
        payload=payload,
    )


def _state(*, provenance_received_at: str = "2026-07-15T01:00:00Z") -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type=MessageType.MARKET_STATE,
        sender="phase5-state",
        market_id=MARKET,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="phase5-state-v1",
        policy_version="phase5-test-policy",
        evidence_ids=("state-evidence",),
        payload={
            "state_version": VERSION,
            "world_state": {
                "completeness": 0.5,
                "schema": {
                    "fields": [
                        {"key": "market.status", "critical": True},
                        {"key": "crypto.regime", "critical": False},
                    ]
                },
                "values": [
                    {
                        "field_key": "market.status",
                        "status": "present",
                        "uncertainty": 0.0,
                        "valid_until": "2026-07-15T01:01:00Z",
                        "provenance_status": "verified_observation_chain",
                        "provenance": [
                            {
                                "evidence_id": "state-evidence",
                                "received_at": provenance_received_at,
                            }
                        ],
                    },
                    {
                        "field_key": "crypto.regime",
                        "status": "missing",
                        "uncertainty": 1.0,
                        "provenance_status": "no_verified_observation",
                        "provenance": [],
                    },
                ],
            },
        },
    )


def _messages(*, duplicate: bool = False, authority_expansion: bool = False):
    specialist_family = "market-price" if duplicate else "incumbent-family"
    prior = _message("prior", "market_prior", "market-price", 0.50)
    specialist = _message(
        "specialist",
        "specialist",
        specialist_family,
        0.65,
        extra={"execution_authority": authority_expansion},
    )
    counter = _message(
        "counter",
        "contrarian",
        "counter-family",
        0.35,
        message_type=MessageType.COUNTERFORECAST,
    )
    calibration = MessageEnvelope.create(
        message_type=MessageType.CALIBRATION_UPDATE,
        sender="calibrator",
        market_id=MARKET,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="calibration-v1",
        policy_version="phase5-test-policy",
        evidence_ids=("calibration-evidence",),
        payload={
            "world_state_version": VERSION,
            "verified_map": True,
            "calibrated_probability": 0.65,
            "applied_offset": 0.0,
        },
    )
    return prior, specialist, counter, calibration


def _context(messages, *, decision_at: datetime = NOW, payload_budget: int = 100_000):
    return GuardContext(
        decision_at=decision_at,
        state=_state(),
        messages=messages,
        resource_usage={
            "agent_count": len(messages),
            "message_count": len(messages),
            "payload_bytes": 1_000,
            "storage_bytes": 1_000,
        },
        resource_budget={
            "agent_count": 7,
            "message_count": 8,
            "payload_bytes": payload_budget,
            "storage_bytes": 1_000_000,
        },
    )


def test_all_eight_guards_report_and_can_only_contract_influence() -> None:
    review = review_context(_context(_messages()))
    assert len(review.findings) == 8
    assert {item.guard for item in review.findings} == {
        "provenance",
        "leakage",
        "confidence",
        "duplication",
        "resource",
        "market_prior",
        "regime",
        "authority",
    }
    assert review.market_prior_floor == 0.50
    assert review.execution_authority is False
    assert all(0.0 <= item.influence_cap <= 1.0 for item in review.findings)
    assert all(value <= 1.0 for value in review.family_influence_caps.values())


def test_duplicate_family_is_capped_instead_of_counted_twice() -> None:
    review = review_context(_context(_messages(duplicate=True)))
    finding = next(item for item in review.findings if item.guard == "duplication")
    assert finding.action is GuardAction.DOWNGRADE
    assert finding.influence_cap == 0.5
    assert review.family_influence_caps["market-price"] == 0.5


def test_authority_expansion_terminates_and_requires_abstention() -> None:
    review = review_context(_context(_messages(authority_expansion=True)))
    finding = next(item for item in review.findings if item.guard == "authority")
    assert finding.action is GuardAction.TERMINATE
    assert review.hard_veto is True
    assert review.requires_abstention is True


def test_future_message_is_detected_even_if_message_schema_is_otherwise_valid() -> None:
    messages = _messages()
    future = _message(
        "future-specialist",
        "specialist",
        "future-family",
        0.65,
        issued_at=NOW + timedelta(seconds=1),
    )
    review = review_context(_context((*messages, future)))
    finding = next(item for item in review.findings if item.guard == "leakage")
    assert finding.action is GuardAction.REQUIRE_ABSTENTION


def test_invalid_world_state_provenance_clock_requires_abstention() -> None:
    context = GuardContext(
        decision_at=NOW,
        state=_state(provenance_received_at="not-an-instant"),
        messages=_messages(),
        resource_usage={"payload_bytes": 1_000},
        resource_budget={"payload_bytes": 10_000},
    )
    review = review_context(context)
    finding = next(item for item in review.findings if item.guard == "leakage")
    assert finding.action is GuardAction.REQUIRE_ABSTENTION
    assert finding.reason.startswith("invalid_world_state_clock:")


def test_unmeasured_budgeted_resource_requests_measurement_and_contracts() -> None:
    context = GuardContext(
        decision_at=NOW,
        state=_state(),
        messages=_messages(),
        resource_usage={"cpu_ms": None, "payload_bytes": 1_000},
        resource_budget={"cpu_ms": 5_000, "payload_bytes": 10_000},
    )
    review = review_context(context)
    finding = next(item for item in review.findings if item.guard == "resource")
    assert finding.action is GuardAction.REQUEST_EVIDENCE
    assert finding.influence_cap < 1.0
    assert "cpu_ms" in finding.reason


def test_resource_budget_excess_terminates_without_expanding_budget() -> None:
    context = GuardContext(
        decision_at=NOW,
        state=_state(),
        messages=_messages(),
        resource_usage={"payload_bytes": 10_001},
        resource_budget={"payload_bytes": 10_000},
    )
    review = review_context(context)
    finding = next(item for item in review.findings if item.guard == "resource")
    assert finding.action is GuardAction.TERMINATE
    assert finding.influence_cap == 0.0


def test_mixed_world_state_versions_fail_before_any_guard_runs() -> None:
    messages = list(_messages())
    payload = dict(messages[0].payload)
    payload["world_state_version"] = "other-version"
    messages[0] = MessageEnvelope.create(
        message_type=MessageType.FORECAST,
        sender="mixed-prior",
        market_id=MARKET,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="phase5-test-v1",
        policy_version="phase5-test-policy",
        evidence_ids=("mixed-evidence",),
        payload=payload,
    )
    try:
        _context(tuple(messages))
    except ValueError as exc:
        assert "mixed state versions" in str(exc)
    else:
        raise AssertionError("mixed state version was accepted")
