"""Typed message vocabulary for DUMMY vNext."""

from dummy.protocols.messages import (
    MessageEnvelope,
    MessageType,
    ProtocolValidationError,
    required_authority,
)

__all__ = [
    "MessageEnvelope",
    "MessageType",
    "ProtocolValidationError",
    "required_authority",
]
