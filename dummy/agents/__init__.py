"""Deterministic, typed, research-only agent runtime for DUMMY vNext."""

from dummy.agents.contract import (
    AgentBudget,
    AgentContract,
    AgentRole,
    AgentVertical,
    ContractValidationError,
)
from dummy.agents.catalog import (
    build_phase2_runtime,
    phase2_catalog_digest,
    phase2_catalog_manifest,
    phase2_contract_catalog,
)
from dummy.agents.health import AgentHealth, HealthPolicy, HealthStatus
from dummy.agents.incumbent import (
    CalibrationAgent,
    SettlementGraderAgent,
    SettlementRecord,
    ShadowExecutionTruthAgent,
    ShadowFillRecord,
    SignalForecastAgent,
    build_crypto_signal_agent,
    build_market_prior_agent,
    build_mlb_specialist_agent,
    calibration_contract,
    forecast_contract,
    market_view_from_observation,
    market_view_observation,
    settlement_observation,
    shadow_fill_observation,
    truth_contract,
)
from dummy.agents.lifecycle import (
    AgentLifecycle,
    AgentState,
    LifecycleTransitionError,
)
from dummy.agents.mailbox import DeterministicMailbox, MailboxEntry, MailboxError
from dummy.agents.permissions import AgentPermissions, PermissionViolation
from dummy.agents.registry import AgentRegistry, RegistryError
from dummy.agents.runtime import (
    AgentHandler,
    AgentInvocation,
    AgentRuntime,
    InvocationResult,
    InvocationStatus,
)

__all__ = [
    "AgentBudget",
    "AgentContract",
    "AgentHandler",
    "AgentHealth",
    "AgentInvocation",
    "AgentLifecycle",
    "AgentPermissions",
    "AgentRegistry",
    "AgentRole",
    "AgentRuntime",
    "AgentState",
    "AgentVertical",
    "CalibrationAgent",
    "ContractValidationError",
    "DeterministicMailbox",
    "HealthPolicy",
    "HealthStatus",
    "InvocationResult",
    "InvocationStatus",
    "LifecycleTransitionError",
    "MailboxEntry",
    "MailboxError",
    "PermissionViolation",
    "RegistryError",
    "SettlementGraderAgent",
    "SettlementRecord",
    "ShadowExecutionTruthAgent",
    "ShadowFillRecord",
    "SignalForecastAgent",
    "build_crypto_signal_agent",
    "build_market_prior_agent",
    "build_mlb_specialist_agent",
    "build_phase2_runtime",
    "calibration_contract",
    "forecast_contract",
    "market_view_from_observation",
    "market_view_observation",
    "phase2_catalog_digest",
    "phase2_catalog_manifest",
    "phase2_contract_catalog",
    "settlement_observation",
    "shadow_fill_observation",
    "truth_contract",
]
