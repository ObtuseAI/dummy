"""Core-backed rollback detection for Dummy's venue-local state stores."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)

from live_firewall.dumbmoney_capital import verify_signed_envelope
from live_firewall.operational_journal import canonical_json, sha256_json


CELL_ID = "dummy_kalshi"
ANCHOR_REQUEST_SCHEMA = "dumbmoney.cell-journal-anchor-request.v1"
ANCHOR_RESPONSE_SCHEMA = "dumbmoney.cell-journal-anchor-response.v1"
ANCHOR_CHECKPOINT_SCHEMA = "dumbmoney.cell-journal-anchor-checkpoint.v1"
ANCHOR_BODY_SCHEMA = "dumbmoney.cell-journal-head-anchor.v1"
LEDGER_PROOF_SCHEMA = "dumbmoney.ledger-event-proof.v1"
CORE_SOURCE_ID = "dumbmoney-core"
MAXIMUM_RESPONSE_BYTES = 524_288
ZERO_DIGEST = "0" * 64

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_RESPONSE_FIELDS = {
    "schema",
    "cell_id",
    "request_nonce",
    "observed_at",
    "reused",
    "anchor_envelope",
    "ledger_proof",
    "checkpoint",
    "checkpoint_signature",
}
_CHECKPOINT_FIELDS = {
    "schema",
    "cell_id",
    "request_nonce",
    "account_hash",
    "journal_name",
    "journal_schema",
    "journal_stream_id",
    "journal_sequence",
    "journal_head_sha256",
    "anchor_body_digest",
    "anchor_event_digest",
    "reused",
    "observed_at",
}
_SIGNATURE_FIELDS = {"algorithm", "signer_key_id", "signature"}
_ANCHOR_BODY_FIELDS = {
    "schema",
    "anchor_id",
    "venue",
    "account_hash",
    "journal_name",
    "journal_schema",
    "journal_stream_id",
    "journal_sequence",
    "journal_head_sha256",
    "previous_anchor_body_digest",
    "anchored_at",
}
_LEDGER_PROOF_FIELDS = {
    "schema",
    "global_sequence",
    "event_id",
    "source_id",
    "source_sequence",
    "signer_key_id",
    "nonce",
    "event_schema",
    "observed_at",
    "received_at",
    "correlation_id",
    "causation_id",
    "payload_digest",
    "previous_source_digest",
    "previous_global_digest",
    "event_digest",
}


class JournalAnchorError(RuntimeError):
    """A Core anchor, signature, or monotonicity check failed closed."""


@dataclass(frozen=True)
class JournalAnchorResponse:
    status_code: int
    body: bytes


class JournalAnchorTransport(Protocol):
    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
        body: bytes,
    ) -> JournalAnchorResponse: ...


@dataclass(frozen=True)
class VerifiedJournalAnchor:
    journal_name: str
    journal_sequence: int
    journal_head_sha256: str
    anchor_body_digest: str
    anchor_event_digest: str
    reused: bool
    observed_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC_RE.fullmatch(value):
        raise JournalAnchorError(
            f"{field} must be canonical RFC3339 UTC"
        )
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(
        timezone.utc
    )


def _digest(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise JournalAnchorError(f"{field} must be a lowercase sha256")
    return value


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise JournalAnchorError(f"{field} must be a canonical identifier")
    return value


def _integer(value: Any, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise JournalAnchorError(
            f"{field} must be an integer >= {minimum}"
        )
    return value


def _strict_json(body: bytes) -> dict[str, Any]:
    if not isinstance(body, bytes) or len(body) > MAXIMUM_RESPONSE_BYTES:
        raise JournalAnchorError("Core anchor response size is invalid")

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise JournalAnchorError(
                    "Core anchor response contains duplicate keys"
                )
            result[key] = value
        return result

    def constant(token: str) -> None:
        raise JournalAnchorError(
            f"Core anchor response contains non-finite value {token}"
        )

    def finite_float(token: str) -> float:
        value = float(token)
        if not math.isfinite(value):
            constant(token)
        return value

    try:
        decoded = body.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            object_pairs_hook=pairs,
            parse_constant=constant,
            parse_float=finite_float,
        )
    except JournalAnchorError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JournalAnchorError(
            "Core anchor response is not strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise JournalAnchorError("Core anchor response must be an object")
    return cast(dict[str, Any], value)


def _decode_signature(value: Any) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or "=" in value
        or re.search(r"[^A-Za-z0-9_-]", value)
    ):
        raise JournalAnchorError("anchor checkpoint signature is invalid")
    try:
        decoded = base64.urlsafe_b64decode(
            value + "=" * (-len(value) % 4)
        )
    except Exception as exc:
        raise JournalAnchorError(
            "anchor checkpoint signature is invalid"
        ) from exc
    if (
        len(decoded) != 64
        or base64.urlsafe_b64encode(decoded)
        .decode("ascii")
        .rstrip("=")
        != value
    ):
        raise JournalAnchorError(
            "anchor checkpoint signature encoding is invalid"
        )
    return decoded


class CoreJournalAnchorClient:
    """Publish exact local heads and verify Core's durable signed receipt."""

    def __init__(
        self,
        *,
        transport: JournalAnchorTransport,
        cell_token_provider: Callable[[], str],
        trusted_core_public_keys: Mapping[str, bytes | Ed25519PublicKey],
        expected_account_hash: str,
        request_nonce_fn: Callable[[], str] = lambda: secrets.token_hex(32),
        now_fn: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not trusted_core_public_keys:
            raise ValueError("trusted Core public keys are required")
        self._transport = transport
        self._cell_token_provider = cell_token_provider
        self._trusted_core_public_keys = dict(trusted_core_public_keys)
        self._expected_account_hash = _digest(
            expected_account_hash,
            field="expected_account_hash",
        )
        self._request_nonce_fn = request_nonce_fn
        self._now_fn = now_fn
        self._last_nonce: str | None = None

    def stream_id(self, journal_name: str) -> str:
        normalized = _identifier(journal_name, field="journal_name")
        return sha256_json(
            {
                "schema": "dummy.journal-anchor-stream.v1",
                "cell_id": CELL_ID,
                "account_hash": self._expected_account_hash,
                "journal_name": normalized,
            }
        )

    def _verify_checkpoint(
        self,
        checkpoint: Any,
        signature: Any,
    ) -> dict[str, Any]:
        if not isinstance(checkpoint, dict) or set(checkpoint) != (
            _CHECKPOINT_FIELDS
        ):
            raise JournalAnchorError(
                "Core anchor checkpoint fields mismatch"
            )
        if not isinstance(signature, dict) or set(signature) != (
            _SIGNATURE_FIELDS
        ):
            raise JournalAnchorError(
                "Core anchor checkpoint signature fields mismatch"
            )
        if signature["algorithm"] != "Ed25519":
            raise JournalAnchorError(
                "Core anchor checkpoint algorithm mismatch"
            )
        signer = _digest(
            signature["signer_key_id"],
            field="checkpoint signer_key_id",
        )
        key = self._trusted_core_public_keys.get(signer)
        if key is None:
            raise JournalAnchorError(
                "Core anchor checkpoint signer is not pinned"
            )
        raw_key = (
            key.public_bytes_raw()
            if isinstance(key, Ed25519PublicKey)
            else bytes(key)
        )
        if len(raw_key) != 32 or hashlib.sha256(raw_key).hexdigest() != signer:
            raise JournalAnchorError(
                "Core anchor checkpoint key identity mismatch"
            )
        try:
            Ed25519PublicKey.from_public_bytes(raw_key).verify(
                _decode_signature(signature["signature"]),
                canonical_json(checkpoint).encode("utf-8"),
            )
        except (InvalidSignature, ValueError) as exc:
            raise JournalAnchorError(
                "Core anchor checkpoint signature is invalid"
            ) from exc
        return cast(dict[str, Any], checkpoint)

    @staticmethod
    def _verify_ledger_proof(
        proof_raw: Any,
        *,
        signed: Any,
        observed_at: datetime,
    ) -> dict[str, Any]:
        if not isinstance(proof_raw, dict):
            raise JournalAnchorError("anchor ledger proof must be an object")
        proof = json.loads(canonical_json(proof_raw))
        if (
            set(proof) != _LEDGER_PROOF_FIELDS
            or proof.get("schema") != LEDGER_PROOF_SCHEMA
        ):
            raise JournalAnchorError("anchor ledger proof fields mismatch")
        sequence = _integer(
            proof["global_sequence"],
            field="ledger proof global_sequence",
            minimum=1,
        )
        source_sequence = _integer(
            proof["source_sequence"],
            field="ledger proof source_sequence",
            minimum=1,
        )
        received_at = _parse_utc(
            proof["received_at"],
            field="ledger proof received_at",
        )
        record_observed = _parse_utc(
            proof["observed_at"],
            field="ledger proof observed_at",
        )
        if received_at > observed_at:
            raise JournalAnchorError(
                "anchor ledger proof postdates the checkpoint"
            )
        if record_observed != max(received_at, signed.not_before):
            raise JournalAnchorError(
                "anchor ledger proof observation semantics differ"
            )
        previous_global = _digest(
            proof["previous_global_digest"],
            field="ledger proof previous_global_digest",
        )
        previous_source = _digest(
            proof["previous_source_digest"],
            field="ledger proof previous_source_digest",
        )
        if (sequence == 1) != (previous_global == ZERO_DIGEST):
            raise JournalAnchorError(
                "anchor ledger proof global predecessor is invalid"
            )
        if (source_sequence == 1) != (previous_source == ZERO_DIGEST):
            raise JournalAnchorError(
                "anchor ledger proof source predecessor is invalid"
            )
        wrapper = signed.wrapper
        expected = {
            "event_id": signed.event_id,
            "source_id": signed.source_id,
            "source_sequence": signed.source_sequence,
            "signer_key_id": signed.signer_key_id,
            "nonce": signed.nonce,
            "event_schema": signed.body_schema,
            "correlation_id": wrapper["correlation_id"],
            "causation_id": wrapper["causation_id"],
            "payload_digest": wrapper["body_digest"],
        }
        for field, expected_value in expected.items():
            if proof.get(field) != expected_value:
                raise JournalAnchorError(
                    f"anchor ledger proof {field} differs from envelope"
                )
        event_digest = _digest(
            proof["event_digest"],
            field="ledger proof event_digest",
        )
        event_material = {
            key: value
            for key, value in proof.items()
            if key not in {"schema", "event_digest"}
        }
        if sha256_json(event_material) != event_digest:
            raise JournalAnchorError(
                "anchor ledger proof digest is invalid"
            )
        return cast(dict[str, Any], proof)

    def anchor(
        self,
        *,
        journal_name: str,
        journal_schema: str,
        journal_sequence: int,
        journal_head_sha256: str,
    ) -> VerifiedJournalAnchor:
        name = _identifier(journal_name, field="journal_name")
        schema = _identifier(journal_schema, field="journal_schema")
        sequence = _integer(
            journal_sequence,
            field="journal_sequence",
        )
        head = _digest(
            journal_head_sha256,
            field="journal_head_sha256",
        )
        if (sequence == 0) != (head == ZERO_DIGEST):
            raise JournalAnchorError(
                "journal sequence zero must exactly bind the zero head"
            )
        stream_id = self.stream_id(name)
        nonce = _digest(
            self._request_nonce_fn(),
            field="request_nonce",
        )
        if nonce == self._last_nonce:
            raise JournalAnchorError(
                "journal anchor nonce generator repeated a nonce"
            )
        self._last_nonce = nonce
        request = {
            "schema": ANCHOR_REQUEST_SCHEMA,
            "cell_id": CELL_ID,
            "account_hash": self._expected_account_hash,
            "journal_name": name,
            "journal_schema": schema,
            "journal_stream_id": stream_id,
            "journal_sequence": sequence,
            "journal_head_sha256": head,
            "request_nonce": nonce,
        }
        token = self._cell_token_provider()
        if (
            not isinstance(token, str)
            or not token
            or token != token.strip()
            or any(character.isspace() for character in token)
        ):
            raise JournalAnchorError(
                "cell token is not a canonical secret"
            )
        try:
            response = self._transport(
                f"/v1/cells/{CELL_ID}/journal-heads:anchor",
                {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                canonical_json(request).encode("utf-8"),
            )
        except Exception as exc:
            raise JournalAnchorError(
                f"journal anchor transport failed:{type(exc).__name__}"
            ) from exc
        finally:
            token = ""
        if (
            not isinstance(response, JournalAnchorResponse)
            or response.status_code != 200
        ):
            raise JournalAnchorError(
                "Core rejected the journal head anchor"
            )
        payload = _strict_json(response.body)
        if (
            set(payload) != _RESPONSE_FIELDS
            or payload.get("schema") != ANCHOR_RESPONSE_SCHEMA
            or payload.get("cell_id") != CELL_ID
            or payload.get("request_nonce") != nonce
            or not isinstance(payload.get("reused"), bool)
        ):
            raise JournalAnchorError(
                "Core anchor response fields or identity mismatch"
            )
        checkpoint = self._verify_checkpoint(
            payload["checkpoint"],
            payload["checkpoint_signature"],
        )
        observed_at = _parse_utc(
            payload["observed_at"],
            field="anchor response observed_at",
        )
        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            raise JournalAnchorError(
                "journal anchor clock must be timezone-aware"
            )
        now = now.astimezone(timezone.utc)
        if (
            observed_at > now + timedelta(seconds=5)
            or now - observed_at > timedelta(seconds=30)
        ):
            raise JournalAnchorError(
                "Core anchor response is not current"
            )
        expected_checkpoint = {
            "schema": ANCHOR_CHECKPOINT_SCHEMA,
            "cell_id": CELL_ID,
            "request_nonce": nonce,
            "account_hash": self._expected_account_hash,
            "journal_name": name,
            "journal_schema": schema,
            "journal_stream_id": stream_id,
            "journal_sequence": sequence,
            "journal_head_sha256": head,
            "anchor_body_digest": checkpoint["anchor_body_digest"],
            "anchor_event_digest": checkpoint["anchor_event_digest"],
            "reused": payload["reused"],
            "observed_at": payload["observed_at"],
        }
        if checkpoint != expected_checkpoint:
            raise JournalAnchorError(
                "Core anchor checkpoint differs from the request"
            )
        try:
            signed = verify_signed_envelope(
                payload["anchor_envelope"],
                trusted_public_keys=self._trusted_core_public_keys,
                expected_body_schema=ANCHOR_BODY_SCHEMA,
                max_ttl=timedelta(seconds=120),
                require_active=False,
            )
        except (TypeError, ValueError) as exc:
            raise JournalAnchorError(
                "Core journal anchor envelope is invalid"
            ) from exc
        if signed.source_id != CORE_SOURCE_ID:
            raise JournalAnchorError(
                "journal anchor source is not DumbMoney Core"
            )
        body = signed.body
        if set(body) != _ANCHOR_BODY_FIELDS:
            raise JournalAnchorError(
                "journal anchor body fields mismatch"
            )
        anchored_at = _parse_utc(
            body["anchored_at"],
            field="anchor body anchored_at",
        )
        if (
            body.get("venue") != CELL_ID
            or body.get("account_hash") != self._expected_account_hash
            or body.get("journal_name") != name
            or body.get("journal_schema") != schema
            or body.get("journal_stream_id") != stream_id
            or body.get("journal_sequence") != sequence
            or body.get("journal_head_sha256") != head
            or anchored_at > observed_at
        ):
            raise JournalAnchorError(
                "journal anchor body differs from the local head"
            )
        previous = _digest(
            body["previous_anchor_body_digest"],
            field="previous_anchor_body_digest",
        )
        expected_anchor_id = sha256_json(
            {
                "schema": ANCHOR_BODY_SCHEMA,
                "venue": CELL_ID,
                "account_hash": self._expected_account_hash,
                "journal_name": name,
                "journal_schema": schema,
                "journal_stream_id": stream_id,
                "journal_sequence": sequence,
                "journal_head_sha256": head,
                "previous_anchor_body_digest": previous,
            }
        )
        if body.get("anchor_id") != expected_anchor_id:
            raise JournalAnchorError("journal anchor identity is invalid")
        proof = self._verify_ledger_proof(
            payload["ledger_proof"],
            signed=signed,
            observed_at=observed_at,
        )
        body_digest = _digest(
            checkpoint["anchor_body_digest"],
            field="checkpoint anchor_body_digest",
        )
        event_digest = _digest(
            checkpoint["anchor_event_digest"],
            field="checkpoint anchor_event_digest",
        )
        if (
            body_digest != signed.wrapper["body_digest"]
            or body_digest != proof["payload_digest"]
            or event_digest != proof["event_digest"]
        ):
            raise JournalAnchorError(
                "journal anchor checkpoint proof binding is invalid"
            )
        return VerifiedJournalAnchor(
            journal_name=name,
            journal_sequence=sequence,
            journal_head_sha256=head,
            anchor_body_digest=body_digest,
            anchor_event_digest=event_digest,
            reused=bool(payload["reused"]),
            observed_at=cast(str, payload["observed_at"]),
        )


__all__ = [
    "ANCHOR_BODY_SCHEMA",
    "ANCHOR_CHECKPOINT_SCHEMA",
    "ANCHOR_REQUEST_SCHEMA",
    "ANCHOR_RESPONSE_SCHEMA",
    "CoreJournalAnchorClient",
    "JournalAnchorError",
    "JournalAnchorResponse",
    "JournalAnchorTransport",
    "VerifiedJournalAnchor",
]
