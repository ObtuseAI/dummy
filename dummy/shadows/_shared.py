"""Small deterministic helpers shared by contraction-only guards."""

from __future__ import annotations

from dummy.protocols import MessageType

from .context import GuardContext


def forecast_messages(context: GuardContext):
    return tuple(
        message
        for message in context.messages
        if message.message_type in {MessageType.FORECAST, MessageType.COUNTERFORECAST}
    )


def family(message) -> str:
    return str(message.payload.get("source_family", "")).strip()


def non_market_families(context: GuardContext) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                family(message)
                for message in forecast_messages(context)
                if family(message) and family(message) != "market-price"
            }
        )
    )


def evidence_ids(context: GuardContext) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                evidence_id
                for message in (context.state, *context.messages)
                for evidence_id in (*message.evidence_ids, message.message_id)
            }
        )
    )
