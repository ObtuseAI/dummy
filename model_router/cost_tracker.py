from __future__ import annotations
from dataclasses import dataclass, field
from model_router.envelope import ModelResponseEnvelope


@dataclass
class CostTracker:
    """Aggregate real per-provider spend and latency for the session.

    ``cost_usd`` comes from each provider's own reported usage when present
    (``raw_metadata['cost_usd']``); calls whose provider reports nothing are
    counted separately as ``uncosted_calls`` rather than pretending $0.
    """

    calls: int = 0
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    uncosted_calls: int = 0
    gate_blocked_calls: int = 0
    by_provider: dict[str, dict[str, float]] = field(default_factory=dict)

    def record(self, envelope: ModelResponseEnvelope):
        self.calls += 1
        self.total_latency_ms += envelope.latency_ms
        provider = str(envelope.decision.provider_name or "unknown")
        # Voice-health accounting (observational only): a mock fallback whose
        # reason names the original provider counts as that voice's failure;
        # the gate-closed fallback is tracked separately, never per-voice.
        fallback = str(envelope.decision.fallback_reason or "")
        if provider == "mock" and fallback.endswith("_request_failed"):
            failed_voice = fallback[: -len("_request_failed")]
            row = self.by_provider.setdefault(
                failed_voice,
                {"calls": 0.0, "latency_ms": 0.0, "cost_usd": 0.0,
                 "uncosted_calls": 0.0},
            )
            row["failures"] = row.get("failures", 0.0) + 1
        elif provider == "mock" and fallback == "live_calls_disabled":
            self.gate_blocked_calls += 1
        row = self.by_provider.setdefault(
            provider,
            {"calls": 0.0, "latency_ms": 0.0, "cost_usd": 0.0, "uncosted_calls": 0.0},
        )
        row["calls"] += 1
        row["latency_ms"] += envelope.latency_ms
        cost = (envelope.raw_metadata or {}).get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0.0:
            self.total_cost_usd += float(cost)
            row["cost_usd"] += float(cost)
        else:
            self.uncosted_calls += 1
            row["uncosted_calls"] += 1

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "total_latency_ms": round(self.total_latency_ms, 4),
            "avg_latency_ms": round(self.total_latency_ms / max(self.calls, 1), 4),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "uncosted_calls": self.uncosted_calls,
            "gate_blocked_calls": self.gate_blocked_calls,
            "by_provider": {
                provider: {
                    "calls": int(row["calls"]),
                    "latency_ms": round(row["latency_ms"], 4),
                    "avg_latency_ms": round(row["latency_ms"] / max(row["calls"], 1.0), 4),
                    "cost_usd": round(row["cost_usd"], 6),
                    "uncosted_calls": int(row["uncosted_calls"]),
                    "failures": int(row.get("failures", 0.0)),
                }
                for provider, row in sorted(self.by_provider.items())
            },
        }
