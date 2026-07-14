from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from dummy.agents import AgentRole, AgentVertical
from dummy.chronos import ClockDomain
from dummy.organisms import (
    BTC_15M_TEMPLATE,
    MLB_PREGAME_TEMPLATE,
    PHASE3_TEMPLATES,
    EpisodeValidationError,
    phase3_template_manifest,
    select_template,
)
from dummy.protocols import MessageEnvelope, MessageType, ProtocolValidationError


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)


def test_phase3_templates_have_exact_required_roles_and_one_specialist() -> None:
    required = {
        AgentRole.MARKET_PRIOR,
        AgentRole.SPECIALIST,
        AgentRole.CONTRARIAN,
        AgentRole.CALIBRATOR,
        AgentRole.ADVERSARY,
        AgentRole.SHADOW,
        AgentRole.SYNTHESIZER,
    }
    assert len(PHASE3_TEMPLATES) == 2
    for template in PHASE3_TEMPLATES:
        roles = [contract.role for contract in template.contracts]
        assert set(roles) == required
        assert roles.count(AgentRole.SPECIALIST) == 1
        assert len(template.dependency_order) == 7
        assert template.digest() == template.digest()
        assert all(contract.authority.name != "EXECUTE" for contract in template.contracts)


def test_router_is_pure_specific_and_rejects_unsupported_markets() -> None:
    assert (
        select_template(
            market_id="KXBTC15M-26JUL142215-15",
            market_type="15m_direction",
            vertical=AgentVertical.CRYPTO,
            clock_domain=ClockDomain.FIFTEEN_MINUTE,
        )
        is BTC_15M_TEMPLATE
    )
    assert (
        select_template(
            market_id="KXMLBGAME-26JUL14CHCATL-CHI",
            market_type="winner",
            vertical=AgentVertical.MLB,
            clock_domain=ClockDomain.PREGAME,
        )
        is MLB_PREGAME_TEMPLATE
    )
    with pytest.raises(EpisodeValidationError, match="exactly one"):
        select_template(
            market_id="KXNFLGAME-OTHER",
            market_type="winner",
            vertical=AgentVertical.NFL,
            clock_domain=ClockDomain.PREGAME,
        )


def test_template_manifest_keeps_all_authority_and_substitution_disabled() -> None:
    manifest = phase3_template_manifest()
    assert manifest["execution_authority"] is False
    assert manifest["promotion_authority"] == "HUMAN_ONLY"
    assert manifest["incumbent_substitution_allowed"] is False


def test_persisted_template_catalog_matches_executable_templates() -> None:
    path = Path(__file__).parents[1] / "docs" / "VNEXT_PHASE3_TEMPLATE_CATALOG.json"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["execution_authority"] is False
    assert persisted["promotion_authority"] == "HUMAN_ONLY"
    by_id = {item["template_id"]: item for item in persisted["templates"]}
    assert set(by_id) == {template.template_id for template in PHASE3_TEMPLATES}
    for template in PHASE3_TEMPLATES:
        record = by_id[template.template_id]
        assert record["digest"] == template.digest()
        assert record["dependency_order"] == list(template.dependency_order)
        assert record["roles"] == [contract.role.value for contract in template.contracts]


def test_abstention_is_a_durable_typed_forecasting_message() -> None:
    message = MessageEnvelope.create(
        message_type=MessageType.ABSTENTION,
        sender="synthesizer-v1",
        market_id="KXBTC15M-26JUL142215-15",
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="1.0.0",
        policy_version="phase3-policy-v1",
        payload={"candidate_probability": 0.5, "reasons": ["no_edge"]},
    )
    assert message.message_type is MessageType.ABSTENTION
    assert message.authority.name == "FORECAST"
    assert MessageEnvelope.from_dict(message.to_dict()) == message
    with pytest.raises(ProtocolValidationError, match="at least one"):
        MessageEnvelope.create(
            message_type=MessageType.ABSTENTION,
            sender="synthesizer-v1",
            market_id="KXBTC15M-26JUL142215-15",
            issued_at=NOW,
            effective_time=NOW,
            received_at=NOW,
            model_version="1.0.0",
            policy_version="phase3-policy-v1",
            payload={"candidate_probability": 0.5, "reasons": []},
        )
