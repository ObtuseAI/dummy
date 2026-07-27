"""Domain-separated signatures for authenticated DumbMoney broker evidence.

Kalshi authenticates the caller and TLS protects the response in transit, but
portfolio responses are not themselves exchange-signed artifacts.  The venue
service therefore signs the exact normalized response projection immediately
after its stable authenticated reads.  The signature proves which sealed
service identity observed the broker response; it does not turn local
assertions into exchange facts.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from live_firewall.operational_journal import canonical_json, sha256_json


SIGNED_ENVELOPE_SCHEMA = "dumbmoney.signed-envelope.v1"
BROKER_WITNESS_SOURCE_ID = "dummy-kalshi-broker-witness"
TERMINAL_WITNESS_SCHEMA = "dummy.kalshi-order-terminal-witness.v1"
SETTLEMENT_WITNESS_SCHEMA = "dummy.kalshi-settlement-witness.v1"
WITNESS_TTL = timedelta(minutes=5)
_ALLOWED_SCHEMAS = frozenset(
    {TERMINAL_WITNESS_SCHEMA, SETTLEMENT_WITNESS_SCHEMA}
)


def _format_utc(value: datetime) -> str:
    rendered = value.astimezone(timezone.utc).isoformat(
        timespec="microseconds" if value.microsecond else "seconds"
    )
    return rendered.replace("+00:00", "Z")


def sign_broker_witness(
    body: Mapping[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    observed_at: datetime,
    correlation_id: str,
) -> dict[str, Any]:
    """Sign one canonical typed witness with the venue-service identity."""
    if (
        observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("broker witness clock must be timezone-aware")
    value = dict(body)
    schema = value.get("schema")
    if schema not in _ALLOWED_SCHEMAS:
        raise ValueError("broker witness body schema is unsupported")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise ValueError("broker witness correlation id is required")
    observed = observed_at.astimezone(timezone.utc)
    not_before = _format_utc(observed)
    expires_at = _format_utc(observed + WITNESS_TTL)
    public_key = private_key.public_key().public_bytes_raw()
    signer_key_id = hashlib.sha256(public_key).hexdigest()
    body_digest = sha256_json(value)
    event_material = {
        "schema": SIGNED_ENVELOPE_SCHEMA,
        "source_id": BROKER_WITNESS_SOURCE_ID,
        "source_sequence": max(1, int(observed.timestamp() * 1_000_000)),
        "correlation_id": correlation_id,
        "causation_id": None,
        "nonce": body_digest,
        "not_before": not_before,
        "expires_at": expires_at,
        "body_schema": schema,
        "body_digest": body_digest,
        "body": value,
        "signature_algorithm": "Ed25519",
        "signer_key_id": signer_key_id,
    }
    wrapper = {
        **event_material,
        "event_id": sha256_json(event_material),
    }
    wrapper["signature"] = (
        base64.urlsafe_b64encode(
            private_key.sign(canonical_json(wrapper).encode("utf-8"))
        )
        .decode("ascii")
        .rstrip("=")
    )
    return wrapper


__all__ = [
    "BROKER_WITNESS_SOURCE_ID",
    "SETTLEMENT_WITNESS_SCHEMA",
    "SIGNED_ENVELOPE_SCHEMA",
    "TERMINAL_WITNESS_SCHEMA",
    "WITNESS_TTL",
    "sign_broker_witness",
]
