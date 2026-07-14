from __future__ import annotations
from dataclasses import dataclass
from model_router.envelope import ModelResponseEnvelope


@dataclass
class CostTracker:
    calls: int = 0
    total_latency_ms: float = 0.0

    def record(self, envelope: ModelResponseEnvelope):
        self.calls += 1
        self.total_latency_ms += envelope.latency_ms

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "total_latency_ms": round(self.total_latency_ms, 4),
            "avg_latency_ms": round(self.total_latency_ms / max(self.calls, 1), 4),
        }
