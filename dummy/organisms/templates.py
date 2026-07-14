"""Pure routing and deterministic morphology templates for Phase 3 pilots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from dummy.agents import (
    AgentBudget,
    AgentContract,
    AgentRegistry,
    AgentRole,
    AgentVertical,
)
from dummy.chronos import ClockDomain
from dummy.constitution import Authority
from dummy.protocols import MessageType

from .models import EpisodeValidationError


REQUIRED_ROLES = frozenset(
    {
        AgentRole.MARKET_PRIOR,
        AgentRole.SPECIALIST,
        AgentRole.CONTRARIAN,
        AgentRole.CALIBRATOR,
        AgentRole.ADVERSARY,
        AgentRole.SHADOW,
        AgentRole.SYNTHESIZER,
    }
)


def _contract(
    *,
    agent_id: str,
    role: AgentRole,
    vertical: AgentVertical,
    market_type: str,
    clock_domain: ClockDomain,
    inputs: tuple[MessageType, ...],
    outputs: tuple[MessageType, ...],
    authority: Authority,
    source_family: str,
    dependencies: tuple[str, ...] = (),
) -> AgentContract:
    return AgentContract(
        agent_id=agent_id,
        role=role,
        vertical=vertical,
        supported_market_types=(market_type,),
        input_types=inputs,
        output_types=outputs,
        clock_domain=clock_domain,
        authority=authority,
        evidence_requirements=("frozen_point_in_time_state",),
        fail_closed_on=(
            "future_received_evidence",
            "missing_required_state",
            "stale_state",
        ),
        budget=AgentBudget(
            max_messages_per_invocation=8,
            max_payload_bytes=128 * 1024,
            max_evidence_items=128,
            max_wall_time_ms=1_000,
        ),
        calibration_identity=f"{agent_id}-calibration",
        source_family=source_family,
        version="1.0.0",
        dependencies=dependencies,
        max_input_age_ms=300_000,
    )


@dataclass(frozen=True, slots=True)
class OrganismTemplate:
    template_id: str
    ticker_prefix: str
    market_type: str
    vertical: AgentVertical
    clock_domain: ClockDomain
    contracts: tuple[AgentContract, ...]
    template_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.template_id.strip() or not self.ticker_prefix.strip():
            raise EpisodeValidationError("template identifiers must be non-empty")
        roles = tuple(contract.role for contract in self.contracts)
        if frozenset(roles) != REQUIRED_ROLES or len(roles) != len(REQUIRED_ROLES):
            raise EpisodeValidationError(
                "organism template must contain each required role exactly once"
            )
        if roles.count(AgentRole.SPECIALIST) != 1:
            raise EpisodeValidationError(
                "one-specialist-per-market routing must be preserved"
            )
        if any(contract.vertical is not self.vertical for contract in self.contracts):
            raise EpisodeValidationError("template contract vertical mismatch")
        if any(
            contract.clock_domain is not self.clock_domain
            for contract in self.contracts
        ):
            raise EpisodeValidationError("template contract clock mismatch")
        if any(
            not contract.supports_market_type(self.market_type)
            for contract in self.contracts
        ):
            raise EpisodeValidationError("template contract market mismatch")
        registry = AgentRegistry()
        for contract in self.contracts:
            registry.register(contract)
        registry.seal()

    @property
    def dependency_order(self) -> tuple[str, ...]:
        registry = AgentRegistry()
        for contract in self.contracts:
            registry.register(contract)
        return registry.seal()

    def contract_for(self, role: AgentRole) -> AgentContract:
        matches = tuple(item for item in self.contracts if item.role is role)
        if len(matches) != 1:
            raise EpisodeValidationError(f"template role is not unique: {role.value}")
        return matches[0]

    def matches(
        self,
        *,
        market_id: str,
        market_type: str,
        vertical: AgentVertical,
        clock_domain: ClockDomain,
    ) -> bool:
        return (
            market_id.upper().startswith(self.ticker_prefix)
            and market_type == self.market_type
            and vertical is self.vertical
            and clock_domain is self.clock_domain
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "ticker_prefix": self.ticker_prefix,
            "market_type": self.market_type,
            "vertical": self.vertical.value,
            "clock_domain": self.clock_domain.value,
            "one_specialist_per_market": True,
            "dependency_order": list(self.dependency_order),
            "contracts": [
                contract.to_dict()
                for contract in sorted(self.contracts, key=lambda item: item.agent_id)
            ],
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _build_template(
    *,
    stem: str,
    template_id: str,
    ticker_prefix: str,
    market_type: str,
    vertical: AgentVertical,
    clock_domain: ClockDomain,
    incumbent_source_family: str,
) -> OrganismTemplate:
    prior_id = f"{stem}-market-prior-v1"
    incumbent_id = f"{stem}-incumbent-v1"
    contrarian_id = f"{stem}-contrarian-v1"
    calibrator_id = f"{stem}-calibrator-v1"
    adversary_id = f"{stem}-adversary-v1"
    shadow_id = f"{stem}-shadow-controller-v1"
    synthesizer_id = f"{stem}-synthesizer-v1"
    common = {
        "vertical": vertical,
        "market_type": market_type,
        "clock_domain": clock_domain,
    }
    contracts = (
        _contract(
            agent_id=prior_id,
            role=AgentRole.MARKET_PRIOR,
            inputs=(MessageType.MARKET_STATE,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
            source_family="market-price",
            **common,
        ),
        _contract(
            agent_id=incumbent_id,
            role=AgentRole.SPECIALIST,
            inputs=(MessageType.MARKET_STATE,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
            source_family=incumbent_source_family,
            **common,
        ),
        _contract(
            agent_id=contrarian_id,
            role=AgentRole.CONTRARIAN,
            inputs=(MessageType.FORECAST,),
            outputs=(MessageType.COUNTERFORECAST,),
            authority=Authority.CHALLENGE,
            source_family=f"{stem}-countercase",
            dependencies=(prior_id, incumbent_id),
            **common,
        ),
        _contract(
            agent_id=calibrator_id,
            role=AgentRole.CALIBRATOR,
            inputs=(MessageType.FORECAST, MessageType.MARKET_STATE),
            outputs=(MessageType.CALIBRATION_UPDATE,),
            authority=Authority.MODEL,
            source_family=f"{stem}-calibration",
            dependencies=(incumbent_id,),
            **common,
        ),
        _contract(
            agent_id=adversary_id,
            role=AgentRole.ADVERSARY,
            inputs=(
                MessageType.FORECAST,
                MessageType.COUNTERFORECAST,
                MessageType.CALIBRATION_UPDATE,
            ),
            outputs=(MessageType.UNCERTAINTY, MessageType.VETO),
            authority=Authority.CHALLENGE,
            source_family=f"{stem}-adversarial-review",
            dependencies=(prior_id, incumbent_id, contrarian_id, calibrator_id),
            **common,
        ),
        _contract(
            agent_id=shadow_id,
            role=AgentRole.SHADOW,
            inputs=(
                MessageType.FORECAST,
                MessageType.COUNTERFORECAST,
                MessageType.CALIBRATION_UPDATE,
                MessageType.UNCERTAINTY,
                MessageType.VETO,
            ),
            outputs=(MessageType.UNCERTAINTY, MessageType.VETO),
            authority=Authority.CHALLENGE,
            source_family="constitutional-shadow",
            dependencies=(prior_id, incumbent_id, contrarian_id, calibrator_id, adversary_id),
            **common,
        ),
        _contract(
            agent_id=synthesizer_id,
            role=AgentRole.SYNTHESIZER,
            inputs=(
                MessageType.FORECAST,
                MessageType.COUNTERFORECAST,
                MessageType.CALIBRATION_UPDATE,
                MessageType.UNCERTAINTY,
                MessageType.VETO,
            ),
            outputs=(MessageType.FORECAST, MessageType.ABSTENTION),
            authority=Authority.FORECAST,
            source_family=f"{stem}-family-capped-synthesis",
            dependencies=(
                prior_id,
                incumbent_id,
                contrarian_id,
                calibrator_id,
                adversary_id,
                shadow_id,
            ),
            **common,
        ),
    )
    return OrganismTemplate(
        template_id=template_id,
        ticker_prefix=ticker_prefix,
        market_type=market_type,
        vertical=vertical,
        clock_domain=clock_domain,
        contracts=contracts,
    )


BTC_15M_TEMPLATE = _build_template(
    stem="btc15m",
    template_id="btc-15m-direction-organism-v1",
    ticker_prefix="KXBTC15M",
    market_type="15m_direction",
    vertical=AgentVertical.CRYPTO,
    clock_domain=ClockDomain.FIFTEEN_MINUTE,
    incumbent_source_family="crypto-coinbase-distribution",
)

MLB_PREGAME_TEMPLATE = _build_template(
    stem="mlbpregame",
    template_id="mlb-pregame-winner-organism-v1",
    ticker_prefix="KXMLBGAME",
    market_type="winner",
    vertical=AgentVertical.MLB,
    clock_domain=ClockDomain.PREGAME,
    incumbent_source_family="mlb-structural",
)

PHASE3_TEMPLATES = (BTC_15M_TEMPLATE, MLB_PREGAME_TEMPLATE)


def select_template(
    *,
    market_id: str,
    market_type: str,
    vertical: AgentVertical,
    clock_domain: ClockDomain,
) -> OrganismTemplate:
    matches = tuple(
        template
        for template in PHASE3_TEMPLATES
        if template.matches(
            market_id=market_id,
            market_type=market_type,
            vertical=vertical,
            clock_domain=clock_domain,
        )
    )
    if len(matches) != 1:
        raise EpisodeValidationError(
            "market does not resolve to exactly one Phase 3 specialist template"
        )
    return matches[0]


def phase3_template_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "execution_authority": False,
        "promotion_authority": "HUMAN_ONLY",
        "incumbent_substitution_allowed": False,
        "templates": [template.to_dict() for template in PHASE3_TEMPLATES],
    }
