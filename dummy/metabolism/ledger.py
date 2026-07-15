"""Deterministic resource accounting that marks unavailable metrics unknown."""

from __future__ import annotations

from dummy.protocols import MessageEnvelope

from .models import ResourceUsage


def account_messages(
    messages: tuple[MessageEnvelope, ...],
    *,
    provider_calls: int = 0,
    data_fetches: int = 0,
    simulations: int = 0,
    monte_carlo_paths: int = 0,
    cpu_ms: float | None = None,
    peak_memory_bytes: int | None = None,
    replay_ms: float | None = None,
    hydration_ms: float | None = None,
    wall_clock_ms: float | None = None,
) -> ResourceUsage:
    payload_bytes = sum(len(message.to_json().encode("utf-8")) for message in messages)
    return ResourceUsage(
        provider_calls=provider_calls,
        cpu_ms=cpu_ms,
        peak_memory_bytes=peak_memory_bytes,
        simulations=simulations,
        monte_carlo_paths=monte_carlo_paths,
        data_fetches=data_fetches,
        storage_bytes=payload_bytes,
        replay_ms=replay_ms,
        hydration_ms=hydration_ms,
        agent_count=len({message.sender for message in messages}),
        wall_clock_ms=wall_clock_ms,
        message_count=len(messages),
        payload_bytes=payload_bytes,
    )
