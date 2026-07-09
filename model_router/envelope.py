from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from model_router.tasks import ModelTask


class ModelRouteDecision(BaseModel):
    task: ModelTask
    provider_name: str
    model_name: str
    reason: str
    fallback_reason: str | None = None


class ModelResponseEnvelope(BaseModel):
    task: ModelTask
    decision: ModelRouteDecision
    prompt: str
    content: str
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float
    proof_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    blocked_by: str | None = None
