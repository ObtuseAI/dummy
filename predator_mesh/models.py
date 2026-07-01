"""Shared mesh dataclasses and enums."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LaneState(str, Enum):
    """Lifecycle states for a mesh lane."""

    READY = "READY"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"
    COMPLETED = "COMPLETED"
    QUARANTINED = "QUARANTINED"


class LanePriority(str, Enum):
    """Mesh lane priority levels, ordered from most to least urgent."""

    REALTIME_MARKET_TERRAIN = "realtime_market_terrain"
    HIGH_VALUE_SIGNAL = "high_value_signal"
    FORECAST_UPDATE = "forecast_update"
    STRATEGY_REVIEW = "strategy_review"
    CALIBRATION_UPDATE = "calibration_update"
    SOURCE_DISCOVERY = "source_discovery"
    MAINTENANCE = "maintenance"

    @property
    def rank(self) -> int:
        """Higher rank means higher priority."""
        return {
            LanePriority.REALTIME_MARKET_TERRAIN: 700,
            LanePriority.HIGH_VALUE_SIGNAL: 600,
            LanePriority.FORECAST_UPDATE: 500,
            LanePriority.STRATEGY_REVIEW: 400,
            LanePriority.CALIBRATION_UPDATE: 300,
            LanePriority.SOURCE_DISCOVERY: 200,
            LanePriority.MAINTENANCE: 100,
        }[self]


class MeshPriority(BaseModel):
    """Priority wrapper used for scheduling decisions."""

    level: LanePriority = LanePriority.MAINTENANCE

    @property
    def rank(self) -> int:
        return self.level.rank


class MeshTimeout(BaseModel):
    """Timeout configuration for a scheduler cycle and its lanes."""

    per_lane_timeout_s: float = Field(default=10.0, ge=0.0)
    cycle_timeout_s: float = Field(default=30.0, ge=0.0)
    stuck_task_grace_s: float = Field(default=2.0, ge=0.0)


class MeshProofRef(BaseModel):
    """Reference to a proof/event recorded by the mesh proof ledger."""

    ref_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    component: str
    verdict: str
    payload_hash: str = ""


class MeshTask(BaseModel):
    """A unit of work dispatched to a lane."""

    task_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    lane_name: str
    priority: MeshPriority = Field(default_factory=lambda: MeshPriority())
    payload: dict[str, Any] = Field(default_factory=dict)


class MeshLane(BaseModel):
    """Static descriptor / snapshot of a mesh lane."""

    name: str
    priority: MeshPriority = Field(default_factory=lambda: MeshPriority())
    state: LaneState = LaneState.READY
    timeout: Optional[MeshTimeout] = None
    task: Optional[MeshTask] = None
    dependencies: list[str] = Field(default_factory=list)
    retries: int = 0
    max_retries: int = 0


class MeshResult(BaseModel):
    """Outcome of executing a single lane."""

    lane_name: str
    state: LaneState = LaneState.READY
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    proof_ref: Optional[MeshProofRef] = None
    events_recorded: int = 0


class MeshHeartbeat(BaseModel):
    """Heartbeat emitted by a running lane."""

    lane_name: str
    state: LaneState = LaneState.READY
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    progress_pct: float = Field(default=0.0, ge=0.0, le=1.0)


class MeshBudget(BaseModel):
    """Bounded call budget for provider and Kalshi read-only calls."""

    max_provider_calls: int = Field(default=20, ge=0)
    max_kalshi_calls: int = Field(default=10, ge=0)
    provider_call_count: int = 0
    kalshi_call_count: int = 0

    def can_call_provider(self) -> bool:
        return self.provider_call_count < self.max_provider_calls

    def can_call_kalshi(self) -> bool:
        return self.kalshi_call_count < self.max_kalshi_calls

    def spend_provider(self, n: int = 1) -> bool:
        if self.provider_call_count + n > self.max_provider_calls:
            return False
        self.provider_call_count += n
        return True

    def spend_kalshi(self, n: int = 1) -> bool:
        if self.kalshi_call_count + n > self.max_kalshi_calls:
            return False
        self.kalshi_call_count += n
        return True

    def remaining_provider_calls(self) -> int:
        return max(0, self.max_provider_calls - self.provider_call_count)

    def remaining_kalshi_calls(self) -> int:
        return max(0, self.max_kalshi_calls - self.kalshi_call_count)


class MeshContext(BaseModel):
    """Execution context passed to every lane."""

    run_id: str
    lane_name: str
    budget: MeshBudget
    timeout: MeshTimeout
    proof_ledger: Any = None
    shared_state: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class MeshRun(BaseModel):
    """Result of a full scheduler cycle."""

    run_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    state: LaneState = LaneState.RUNNING
    budget_used: MeshBudget = Field(default_factory=lambda: MeshBudget())
    lane_results: list[MeshResult] = Field(default_factory=list)
    timeouts: list[MeshTimeout] = Field(default_factory=list)
    proof_refs: list[MeshProofRef] = Field(default_factory=list)
    stuck_tasks: list[Any] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


# Re-export scheduler so it is importable from models.py as required by Task 1.
from predator_mesh.scheduler import MeshScheduler  # noqa: E402,F401
