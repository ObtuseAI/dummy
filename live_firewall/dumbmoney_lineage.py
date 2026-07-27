"""Authenticated Core resolver for Dummy's singleton live lineage.

Capital is an upper bound, not evidence that the named strategy, passport, or
promotion exists.  This module resolves the exact passport and promotion
digests through DumbMoney Core's loopback-only cell endpoint and verifies:

* a fresh, nonce-bound Core checkpoint;
* the original ledger proof and signed envelope;
* disjoint Core, research, and promoter signing roles; and
* the complete strategy/passport/promotion/instrument/capital relationship.

There is deliberately no HTTP client or retry loop here.  A sealed local
runner injects one loopback GET transport and a Windows-credential-backed cell
token provider.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast
from urllib.parse import urlencode

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from live_firewall.dumbmoney_capital import (
    VerifiedCapitalEnvelope,
    VerifiedSignedEnvelope,
    verify_signed_envelope,
)
from live_firewall.operational_journal import canonical_json, sha256_json


CELL_ID = "dummy_kalshi"
ALPHA_PASSPORT_SCHEMA = "dumbmoney.alpha_passport.v1"
PROMOTION_CERTIFICATE_SCHEMA = "dumbmoney.promotion-certificate.v1"
CONTRACT_RESOLUTION_SCHEMA = "dumbmoney.cell-contract-resolution.v1"
CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA = (
    "dumbmoney.cell-contract-resolution-checkpoint.v1"
)
LEDGER_PROOF_SCHEMA = "dumbmoney.ledger-event-proof.v1"
LIVE_PROMOTION_STAGES = frozenset(
    {"EXPLORATORY_LIVE", "AGGRESSIVE_BOUNDED"}
)
EVIDENCE_CLASSES = frozenset(
    {"SYNTHETIC", "REPLAY", "BACKTEST", "PAPER", "FORWARD", "REALIZED"}
)
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
    "requested_body_digest",
    "capital_envelope_digest",
    "fencing_generation",
    "observed_at",
    "contract_schema",
    "transport_window_current",
    "body_window_current",
    "eligible_live_input",
    "authority_state",
    "ledger_proof",
    "envelope",
    "checkpoint",
    "checkpoint_signature",
}
_CHECKPOINT_FIELDS = _RESPONSE_FIELDS - {
    "checkpoint",
    "checkpoint_signature",
}
_SIGNATURE_FIELDS = {"algorithm", "signer_key_id", "signature"}
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
_PASSPORT_FIELDS = {
    "schema",
    "passport_id",
    "strategy_lineage_id",
    "venue",
    "strategy_hash",
    "artifact_hashes",
    "evidence_verdict_hashes",
    "intended_instruments",
    "maximum_loss_cents",
    "evidence_class",
    "created_at",
    "expires_at",
}
_PROMOTION_FIELDS = {
    "schema",
    "certificate_id",
    "passport_digest",
    "verdict_digests",
    "stage",
    "venue",
    "instruments",
    "maximum_loss_cents",
    "rollback_triggers",
    "policy_epoch",
    "not_before",
    "expires_at",
}
AUTHORITY_STATE_SCHEMA = "dumbmoney.cell-authority-state.v1"
_AUTHORITY_STATE_FIELDS = {
    "schema",
    "evaluated_at",
    "authority_valid_until",
    "policy_epoch",
    "mandate_id",
    "mandate_event_digest",
    "kill_clear",
    "kill_generation",
    "kill_event_digest",
    "desired_mode",
    "desired_mode_revision",
    "desired_mode_event_digest",
    "capital_envelope_digest",
    "capital_event_digest",
    "fencing_generation",
    "strategy_hash",
    "passport_digest",
    "passport_event_digest",
    "promotion_digest",
    "promotion_event_digest",
    "verdicts",
    "ledger_head_sequence",
    "ledger_head_digest",
}
_AUTHORITY_VERDICT_FIELDS = {
    "verdict_digest",
    "verdict_event_digest",
    "verdict_id",
    "court",
    "decision",
    "signer_key_id",
    "evaluated_at",
    "expires_at",
    "transport_expires_at",
}
_VERDICT_COURTS = frozenset(
    {"integrity", "statistics", "economics", "adversarial_operations"}
)


class LineageResolutionError(RuntimeError):
    """A resolver, provenance, or relationship failure that removes authority."""


@dataclass(frozen=True)
class ContractResolutionResponse:
    """One injected loopback GET response."""

    status_code: int
    body: bytes


class ContractResolutionTransport(Protocol):
    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
    ) -> ContractResolutionResponse: ...


@dataclass(frozen=True)
class VerifiedLineageBinding:
    """Exact authenticated lineage pinned to one current capital fence."""

    strategy_hash: str
    passport_hash: str
    promotion_hash: str
    authorized_instrument: str
    maximum_loss_cents: int
    policy_epoch: int
    capital_envelope_id: str
    capital_event_id: str
    capital_body_digest: str
    capital_fencing_generation: int
    passport_event_id: str
    promotion_event_id: str
    passport_signer_key_id: str
    promotion_signer_key_id: str
    expires_at: str
    passport_resolution_sha256: str
    promotion_resolution_sha256: str
    authority_state_sha256: str
    authority_kill_generation: int
    authority_desired_mode_revision: int
    authority_ledger_head_sequence: int
    authority_ledger_head_digest: str
    authority_valid_until: str

    def evidence(self) -> dict[str, Any]:
        return {
            "strategy_hash": self.strategy_hash,
            "passport_hash": self.passport_hash,
            "promotion_hash": self.promotion_hash,
            "authorized_instrument": self.authorized_instrument,
            "maximum_loss_cents": self.maximum_loss_cents,
            "policy_epoch": self.policy_epoch,
            "capital_envelope_id": self.capital_envelope_id,
            "capital_event_id": self.capital_event_id,
            "capital_body_digest": self.capital_body_digest,
            "capital_fencing_generation": self.capital_fencing_generation,
            "passport_event_id": self.passport_event_id,
            "promotion_event_id": self.promotion_event_id,
            "passport_signer_key_id": self.passport_signer_key_id,
            "promotion_signer_key_id": self.promotion_signer_key_id,
            "expires_at": self.expires_at,
            "passport_resolution_sha256": self.passport_resolution_sha256,
            "promotion_resolution_sha256": self.promotion_resolution_sha256,
            "authority_state_sha256": self.authority_state_sha256,
            "authority_kill_generation": self.authority_kill_generation,
            "authority_desired_mode_revision": (
                self.authority_desired_mode_revision
            ),
            "authority_ledger_head_sequence": (
                self.authority_ledger_head_sequence
            ),
            "authority_ledger_head_digest": self.authority_ledger_head_digest,
            "authority_valid_until": self.authority_valid_until,
        }


@dataclass(frozen=True)
class _ResolvedContract:
    response: dict[str, Any]
    signed: VerifiedSignedEnvelope
    body_not_before: datetime
    body_expires_at: datetime
    authority_state: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC_RE.fullmatch(value):
        raise LineageResolutionError(f"{field} must be canonical RFC3339 UTC")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise LineageResolutionError(f"{field} must be a lowercase sha256")
    return value


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise LineageResolutionError(f"{field} must be a canonical identifier")
    return value


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LineageResolutionError(f"{field} must be a positive integer")
    return value


def _sorted_hashes(
    value: Any,
    *,
    field: str,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "an array" if allow_empty else "a nonempty array"
        raise LineageResolutionError(f"{field} must be {qualifier}")
    result = tuple(_digest(item, field=f"{field}[]") for item in value)
    if result != tuple(sorted(set(result))):
        raise LineageResolutionError(f"{field} must be sorted and unique")
    return result


def _sorted_identifiers(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise LineageResolutionError(f"{field} must be a nonempty array")
    result = tuple(_identifier(item, field=f"{field}[]") for item in value)
    if result != tuple(sorted(set(result))):
        raise LineageResolutionError(f"{field} must be sorted and unique")
    return result


def _decode_signature(value: Any) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or "=" in value
        or re.search(r"[^A-Za-z0-9_-]", value)
    ):
        raise LineageResolutionError("signature must be unpadded base64url")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise LineageResolutionError("signature is invalid base64url") from exc
    if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != value:
        raise LineageResolutionError("signature is not canonical base64url")
    return decoded


def _keyring(
    raw: Mapping[str, bytes | Ed25519PublicKey],
    *,
    role: str,
    maximum_keys: int = 16,
) -> dict[str, bytes]:
    if not isinstance(raw, Mapping) or not 1 <= len(raw) <= maximum_keys:
        raise ValueError(
            f"{role} keyring must contain 1 to {maximum_keys} keys"
        )
    result: dict[str, bytes] = {}
    for raw_key_id, material in raw.items():
        key_id = _digest(raw_key_id, field=f"{role} key id")
        key = (
            material.public_bytes_raw()
            if isinstance(material, Ed25519PublicKey)
            else bytes(material)
        )
        if len(key) != 32 or hashlib.sha256(key).hexdigest() != key_id:
            raise ValueError(f"{role} key id does not bind its Ed25519 key")
        result[key_id] = key
    return result


def _strict_json(body: bytes, *, maximum_bytes: int) -> dict[str, Any]:
    if not isinstance(body, bytes):
        raise LineageResolutionError("contract response body must be bytes")
    if not body or len(body) > maximum_bytes:
        raise LineageResolutionError("contract response size is invalid")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise LineageResolutionError(
                    f"contract response contains duplicate key {key!r}"
                )
            value[key] = item
        return value

    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                LineageResolutionError(
                    f"contract response contains non-finite value {token}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LineageResolutionError("contract response is not strict JSON") from exc
    if not isinstance(value, dict):
        raise LineageResolutionError("contract response must be an object")
    return value


def _validate_checkpoint(
    checkpoint_raw: Any,
    signature_raw: Any,
    *,
    core_keys: Mapping[str, bytes],
) -> dict[str, Any]:
    if not isinstance(checkpoint_raw, dict) or not isinstance(signature_raw, dict):
        raise LineageResolutionError(
            "contract checkpoint and signature must be objects"
        )
    checkpoint = json.loads(canonical_json(checkpoint_raw))
    signature = json.loads(canonical_json(signature_raw))
    if (
        set(checkpoint) != _CHECKPOINT_FIELDS
        or checkpoint.get("schema")
        != CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA
    ):
        raise LineageResolutionError("contract checkpoint fields mismatch")
    if set(signature) != _SIGNATURE_FIELDS:
        raise LineageResolutionError("contract checkpoint signature fields mismatch")
    if signature["algorithm"] != "Ed25519":
        raise LineageResolutionError("contract checkpoint algorithm mismatch")
    signer = _digest(
        signature["signer_key_id"],
        field="contract checkpoint signer_key_id",
    )
    public_key = core_keys.get(signer)
    if public_key is None:
        raise LineageResolutionError("contract checkpoint signer is not pinned Core")
    raw_signature = _decode_signature(signature["signature"])
    if len(raw_signature) != 64:
        raise LineageResolutionError(
            "contract checkpoint signature must be 64 bytes"
        )
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            raw_signature,
            canonical_json(checkpoint).encode("utf-8"),
        )
    except (InvalidSignature, ValueError) as exc:
        raise LineageResolutionError(
            "contract checkpoint signature is invalid"
        ) from exc
    return cast(dict[str, Any], checkpoint)


def _validate_ledger_proof(
    proof_raw: Any,
    *,
    signed: VerifiedSignedEnvelope,
    expected_schema: str,
    observed_at: datetime,
) -> dict[str, Any]:
    if not isinstance(proof_raw, dict):
        raise LineageResolutionError("contract ledger proof must be an object")
    proof = json.loads(canonical_json(proof_raw))
    if (
        set(proof) != _LEDGER_PROOF_FIELDS
        or proof.get("schema") != LEDGER_PROOF_SCHEMA
    ):
        raise LineageResolutionError("contract ledger proof fields mismatch")
    global_sequence = _positive_int(
        proof["global_sequence"],
        field="ledger global_sequence",
    )
    source_sequence = _positive_int(
        proof["source_sequence"],
        field="ledger source_sequence",
    )
    event_id = _digest(proof["event_id"], field="ledger event_id")
    event_digest = _digest(proof["event_digest"], field="ledger event_digest")
    payload_digest = _digest(
        proof["payload_digest"],
        field="ledger payload_digest",
    )
    previous_source = _digest(
        proof["previous_source_digest"],
        field="ledger previous_source_digest",
    )
    previous_global = _digest(
        proof["previous_global_digest"],
        field="ledger previous_global_digest",
    )
    source_id = _identifier(proof["source_id"], field="ledger source_id")
    signer = _digest(proof["signer_key_id"], field="ledger signer_key_id")
    nonce = _identifier(proof["nonce"], field="ledger nonce")
    event_schema = _identifier(proof["event_schema"], field="ledger event_schema")
    correlation = _identifier(
        proof["correlation_id"],
        field="ledger correlation_id",
    )
    causation = proof["causation_id"]
    if causation is not None:
        causation = _digest(causation, field="ledger causation_id")
    record_observed = _parse_utc(
        proof["observed_at"],
        field="ledger observed_at",
    )
    received_at = _parse_utc(proof["received_at"], field="ledger received_at")
    if received_at > observed_at:
        raise LineageResolutionError(
            "ledger proof was received after contract observation"
        )
    if record_observed != max(received_at, signed.not_before):
        raise LineageResolutionError(
            "ledger proof observed_at differs from ingestion semantics"
        )
    if (global_sequence == 1) != (previous_global == ZERO_DIGEST):
        raise LineageResolutionError("ledger previous_global_digest mismatch")
    if (source_sequence == 1) != (previous_source == ZERO_DIGEST):
        raise LineageResolutionError("ledger previous_source_digest mismatch")
    wrapper = signed.wrapper
    duplicated = {
        "event_id": (event_id, signed.event_id),
        "source_id": (source_id, signed.source_id),
        "source_sequence": (source_sequence, signed.source_sequence),
        "signer_key_id": (signer, signed.signer_key_id),
        "nonce": (nonce, signed.nonce),
        "event_schema": (event_schema, expected_schema),
        "correlation_id": (correlation, wrapper["correlation_id"]),
        "causation_id": (causation, wrapper["causation_id"]),
        "payload_digest": (payload_digest, wrapper["body_digest"]),
    }
    for field, (actual, expected) in duplicated.items():
        if actual != expected:
            raise LineageResolutionError(
                f"ledger proof {field} differs from contract envelope"
            )
    event_material = {
        key: item
        for key, item in proof.items()
        if key not in {"schema", "event_digest"}
    }
    if sha256_json(event_material) != event_digest:
        raise LineageResolutionError(
            "ledger proof event_digest does not match event material"
        )
    return cast(dict[str, Any], proof)


def _validate_authority_state(
    raw_state: Any,
    *,
    capital: VerifiedCapitalEnvelope,
    now: datetime,
    evaluator_keys: Mapping[str, bytes],
    maximum_resolution_age: timedelta,
    maximum_future_skew: timedelta,
) -> dict[str, Any]:
    """Validate the complete Core-signed authority projection.

    The verdict documents themselves remain Core ledger records; this
    projection pins their event identities and requires their signer key IDs
    to belong to the sealed evaluator role. The surrounding checkpoint signs
    every byte of this state.
    """
    if not isinstance(raw_state, dict):
        raise LineageResolutionError(
            "contract authority_state must be an object"
        )
    state = json.loads(canonical_json(raw_state))
    if (
        set(state) != _AUTHORITY_STATE_FIELDS
        or state.get("schema") != AUTHORITY_STATE_SCHEMA
    ):
        raise LineageResolutionError("contract authority_state fields mismatch")

    evaluated_at = _parse_utc(
        state["evaluated_at"],
        field="authority_state evaluated_at",
    )
    valid_until = _parse_utc(
        state["authority_valid_until"],
        field="authority_state authority_valid_until",
    )
    if evaluated_at > now + maximum_future_skew:
        raise LineageResolutionError("contract authority_state is future-dated")
    if now - evaluated_at > maximum_resolution_age:
        raise LineageResolutionError("contract authority_state is stale")
    if not evaluated_at < valid_until or not now < valid_until:
        raise LineageResolutionError(
            "contract authority_state validity window is not current"
        )
    if (
        capital.ledger_event_digest is None
        or capital.ledger_global_sequence is None
    ):
        raise LineageResolutionError(
            "active capital lacks its authenticated Core ledger binding"
        )
    expected = {
        "policy_epoch": capital.policy_epoch,
        "mandate_id": capital.body["mandate_id"],
        "kill_clear": True,
        "desired_mode": "LIVE",
        "capital_envelope_digest": sha256_json(capital.body),
        "capital_event_digest": capital.ledger_event_digest,
        "fencing_generation": capital.fencing_generation,
        "strategy_hash": capital.strategy_hashes[0],
        "passport_digest": capital.passport_hashes[0],
        "promotion_digest": capital.promotion_hashes[0],
    }
    for field, value in expected.items():
        if state.get(field) != value:
            raise LineageResolutionError(
                f"contract authority_state {field} differs from active authority"
            )
    for field in (
        "kill_generation",
        "desired_mode_revision",
        "ledger_head_sequence",
    ):
        _positive_int(state[field], field=f"authority_state {field}")
    for field in (
        "mandate_event_digest",
        "kill_event_digest",
        "desired_mode_event_digest",
        "capital_event_digest",
        "passport_event_digest",
        "promotion_event_digest",
        "ledger_head_digest",
    ):
        _digest(state[field], field=f"authority_state {field}")

    capital_sequence = capital.ledger_global_sequence
    head_sequence = int(state["ledger_head_sequence"])
    if head_sequence < capital_sequence or (
        head_sequence == capital_sequence
        and state["ledger_head_digest"] != capital.ledger_event_digest
    ):
        raise LineageResolutionError(
            "active capital is not continuous with the authority ledger head"
        )

    verdicts = state["verdicts"]
    if not isinstance(verdicts, list) or len(verdicts) < 2:
        raise LineageResolutionError(
            "contract authority_state requires at least two PASS verdicts"
        )
    facts: set[tuple[str, str, str, str]] = set()
    courts: set[str] = set()
    for index, raw_verdict in enumerate(verdicts):
        if not isinstance(raw_verdict, dict):
            raise LineageResolutionError(
                f"authority_state verdict {index} must be an object"
            )
        verdict = json.loads(canonical_json(raw_verdict))
        if set(verdict) != _AUTHORITY_VERDICT_FIELDS:
            raise LineageResolutionError(
                f"authority_state verdict {index} fields mismatch"
            )
        verdict_digest = _digest(
            verdict["verdict_digest"],
            field=f"authority_state verdict {index} digest",
        )
        event_digest = _digest(
            verdict["verdict_event_digest"],
            field=f"authority_state verdict {index} event_digest",
        )
        verdict_id = _identifier(
            verdict["verdict_id"],
            field=f"authority_state verdict {index} id",
        )
        court = verdict["court"]
        if (
            court not in _VERDICT_COURTS
            or verdict["decision"] != "PASS"
        ):
            raise LineageResolutionError(
                "contract authority verdict is not a recognized PASS"
            )
        signer = _digest(
            verdict["signer_key_id"],
            field=f"authority_state verdict {index} signer_key_id",
        )
        if signer not in evaluator_keys:
            raise LineageResolutionError(
                "contract authority verdict signer is not sealed"
            )
        verdict_evaluated = _parse_utc(
            verdict["evaluated_at"],
            field=f"authority_state verdict {index} evaluated_at",
        )
        verdict_expires = _parse_utc(
            verdict["expires_at"],
            field=f"authority_state verdict {index} expires_at",
        )
        transport_expires = _parse_utc(
            verdict["transport_expires_at"],
            field=f"authority_state verdict {index} transport_expires_at",
        )
        if (
            verdict_evaluated > now + maximum_future_skew
            or not verdict_evaluated < verdict_expires
            or not now < verdict_expires
            or not now < transport_expires
            or valid_until > min(verdict_expires, transport_expires)
        ):
            raise LineageResolutionError(
                "contract authority verdict is stale, future-dated, or expired"
            )
        facts.add((verdict_digest, event_digest, verdict_id, court))
        courts.add(court)
    if len(facts) != len(verdicts) or len(courts) < 2:
        raise LineageResolutionError(
            "contract authority verdict facts or courts are not unique"
        )
    return cast(dict[str, Any], state)


def _validate_passport(
    signed: VerifiedSignedEnvelope,
    *,
    now: datetime,
) -> tuple[datetime, datetime]:
    body = signed.body
    if set(body) != _PASSPORT_FIELDS:
        raise LineageResolutionError("AlphaPassport fields mismatch")
    if body["schema"] != ALPHA_PASSPORT_SCHEMA or body["venue"] != CELL_ID:
        raise LineageResolutionError("AlphaPassport identity mismatch")
    _identifier(body["passport_id"], field="passport_id")
    _identifier(body["strategy_lineage_id"], field="strategy_lineage_id")
    _digest(body["strategy_hash"], field="passport strategy_hash")
    _sorted_hashes(body["artifact_hashes"], field="passport artifact_hashes")
    _sorted_hashes(
        body["evidence_verdict_hashes"],
        field="passport evidence_verdict_hashes",
        allow_empty=True,
    )
    instruments = _sorted_identifiers(
        body["intended_instruments"],
        field="passport intended_instruments",
    )
    if any(
        not item.startswith("event_contract:")
        or item.endswith(":")
        or "*" in item
        for item in instruments
    ):
        raise LineageResolutionError(
            "AlphaPassport contains a noncanonical Dummy instrument"
        )
    _positive_int(body["maximum_loss_cents"], field="passport maximum_loss_cents")
    if body["evidence_class"] not in EVIDENCE_CLASSES:
        raise LineageResolutionError("AlphaPassport evidence_class is unsupported")
    starts = _parse_utc(body["created_at"], field="passport created_at")
    expires = _parse_utc(body["expires_at"], field="passport expires_at")
    if expires <= starts or not starts <= now < expires:
        raise LineageResolutionError("AlphaPassport body window is not current")
    return starts, expires


def _validate_promotion(
    signed: VerifiedSignedEnvelope,
    *,
    now: datetime,
) -> tuple[datetime, datetime]:
    body = signed.body
    if set(body) != _PROMOTION_FIELDS:
        raise LineageResolutionError("PromotionCertificate fields mismatch")
    if body["schema"] != PROMOTION_CERTIFICATE_SCHEMA or body["venue"] != CELL_ID:
        raise LineageResolutionError("PromotionCertificate identity mismatch")
    _identifier(body["certificate_id"], field="certificate_id")
    _digest(body["passport_digest"], field="promotion passport_digest")
    _sorted_hashes(body["verdict_digests"], field="promotion verdict_digests")
    if body["stage"] not in LIVE_PROMOTION_STAGES:
        raise LineageResolutionError(
            "PromotionCertificate stage is not live-authorizing"
        )
    instruments = _sorted_identifiers(
        body["instruments"],
        field="promotion instruments",
    )
    if any(
        not item.startswith("event_contract:")
        or item.endswith(":")
        or "*" in item
        for item in instruments
    ):
        raise LineageResolutionError(
            "PromotionCertificate contains a noncanonical Dummy instrument"
        )
    _positive_int(
        body["maximum_loss_cents"],
        field="promotion maximum_loss_cents",
    )
    _sorted_identifiers(
        body["rollback_triggers"],
        field="promotion rollback_triggers",
    )
    _positive_int(body["policy_epoch"], field="promotion policy_epoch")
    starts = _parse_utc(body["not_before"], field="promotion not_before")
    expires = _parse_utc(body["expires_at"], field="promotion expires_at")
    if expires <= starts or not starts <= now < expires:
        raise LineageResolutionError(
            "PromotionCertificate body window is not current"
        )
    return starts, expires


class CoreAuthorityContractResolver:
    """Fetch and authenticate the exact singleton lineage named by capital."""

    def __init__(
        self,
        *,
        transport: ContractResolutionTransport,
        cell_token_provider: Callable[[], str],
        trusted_core_public_keys: Mapping[
            str,
            bytes | Ed25519PublicKey,
        ],
        trusted_research_public_keys: Mapping[
            str,
            bytes | Ed25519PublicKey,
        ],
        trusted_promoter_public_keys: Mapping[
            str,
            bytes | Ed25519PublicKey,
        ],
        trusted_evaluator_public_keys: Mapping[
            str,
            bytes | Ed25519PublicKey,
        ],
        now_fn: Callable[[], datetime] | None = None,
        request_nonce_fn: Callable[[], str] | None = None,
        maximum_response_bytes: int = 1_048_576,
        maximum_resolution_age: timedelta = timedelta(seconds=60),
        maximum_future_skew: timedelta = timedelta(seconds=5),
    ) -> None:
        if not callable(transport) or not callable(cell_token_provider):
            raise TypeError("resolver transport and token provider must be callable")
        if request_nonce_fn is not None and not callable(request_nonce_fn):
            raise TypeError("resolver nonce provider must be callable")
        if maximum_response_bytes < 1:
            raise ValueError("maximum response bytes must be positive")
        if maximum_resolution_age <= timedelta(0):
            raise ValueError("maximum resolution age must be positive")
        if maximum_future_skew < timedelta(0):
            raise ValueError("maximum future skew cannot be negative")
        core = _keyring(trusted_core_public_keys, role="Core")
        research = _keyring(trusted_research_public_keys, role="research")
        promoter = _keyring(trusted_promoter_public_keys, role="promoter")
        evaluator = _keyring(
            trusted_evaluator_public_keys,
            role="evaluator",
            maximum_keys=32,
        )
        if set(core) & set(research) or set(core) & set(promoter):
            raise ValueError("Core and contract signing roles must be disjoint")
        if set(research) & set(promoter):
            raise ValueError("research and promoter signing roles must be disjoint")
        if (
            set(evaluator) & set(core)
            or set(evaluator) & set(research)
            or set(evaluator) & set(promoter)
        ):
            raise ValueError(
                "evaluator and control/contract signing roles must be disjoint"
            )
        self._transport = transport
        self._cell_token_provider = cell_token_provider
        self._core_keys = core
        self._research_keys = research
        self._promoter_keys = promoter
        self._evaluator_keys = evaluator
        self._now_fn = now_fn or _utc_now
        self._request_nonce_fn = request_nonce_fn or (
            lambda: secrets.token_hex(32)
        )
        self._nonce_lock = threading.Lock()
        self._last_nonce: str | None = None
        self.maximum_response_bytes = maximum_response_bytes
        self.maximum_resolution_age = maximum_resolution_age
        self.maximum_future_skew = maximum_future_skew

    def _now(self) -> datetime:
        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            raise LineageResolutionError(
                "contract resolver clock must be timezone-aware"
            )
        return now.astimezone(timezone.utc)

    def _nonce(self) -> str:
        try:
            nonce = _digest(
                self._request_nonce_fn(),
                field="contract request_nonce",
            )
        except Exception as exc:
            raise LineageResolutionError(
                "cryptographic contract nonce generation failed"
            ) from exc
        with self._nonce_lock:
            if nonce == self._last_nonce:
                raise LineageResolutionError("contract request nonce replay")
            self._last_nonce = nonce
        return nonce

    def _token(self) -> str:
        try:
            token = self._cell_token_provider()
        except Exception as exc:
            raise LineageResolutionError(
                "cell bearer retrieval failed closed"
            ) from exc
        if (
            not isinstance(token, str)
            or token != token.strip()
            or not 32 <= len(token) <= 4096
            or any(ord(char) < 33 or ord(char) > 126 for char in token)
        ):
            raise LineageResolutionError("cell bearer is invalid")
        return token

    def _resolve(
        self,
        *,
        digest: str,
        expected_schema: str,
        capital: VerifiedCapitalEnvelope,
    ) -> _ResolvedContract:
        requested_digest = _digest(digest, field="requested contract digest")
        capital_digest = _digest(
            sha256_json(capital.body),
            field="active capital body digest",
        )
        if expected_schema not in {
            ALPHA_PASSPORT_SCHEMA,
            PROMOTION_CERTIFICATE_SCHEMA,
        }:
            raise LineageResolutionError("requested contract schema is unsupported")
        fence = _positive_int(
            capital.fencing_generation,
            field="active capital fencing generation",
        )
        request_nonce = self._nonce()
        query = urlencode(
            {
                "capital_envelope_digest": capital_digest,
                "request_nonce": request_nonce,
            }
        )
        path = (
            f"/v1/cells/{CELL_ID}/contracts/{requested_digest}?{query}"
        )
        try:
            response = self._transport(
                path,
                {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._token()}",
                },
            )
        except Exception as exc:
            raise LineageResolutionError(
                f"contract transport failed closed:{type(exc).__name__}"
            ) from exc
        if not isinstance(response, ContractResolutionResponse):
            raise LineageResolutionError(
                "contract transport returned an unsupported response"
            )
        if isinstance(response.status_code, bool) or not isinstance(
            response.status_code,
            int,
        ):
            raise LineageResolutionError("contract response status is invalid")
        if response.status_code in {401, 403}:
            raise LineageResolutionError(
                "contract resolution authentication or scope was denied"
            )
        if response.status_code != 200:
            raise LineageResolutionError(
                f"contract resolver returned HTTP {response.status_code}"
            )
        payload = _strict_json(
            response.body,
            maximum_bytes=self.maximum_response_bytes,
        )
        now = self._now()
        if (
            set(payload) != _RESPONSE_FIELDS
            or payload.get("schema") != CONTRACT_RESOLUTION_SCHEMA
        ):
            raise LineageResolutionError("contract resolution fields mismatch")
        checkpoint = _validate_checkpoint(
            payload["checkpoint"],
            payload["checkpoint_signature"],
            core_keys=self._core_keys,
        )
        expected_checkpoint = {
            key: item
            for key, item in payload.items()
            if key not in {"schema", "checkpoint", "checkpoint_signature"}
        }
        expected_checkpoint["schema"] = (
            CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA
        )
        if checkpoint != expected_checkpoint:
            raise LineageResolutionError(
                "signed checkpoint does not bind the full contract resolution"
            )
        if payload["cell_id"] != CELL_ID:
            raise LineageResolutionError(
                "contract resolution targets another venue cell"
            )
        if (
            _digest(payload["request_nonce"], field="response request_nonce")
            != request_nonce
        ):
            raise LineageResolutionError("contract response nonce mismatch")
        if (
            _digest(
                payload["requested_body_digest"],
                field="response requested_body_digest",
            )
            != requested_digest
        ):
            raise LineageResolutionError("contract response digest mismatch")
        if (
            _digest(
                payload["capital_envelope_digest"],
                field="response capital_envelope_digest",
            )
            != capital_digest
        ):
            raise LineageResolutionError(
                "contract response is not bound to active capital"
            )
        if payload["fencing_generation"] != fence or isinstance(
            payload["fencing_generation"],
            bool,
        ):
            raise LineageResolutionError(
                "contract response is not bound to active capital fence"
            )
        if payload["contract_schema"] != expected_schema:
            raise LineageResolutionError("contract response schema mismatch")
        for field in (
            "transport_window_current",
            "body_window_current",
            "eligible_live_input",
        ):
            if not isinstance(payload[field], bool):
                raise LineageResolutionError(
                    f"contract response {field} must be boolean"
                )
        observed_at = _parse_utc(
            payload["observed_at"],
            field="contract observed_at",
        )
        if observed_at > now + self.maximum_future_skew:
            raise LineageResolutionError(
                "contract response observation is future-dated"
            )
        if now - observed_at > self.maximum_resolution_age:
            raise LineageResolutionError("contract response observation is stale")
        envelope = payload["envelope"]
        if not isinstance(envelope, dict):
            raise LineageResolutionError(
                "contract response envelope must be an object"
            )
        role_keys = (
            self._research_keys
            if expected_schema == ALPHA_PASSPORT_SCHEMA
            else self._promoter_keys
        )
        try:
            signed = verify_signed_envelope(
                envelope,
                trusted_public_keys=role_keys,
                now=now,
                expected_body_schema=expected_schema,
            )
        except ValueError as exc:
            raise LineageResolutionError(
                f"resolved signed contract invalid: {exc}"
            ) from exc
        if signed.wrapper["body_digest"] != requested_digest:
            raise LineageResolutionError(
                "resolved envelope body digest differs from request"
            )
        authority_state = _validate_authority_state(
            payload["authority_state"],
            capital=capital,
            now=now,
            evaluator_keys=self._evaluator_keys,
            maximum_resolution_age=self.maximum_resolution_age,
            maximum_future_skew=self.maximum_future_skew,
        )
        if (
            _parse_utc(
                authority_state["evaluated_at"],
                field="authority_state evaluated_at",
            )
            != observed_at
        ):
            raise LineageResolutionError(
                "contract authority_state evaluated_at does not mirror observed_at"
            )
        proof = _validate_ledger_proof(
            payload["ledger_proof"],
            signed=signed,
            expected_schema=expected_schema,
            observed_at=observed_at,
        )
        authority_event_digest = authority_state[
            (
                "promotion_event_digest"
                if expected_schema == PROMOTION_CERTIFICATE_SCHEMA
                else "passport_event_digest"
            )
        ]
        if proof["event_digest"] != authority_event_digest:
            raise LineageResolutionError(
                "contract proof event digest differs from authority_state"
            )
        proof_sequence = int(proof["global_sequence"])
        head_sequence = int(authority_state["ledger_head_sequence"])
        if proof_sequence > head_sequence or (
            proof_sequence == head_sequence
            and proof["event_digest"] != authority_state["ledger_head_digest"]
        ):
            raise LineageResolutionError(
                "contract proof is not continuous with the authority ledger head"
            )
        if expected_schema == ALPHA_PASSPORT_SCHEMA:
            body_starts, body_expires = _validate_passport(signed, now=now)
        else:
            body_starts, body_expires = _validate_promotion(signed, now=now)
        transport_current = (
            signed.not_before <= observed_at < signed.expires_at
        )
        body_current = body_starts <= observed_at < body_expires
        eligible = transport_current and body_current
        if expected_schema == PROMOTION_CERTIFICATE_SCHEMA:
            eligible = (
                eligible
                and signed.body["stage"] in LIVE_PROMOTION_STAGES
            )
        if payload["transport_window_current"] is not transport_current:
            raise LineageResolutionError(
                "contract transport-window projection mismatch"
            )
        if payload["body_window_current"] is not body_current:
            raise LineageResolutionError(
                "contract body-window projection mismatch"
            )
        if payload["eligible_live_input"] is not eligible:
            raise LineageResolutionError(
                "contract live-eligibility projection mismatch"
            )
        if not eligible:
            raise LineageResolutionError(
                "resolved contract is not an eligible current live input"
            )
        return _ResolvedContract(
            response=json.loads(canonical_json(payload)),
            signed=signed,
            body_not_before=body_starts,
            body_expires_at=body_expires,
            authority_state=authority_state,
        )

    def resolve_lineage(
        self,
        *,
        capital: VerifiedCapitalEnvelope,
        strategy_hash: str,
        passport_hash: str,
        promotion_hash: str,
        authorized_instrument: str,
        expected_binding: Mapping[str, Any] | None = None,
    ) -> VerifiedLineageBinding:
        """Resolve and bind the exact active singleton lineage."""
        now = self._now()
        strategy = _digest(strategy_hash, field="strategy_hash")
        passport = _digest(passport_hash, field="passport_hash")
        promotion = _digest(promotion_hash, field="promotion_hash")
        instrument = _identifier(
            authorized_instrument,
            field="authorized_instrument",
        )
        if (
            capital.venue != CELL_ID
            or capital.strategy_hashes != (strategy,)
            or capital.passport_hashes != (passport,)
            or capital.promotion_hashes != (promotion,)
            or instrument not in capital.authorized_instruments
        ):
            raise LineageResolutionError(
                "requested lineage differs from singleton capital authority"
            )
        capital_body_digest = sha256_json(capital.body)
        promotion_resolution = self._resolve(
            digest=promotion,
            expected_schema=PROMOTION_CERTIFICATE_SCHEMA,
            capital=capital,
        )
        passport_resolution = self._resolve(
            digest=passport,
            expected_schema=ALPHA_PASSPORT_SCHEMA,
            capital=capital,
        )
        promotion_authority = {
            key: item
            for key, item in promotion_resolution.authority_state.items()
            if key != "evaluated_at"
        }
        passport_authority = {
            key: item
            for key, item in passport_resolution.authority_state.items()
            if key != "evaluated_at"
        }
        if promotion_authority != passport_authority:
            raise LineageResolutionError(
                "promotion and passport were not resolved from one authority state"
            )
        promotion_body = promotion_resolution.signed.body
        passport_body = passport_resolution.signed.body
        if promotion_body["passport_digest"] != passport:
            raise LineageResolutionError(
                "promotion does not bind the singleton capital passport"
            )
        if passport_body["strategy_hash"] != strategy:
            raise LineageResolutionError(
                "passport does not bind the singleton capital strategy"
            )
        if (
            instrument not in passport_body["intended_instruments"]
            or instrument not in promotion_body["instruments"]
        ):
            raise LineageResolutionError(
                "instrument is not jointly authorized by lineage"
            )
        if promotion_body["policy_epoch"] != capital.policy_epoch:
            raise LineageResolutionError(
                "promotion and capital policy epochs differ"
            )
        lineage_loss = min(
            int(passport_body["maximum_loss_cents"]),
            int(promotion_body["maximum_loss_cents"]),
        )
        if capital.max_order_risk_cents > lineage_loss:
            raise LineageResolutionError(
                "capital order bound exceeds lineage maximum loss"
            )
        expires_at = min(
            capital.expires_at,
            passport_resolution.signed.expires_at,
            passport_resolution.body_expires_at,
            promotion_resolution.signed.expires_at,
            promotion_resolution.body_expires_at,
            _parse_utc(
                promotion_authority["authority_valid_until"],
                field="authority_state authority_valid_until",
            ),
        )
        if now >= expires_at:
            raise LineageResolutionError(
                "authenticated lineage binding is already expired"
            )
        binding = VerifiedLineageBinding(
            strategy_hash=strategy,
            passport_hash=passport,
            promotion_hash=promotion,
            authorized_instrument=instrument,
            maximum_loss_cents=lineage_loss,
            policy_epoch=capital.policy_epoch,
            capital_envelope_id=capital.envelope_id,
            capital_event_id=capital.event_id,
            capital_body_digest=capital_body_digest,
            capital_fencing_generation=capital.fencing_generation,
            passport_event_id=passport_resolution.signed.event_id,
            promotion_event_id=promotion_resolution.signed.event_id,
            passport_signer_key_id=passport_resolution.signed.signer_key_id,
            promotion_signer_key_id=promotion_resolution.signed.signer_key_id,
            expires_at=_format_utc(expires_at),
            passport_resolution_sha256=sha256_json(
                passport_resolution.response
            ),
            promotion_resolution_sha256=sha256_json(
                promotion_resolution.response
            ),
            authority_state_sha256=sha256_json(promotion_authority),
            authority_kill_generation=int(
                promotion_authority["kill_generation"]
            ),
            authority_desired_mode_revision=int(
                promotion_authority["desired_mode_revision"]
            ),
            authority_ledger_head_sequence=int(
                promotion_authority["ledger_head_sequence"]
            ),
            authority_ledger_head_digest=str(
                promotion_authority["ledger_head_digest"]
            ),
            authority_valid_until=str(
                promotion_authority["authority_valid_until"]
            ),
        )
        if expected_binding is not None:
            expected = json.loads(canonical_json(dict(expected_binding)))
            actual = binding.evidence()
            # A fresh resolution necessarily has a new request nonce and
            # therefore new page digests. Compare the signed contract/event
            # identity and complete authority relationship, not transport
            # transcript hashes from the earlier binding pass.
            expected.pop("passport_resolution_sha256", None)
            expected.pop("promotion_resolution_sha256", None)
            actual.pop("passport_resolution_sha256", None)
            actual.pop("promotion_resolution_sha256", None)
            if expected != actual:
                raise LineageResolutionError(
                    "lineage or active capital fence changed during execution"
                )
        return binding


__all__ = [
    "ALPHA_PASSPORT_SCHEMA",
    "CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA",
    "CONTRACT_RESOLUTION_SCHEMA",
    "ContractResolutionResponse",
    "ContractResolutionTransport",
    "CoreAuthorityContractResolver",
    "LineageResolutionError",
    "PROMOTION_CERTIFICATE_SCHEMA",
    "VerifiedLineageBinding",
]
