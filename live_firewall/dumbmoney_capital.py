"""DumbMoney signed capital-envelope adapter for Dummy's local firewall.

The adapter is venue-neutral at the wire level and configured here for a
specific expected venue/account.  A valid grant is only an additional upper
bound.  It cannot enable live submission, alter Dummy's local caps, provide
broker credentials, or establish cancellation authority.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from autonomy.fees import kalshi_taker_fee_cents
from live_firewall.dumbmoney_broker_witness import (
    BROKER_WITNESS_SOURCE_ID,
    SETTLEMENT_WITNESS_SCHEMA,
    TERMINAL_WITNESS_SCHEMA,
    WITNESS_TTL,
)
from live_firewall.operational_journal import (
    AppendOnlyOperationalJournal,
    OperationalJournalError,
    canonical_json,
    sha256_json,
)


SIGNED_ENVELOPE_SCHEMA = "dumbmoney.signed-envelope.v1"
CAPITAL_ENVELOPE_SCHEMA = "dumbmoney.capital-envelope.v1"
FLAT_BOOTSTRAP_SCHEMA = "dummy.broker-bootstrap.flat.v1"
INHERITED_BOOTSTRAP_SCHEMA = "dummy.broker-bootstrap.inherited-exposure.v1"
CAPITAL_RESERVATION_SCHEMA = "dummy.capital-reservation.v1"
CAPITAL_DISPATCH_CLAIM_SCHEMA = "dummy.capital-dispatch-claim.v1"
CAPITAL_POSITION_EXPOSURE_SCHEMA = "dummy.capital-position-exposure.v1"
CAPITAL_TERMINAL_RELEASE_SCHEMA = "dummy.capital-terminal-release.v1"
CAPITAL_POSITION_RELEASE_SCHEMA = "dummy.capital-position-release.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC_RE.fullmatch(value):
        raise ValueError(f"{field} must be canonical RFC3339 UTC")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field} must be a nonblank canonical string")
    return value


def _require_identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{field} must be a canonical identifier")
    return value


def _require_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase sha256")
    return value


def _require_int(value: Any, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def _require_hashes(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a nonempty sorted list")
    normalized = tuple(_require_sha256(item, field=field) for item in value)
    if list(normalized) != sorted(set(normalized)):
        raise ValueError(f"{field} must be sorted and unique")
    return normalized


def _require_identifiers(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a nonempty sorted list")
    normalized = tuple(
        _require_identifier(item, field=f"{field}[]") for item in value
    )
    if list(normalized) != sorted(set(normalized)):
        raise ValueError(f"{field} must be sorted and unique")
    return normalized


def _decode_base64url_no_padding(value: Any, *, field: str) -> bytes:
    if not isinstance(value, str) or not value or "=" in value:
        raise ValueError(f"{field} must be unpadded base64url")
    if re.search(r"[^A-Za-z0-9_-]", value):
        raise ValueError(f"{field} must be unpadded base64url")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise ValueError(f"{field} is invalid base64url") from exc
    encoded = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if encoded != value:
        raise ValueError(f"{field} is not canonical base64url")
    return decoded


def _public_key_bytes(value: bytes | Ed25519PublicKey) -> bytes:
    if isinstance(value, Ed25519PublicKey):
        return bytes(value.public_bytes_raw())
    raw = bytes(value)
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return raw


def strategy_binding_hash(reference: str) -> str:
    """Bind an existing proof/passport reference without changing its schema."""
    return hashlib.sha256(reference.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerifiedCapitalEnvelope:
    wrapper: dict[str, Any]
    body: dict[str, Any]
    event_id: str
    envelope_id: str
    source_id: str
    source_sequence: int
    nonce: str
    signer_key_id: str
    venue: str
    account_hash: str
    strategy_hashes: tuple[str, ...]
    passport_hashes: tuple[str, ...]
    promotion_hashes: tuple[str, ...]
    authorized_instruments: tuple[str, ...]
    authorized_mode: str
    max_order_risk_cents: int
    max_open_risk_cents: int
    max_correlated_risk_cents: int
    max_daily_loss_cents: int
    max_open_orders: int
    fencing_generation: int
    policy_epoch: int
    not_before: datetime
    expires_at: datetime
    ledger_event_digest: str | None = None
    ledger_global_sequence: int | None = None


@dataclass(frozen=True)
class VerifiedSignedEnvelope:
    """Cryptographically verified DumbMoney wrapper with an active window."""

    wrapper: dict[str, Any]
    body: dict[str, Any]
    event_id: str
    source_id: str
    source_sequence: int
    nonce: str
    signer_key_id: str
    body_schema: str
    not_before: datetime
    expires_at: datetime


@dataclass(frozen=True)
class CapitalVerdict:
    allow: bool
    reason: str
    rejected_by: str | None = None
    reservation_id: str | None = None
    effective_limits: dict[str, int] | None = None


class CapitalLineageResolver(Protocol):
    """Authenticate one exact singleton lineage through DumbMoney Core."""

    def resolve_lineage(
        self,
        *,
        capital: VerifiedCapitalEnvelope,
        strategy_hash: str,
        passport_hash: str,
        promotion_hash: str,
        authorized_instrument: str,
        expected_binding: Mapping[str, Any] | None = None,
    ) -> Any: ...


def verify_signed_envelope(
    wrapper: Mapping[str, Any],
    *,
    trusted_public_keys: Mapping[str, bytes | Ed25519PublicKey],
    now: datetime | None = None,
    expected_body_schema: str | None = None,
    max_ttl: timedelta | None = None,
    require_active: bool = True,
) -> VerifiedSignedEnvelope:
    """Validate a complete DumbMoney signed-envelope wrapper.

    This is the shared authority verifier for capital, kill, and desired-mode
    commands. It verifies exact wire shape, canonical hashes, signer binding,
    signature, and the active authority window. Body-specific semantics remain
    the responsibility of the receiving authority adapter.
    """
    value = json.loads(canonical_json(dict(wrapper)))
    if value.get("schema") != SIGNED_ENVELOPE_SCHEMA:
        raise ValueError("signed envelope schema mismatch")
    required_wrapper = {
        "schema",
        "source_id",
        "source_sequence",
        "event_id",
        "correlation_id",
        "causation_id",
        "nonce",
        "not_before",
        "expires_at",
        "body_schema",
        "body_digest",
        "body",
        "signature_algorithm",
        "signer_key_id",
        "signature",
    }
    if set(value) != required_wrapper:
        raise ValueError("signed envelope fields mismatch")
    source_id = _require_identifier(value["source_id"], field="source_id")
    source_sequence = _require_int(
        value["source_sequence"], field="source_sequence", minimum=1
    )
    event_id = _require_sha256(value["event_id"], field="event_id")
    _require_identifier(value["correlation_id"], field="correlation_id")
    if value["causation_id"] is not None:
        _require_sha256(value["causation_id"], field="causation_id")
    nonce = _require_identifier(value["nonce"], field="nonce")
    wrapper_not_before = _parse_utc(value["not_before"], field="not_before")
    wrapper_expires_at = _parse_utc(value["expires_at"], field="expires_at")
    body_schema = _require_identifier(value["body_schema"], field="body_schema")
    if expected_body_schema is not None and body_schema != expected_body_schema:
        raise ValueError("body schema mismatch")
    if value["signature_algorithm"] != "Ed25519":
        raise ValueError("signature algorithm mismatch")
    signer_key_id = _require_sha256(value["signer_key_id"], field="signer_key_id")
    body_digest = _require_sha256(value["body_digest"], field="body_digest")
    body = value["body"]
    if not isinstance(body, dict):
        raise ValueError("signed envelope body must be an object")
    if body.get("schema") != body_schema:
        raise ValueError("signed envelope body schema mismatch")
    if sha256_json(body) != body_digest:
        raise ValueError("signed envelope body digest mismatch")

    event_material = {
        key: item
        for key, item in value.items()
        if key not in {"event_id", "signature"}
    }
    if sha256_json(event_material) != event_id:
        raise ValueError("signed envelope event id mismatch")

    key_material = trusted_public_keys.get(signer_key_id)
    if key_material is None:
        raise ValueError("signer key is not trusted")
    raw_public_key = _public_key_bytes(key_material)
    if hashlib.sha256(raw_public_key).hexdigest() != signer_key_id:
        raise ValueError("signer key id does not match public key")
    signature = _decode_base64url_no_padding(
        value["signature"], field="signature"
    )
    if len(signature) != 64:
        raise ValueError("signed envelope signature must be 64 bytes")
    signed_material = {key: item for key, item in value.items() if key != "signature"}
    try:
        Ed25519PublicKey.from_public_bytes(raw_public_key).verify(
            signature,
            canonical_json(signed_material).encode("utf-8"),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("signed envelope signature invalid") from exc

    if wrapper_expires_at <= wrapper_not_before:
        raise ValueError("signed envelope authority window is invalid")
    if max_ttl is not None and wrapper_expires_at - wrapper_not_before > max_ttl:
        raise ValueError("signed envelope authority window exceeds maximum")
    if require_active:
        current = now or _utc_now()
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("verification clock must be timezone-aware")
        current = current.astimezone(timezone.utc)
        if current < wrapper_not_before:
            raise ValueError("signed envelope is not active yet")
        if current >= wrapper_expires_at:
            raise ValueError("signed envelope expired")

    return VerifiedSignedEnvelope(
        wrapper=value,
        body=body,
        event_id=event_id,
        source_id=source_id,
        source_sequence=source_sequence,
        nonce=nonce,
        signer_key_id=signer_key_id,
        body_schema=body_schema,
        not_before=wrapper_not_before,
        expires_at=wrapper_expires_at,
    )


def verify_signed_capital_envelope(
    wrapper: Mapping[str, Any],
    *,
    trusted_public_keys: Mapping[str, bytes | Ed25519PublicKey],
    expected_venue: str,
    expected_account_hash: str,
    now: datetime | None = None,
    max_ttl: timedelta = timedelta(minutes=5),
    require_active: bool = True,
) -> VerifiedCapitalEnvelope:
    """Validate the complete DumbMoney wrapper and capital body."""
    signed = verify_signed_envelope(
        wrapper,
        trusted_public_keys=trusted_public_keys,
        now=now,
        expected_body_schema=CAPITAL_ENVELOPE_SCHEMA,
        max_ttl=max_ttl,
        require_active=require_active,
    )
    value = signed.wrapper
    body = signed.body
    required_body = {
        "schema",
        "envelope_id",
        "mandate_id",
        "venue",
        "account_hash",
        "strategy_hashes",
        "passport_hashes",
        "promotion_hashes",
        "authorized_instruments",
        "authorized_mode",
        "max_order_risk_cents",
        "max_open_risk_cents",
        "max_correlated_risk_cents",
        "max_daily_loss_cents",
        "max_open_orders",
        "fencing_generation",
        "policy_epoch",
        "not_before",
        "expires_at",
    }
    if set(body) != required_body:
        raise ValueError("capital envelope fields mismatch")

    envelope_id = _require_sha256(body["envelope_id"], field="envelope_id")
    _require_sha256(body["mandate_id"], field="mandate_id")
    venue = _require_text(body["venue"], field="venue")
    if venue not in {"dummy_kalshi", "dopey_robinhood"}:
        raise ValueError("capital envelope venue is unsupported")
    if venue != expected_venue:
        raise ValueError("capital envelope venue mismatch")
    account_hash = _require_sha256(body["account_hash"], field="account_hash")
    if account_hash != _require_sha256(
        expected_account_hash, field="expected_account_hash"
    ):
        raise ValueError("capital envelope account mismatch")
    strategy_hashes = _require_hashes(body["strategy_hashes"], field="strategy_hashes")
    passport_hashes = _require_hashes(body["passport_hashes"], field="passport_hashes")
    promotion_hashes = _require_hashes(
        body["promotion_hashes"], field="promotion_hashes"
    )
    if not (
        len(strategy_hashes) == len(passport_hashes) == len(promotion_hashes)
    ):
        raise ValueError(
            "strategy, passport, and promotion hash counts must match"
        )
    if len(strategy_hashes) != 1:
        raise ValueError(
            "capital envelopes authorize exactly one "
            "strategy/passport/promotion tuple"
        )
    authorized_instruments = _require_identifiers(
        body["authorized_instruments"],
        field="authorized_instruments",
    )
    expected_prefixes = {
        "dummy_kalshi": ("event_contract:",),
        "dopey_robinhood": ("equity:", "option:"),
    }[venue]
    if any(
        not item.startswith(expected_prefixes)
        or item.endswith(":")
        or "*" in item
        for item in authorized_instruments
    ):
        raise ValueError("authorized instrument is invalid for venue")
    authorized_mode = _require_text(body["authorized_mode"], field="authorized_mode")
    if authorized_mode != "LIVE":
        raise ValueError("authorized_mode must be LIVE")
    max_order = _require_int(
        body["max_order_risk_cents"], field="max_order_risk_cents", minimum=1
    )
    max_open = _require_int(
        body["max_open_risk_cents"], field="max_open_risk_cents", minimum=1
    )
    max_correlated = _require_int(
        body["max_correlated_risk_cents"],
        field="max_correlated_risk_cents",
        minimum=1,
    )
    max_daily_loss = _require_int(
        body["max_daily_loss_cents"], field="max_daily_loss_cents", minimum=1
    )
    max_open_orders = _require_int(
        body["max_open_orders"], field="max_open_orders", minimum=1
    )
    if not max_order <= max_correlated <= max_open:
        raise ValueError("capital envelope limits are internally inconsistent")
    fencing_generation = _require_int(
        body["fencing_generation"], field="fencing_generation", minimum=1
    )
    policy_epoch = _require_int(
        body["policy_epoch"], field="policy_epoch", minimum=1
    )
    body_not_before = _parse_utc(body["not_before"], field="body.not_before")
    body_expires_at = _parse_utc(body["expires_at"], field="body.expires_at")
    if (
        body_not_before != signed.not_before
        or body_expires_at != signed.expires_at
    ):
        raise ValueError("wrapper and body authority windows differ")

    return VerifiedCapitalEnvelope(
        wrapper=value,
        body=body,
        event_id=signed.event_id,
        envelope_id=envelope_id,
        source_id=signed.source_id,
        source_sequence=signed.source_sequence,
        nonce=signed.nonce,
        signer_key_id=signed.signer_key_id,
        venue=venue,
        account_hash=account_hash,
        strategy_hashes=strategy_hashes,
        passport_hashes=passport_hashes,
        promotion_hashes=promotion_hashes,
        authorized_instruments=authorized_instruments,
        authorized_mode=authorized_mode,
        max_order_risk_cents=max_order,
        max_open_risk_cents=max_open,
        max_correlated_risk_cents=max_correlated,
        max_daily_loss_cents=max_daily_loss,
        max_open_orders=max_open_orders,
        fencing_generation=fencing_generation,
        policy_epoch=policy_epoch,
        not_before=body_not_before,
        expires_at=body_expires_at,
    )


def flat_book_receipt(
    *,
    receipt_id: str,
    venue: str,
    account_hash: str,
    observed_at: str,
    broker_snapshot_sha256: str,
) -> dict[str, Any]:
    return {
        "schema": FLAT_BOOTSTRAP_SCHEMA,
        "receipt_id": _require_text(receipt_id, field="receipt_id"),
        "venue": _require_text(venue, field="venue"),
        "account_hash": _require_sha256(account_hash, field="account_hash"),
        "observed_at": observed_at,
        "broker_snapshot_sha256": _require_sha256(
            broker_snapshot_sha256, field="broker_snapshot_sha256"
        ),
        "flat_book_observed": True,
        "total_exposure_cents": 0,
        "open_order_count": 0,
        "market_exposure_cents": {},
        "correlated_exposure_cents": {},
    }


def inherited_exposure_receipt(
    *,
    receipt_id: str,
    venue: str,
    account_hash: str,
    observed_at: str,
    broker_snapshot_sha256: str,
    total_exposure_cents: int,
    open_order_count: int,
    market_exposure_cents: Mapping[str, int],
    correlated_exposure_cents: Mapping[str, int],
) -> dict[str, Any]:
    total = _require_int(
        total_exposure_cents, field="total_exposure_cents", minimum=0
    )
    orders = _require_int(open_order_count, field="open_order_count", minimum=0)
    markets = {
        _require_text(str(key), field="market_exposure_key"): _require_int(
            item, field="market_exposure_cents", minimum=0
        )
        for key, item in market_exposure_cents.items()
    }
    correlated = {
        _require_text(str(key), field="correlated_exposure_key"): _require_int(
            item, field="correlated_exposure_cents", minimum=0
        )
        for key, item in correlated_exposure_cents.items()
    }
    if total == 0 and orders == 0:
        raise ValueError("inherited exposure receipt cannot represent a flat book")
    if sum(markets.values()) > total or max(correlated.values(), default=0) > total:
        raise ValueError("inherited exposure breakdown exceeds total exposure")
    return {
        "schema": INHERITED_BOOTSTRAP_SCHEMA,
        "receipt_id": _require_text(receipt_id, field="receipt_id"),
        "venue": _require_text(venue, field="venue"),
        "account_hash": _require_sha256(account_hash, field="account_hash"),
        "observed_at": observed_at,
        "broker_snapshot_sha256": _require_sha256(
            broker_snapshot_sha256, field="broker_snapshot_sha256"
        ),
        "flat_book_observed": False,
        "total_exposure_cents": total,
        "open_order_count": orders,
        "market_exposure_cents": markets,
        "correlated_exposure_cents": correlated,
    }


class CapitalEnvelopeAdapter:
    """Validate grants and durably reserve only bounded additional risk."""

    def __init__(
        self,
        *,
        journal: AppendOnlyOperationalJournal,
        trusted_public_keys: Mapping[str, bytes | Ed25519PublicKey],
        expected_venue: str,
        expected_account_hash: str,
        lineage_resolver: CapitalLineageResolver,
        trusted_broker_witness_public_keys: (
            Mapping[str, bytes | Ed25519PublicKey] | None
        ) = None,
        expected_subaccount_number: int = 0,
        now_fn: Callable[[], datetime] | None = None,
        max_envelope_ttl: timedelta = timedelta(minutes=5),
        max_bootstrap_age: timedelta = timedelta(minutes=5),
    ) -> None:
        self.journal = journal
        self.trusted_public_keys = dict(trusted_public_keys)
        self.trusted_broker_witness_public_keys = dict(
            trusted_broker_witness_public_keys or {}
        )
        self.expected_venue = expected_venue
        self.expected_account_hash = _require_sha256(
            expected_account_hash, field="expected_account_hash"
        )
        if (
            isinstance(expected_subaccount_number, bool)
            or not isinstance(expected_subaccount_number, int)
            or expected_subaccount_number != 0
        ):
            raise ValueError(
                "expected_subaccount_number must be 0 until end-to-end "
                "subaccount routing is sealed"
            )
        self.expected_subaccount_number = expected_subaccount_number
        if not hasattr(lineage_resolver, "resolve_lineage") or not callable(
            lineage_resolver.resolve_lineage
        ):
            raise TypeError("a Core authority lineage resolver is required")
        self.lineage_resolver = lineage_resolver
        self._now_fn = now_fn or _utc_now
        self.max_envelope_ttl = max_envelope_ttl
        self.max_bootstrap_age = max_bootstrap_age

    def _events(self, kind: str | None = None) -> tuple[dict[str, Any], ...]:
        if not self.journal.healthy:
            raise OperationalJournalError("capital journal is unhealthy")
        return tuple(
            dict(row) for row in self.journal.events(kind=kind)
        )

    def accept_signed_envelope(
        self,
        wrapper: Mapping[str, Any],
        *,
        ledger_event_digest: str | None = None,
        ledger_global_sequence: int | None = None,
    ) -> VerifiedCapitalEnvelope:
        verified = verify_signed_capital_envelope(
            wrapper,
            trusted_public_keys=self.trusted_public_keys,
            expected_venue=self.expected_venue,
            expected_account_hash=self.expected_account_hash,
            now=self._now_fn(),
            max_ttl=self.max_envelope_ttl,
        )
        if (ledger_event_digest is None) != (ledger_global_sequence is None):
            raise ValueError(
                "capital ledger digest and global sequence must be supplied together"
            )
        if ledger_event_digest is not None:
            verified = replace(
                verified,
                ledger_event_digest=_require_sha256(
                    ledger_event_digest,
                    field="capital ledger_event_digest",
                ),
                ledger_global_sequence=_require_int(
                    ledger_global_sequence,
                    field="capital ledger_global_sequence",
                    minimum=1,
                ),
            )
        payload = {
            "event_id": verified.event_id,
            "envelope_id": verified.envelope_id,
            "source_id": verified.source_id,
            "source_sequence": verified.source_sequence,
            "nonce": verified.nonce,
            "fencing_generation": verified.fencing_generation,
            "ledger_event_digest": verified.ledger_event_digest,
            "ledger_global_sequence": verified.ledger_global_sequence,
            "wrapper": verified.wrapper,
        }

        def validate_existing(rows: tuple[dict[str, Any], ...]) -> None:
            accepted = [
                row
                for row in rows
                if row.get("kind") == "capital.envelope.accepted"
            ]
            seen_nonce = {
                str(row["payload"].get("nonce"))
                for row in accepted
            }
            if verified.nonce in seen_nonce:
                raise ValueError("capital envelope nonce replay")
            source_rows = [
                row
                for row in accepted
                if row["payload"].get("source_id") == verified.source_id
            ]
            if source_rows:
                highest_sequence = max(
                    int(row["payload"]["source_sequence"])
                    for row in source_rows
                )
                if verified.source_sequence <= highest_sequence:
                    raise ValueError("capital envelope source sequence replay")
            highest_fence = max(
                (
                    int(row["payload"]["fencing_generation"])
                    for row in accepted
                ),
                default=0,
            )
            if (
                highest_fence
                and verified.fencing_generation <= highest_fence
            ):
                raise ValueError(
                    "capital envelope fencing generation is not strictly increasing"
                )
            highest_policy_epoch = max(
                (
                    int(row["payload"]["wrapper"]["body"]["policy_epoch"])
                    for row in accepted
                ),
                default=0,
            )
            if verified.policy_epoch < highest_policy_epoch:
                raise ValueError("capital envelope policy epoch regressed")

        self.journal.append(
            "capital.envelope.accepted",
            payload,
            outbox_id=f"capital-envelope:{verified.event_id}",
            validate_existing=validate_existing,
        )
        return verified

    def record_broker_bootstrap(
        self, receipt: Mapping[str, Any]
    ) -> dict[str, Any]:
        value = json.loads(canonical_json(dict(receipt)))
        schema = value.get("schema")
        if schema not in {FLAT_BOOTSTRAP_SCHEMA, INHERITED_BOOTSTRAP_SCHEMA}:
            raise ValueError("broker bootstrap receipt schema mismatch")
        if value.get("venue") != self.expected_venue:
            raise ValueError("broker bootstrap venue mismatch")
        if value.get("account_hash") != self.expected_account_hash:
            raise ValueError("broker bootstrap account mismatch")
        _require_text(value.get("receipt_id"), field="receipt_id")
        observed = _parse_utc(value.get("observed_at"), field="observed_at")
        now = self._now_fn().astimezone(timezone.utc)
        if observed > now + timedelta(seconds=5):
            raise ValueError("broker bootstrap receipt is from the future")
        if now - observed > self.max_bootstrap_age:
            raise ValueError("broker bootstrap receipt is stale")
        _require_sha256(
            value.get("broker_snapshot_sha256"), field="broker_snapshot_sha256"
        )
        total = _require_int(
            value.get("total_exposure_cents"),
            field="total_exposure_cents",
            minimum=0,
        )
        orders = _require_int(
            value.get("open_order_count"), field="open_order_count", minimum=0
        )
        markets = value.get("market_exposure_cents")
        correlated = value.get("correlated_exposure_cents")
        if not isinstance(markets, dict) or not isinstance(correlated, dict):
            raise ValueError("broker bootstrap exposure maps are required")
        for item in (*markets.values(), *correlated.values()):
            _require_int(item, field="bootstrap_exposure_cents", minimum=0)
        if schema == FLAT_BOOTSTRAP_SCHEMA:
            if (
                value.get("flat_book_observed") is not True
                or total != 0
                or orders != 0
                or markets
                or correlated
            ):
                raise ValueError("flat bootstrap receipt contains exposure")
        elif (
            value.get("flat_book_observed") is not False
            or (total == 0 and orders == 0)
        ):
            raise ValueError("inherited bootstrap receipt lacks exposure")
        def validate_existing(rows: tuple[dict[str, Any], ...]) -> None:
            prior_rows = [
                row
                for row in rows
                if row.get("kind") == "broker.bootstrap.recorded"
            ]
            if prior_rows:
                previous_observed = _parse_utc(
                    prior_rows[-1]["payload"]["observed_at"],
                    field="previous.observed_at",
                )
                if observed <= previous_observed:
                    raise ValueError(
                        "broker bootstrap observations must be strictly increasing"
                    )

        event = self.journal.append(
            "broker.bootstrap.recorded",
            value,
            outbox_id=f"broker-bootstrap:{value['receipt_id']}",
            validate_existing=validate_existing,
            validate_existing_latest_kinds=("broker.bootstrap.recorded",),
        )
        return dict(event)

    def _latest_bootstrap(self) -> dict[str, Any] | None:
        rows = self._events("broker.bootstrap.recorded")
        return dict(rows[-1]["payload"]) if rows else None

    def _accepted_envelopes(self) -> list[VerifiedCapitalEnvelope]:
        verified: list[VerifiedCapitalEnvelope] = []
        for row in self._events("capital.envelope.accepted"):
            try:
                accepted = verify_signed_capital_envelope(
                        row["payload"]["wrapper"],
                        trusted_public_keys=self.trusted_public_keys,
                        expected_venue=self.expected_venue,
                        expected_account_hash=self.expected_account_hash,
                        now=self._now_fn(),
                        max_ttl=self.max_envelope_ttl,
                    )
                ledger_digest = row["payload"].get("ledger_event_digest")
                ledger_sequence = row["payload"].get("ledger_global_sequence")
                if ledger_digest is not None or ledger_sequence is not None:
                    accepted = replace(
                        accepted,
                        ledger_event_digest=_require_sha256(
                            ledger_digest,
                            field="capital ledger_event_digest",
                        ),
                        ledger_global_sequence=_require_int(
                            ledger_sequence,
                            field="capital ledger_global_sequence",
                            minimum=1,
                        ),
                    )
                verified.append(
                    accepted
                )
            except ValueError:
                # Expired grants are normal history and are simply inactive.
                continue
        return verified

    def _maximum_accepted_fence(self) -> int:
        """Return the monotonic high-water fence, including expired grants."""
        return max(
            (
                int(row["payload"]["fencing_generation"])
                for row in self._events("capital.envelope.accepted")
            ),
            default=0,
        )

    def _active_reservations(self) -> list[dict[str, Any]]:
        reservations = {
            str(row["payload"]["reservation_id"]): dict(row["payload"])
            for row in self._events("capital.reservation.created")
        }
        released = {
            str(row["payload"]["reservation_id"])
            for row in self._events("capital.reservation.released")
        }
        return [
            value for key, value in reservations.items() if key not in released
        ]

    def _active_position_exposures(self) -> list[dict[str, Any]]:
        positions = {
            str(row["payload"]["position_exposure_id"]): dict(
                row["payload"]
            )
            for row in self._events("capital.position.exposure.recorded")
        }
        released = {
            str(row["payload"]["position_exposure_id"])
            for row in self._events("capital.position.exposure.released")
        }
        return [
            value for key, value in positions.items() if key not in released
        ]

    @staticmethod
    def _fee_inclusive_order_risk(
        request: Any,
    ) -> tuple[int, int, int]:
        size = _require_int(
            int(request.size),
            field="order_size",
            minimum=1,
        )
        price = _require_int(
            int(request.price_cents),
            field="order_price_cents",
            minimum=1,
        )
        if price > 100:
            raise ValueError("order_price_cents must be <= 100")
        notional = size * price
        # Reserve at the general taker schedule even for post-only makers.
        # This remains conservative if maker classification or the embedded
        # maker-series schedule changes before a fill is reconciled.
        fee = kalshi_taker_fee_cents(
            price,
            size,
            str(request.market_ticker),
        )
        return notional, fee, notional + fee

    def _cancel_only(self) -> bool:
        rows = self._events("authority.cancel_only")
        return bool(rows)

    def binding_for(
        self,
        *,
        strategy_hash: str,
        passport_hash: str,
        authorized_instrument: str,
        promotion_hash: str | None = None,
    ) -> dict[str, Any]:
        strategy = _require_sha256(strategy_hash, field="strategy_hash")
        passport = _require_sha256(passport_hash, field="passport_hash")
        instrument = _require_identifier(
            authorized_instrument,
            field="authorized_instrument",
        )
        promotion = (
            _require_sha256(promotion_hash, field="promotion_hash")
            if promotion_hash is not None
            else None
        )
        eligible = [
            envelope
            for envelope in self._accepted_envelopes()
            if envelope.authorized_mode == "LIVE"
            and envelope.fencing_generation == self._maximum_accepted_fence()
            and strategy in envelope.strategy_hashes
            and passport in envelope.passport_hashes
            and instrument in envelope.authorized_instruments
            and (
                promotion in envelope.promotion_hashes
                if promotion is not None
                else len(envelope.promotion_hashes) == 1
            )
        ]
        if not eligible:
            raise ValueError("no active capital envelope covers request lineage")
        selected = max(
            eligible,
            key=lambda item: (
                item.fencing_generation,
                item.source_sequence,
                item.expires_at,
            ),
        )
        selected_promotion = (
            promotion
            if promotion is not None
            else selected.promotion_hashes[0]
        )
        binding = self.lineage_resolver.resolve_lineage(
            capital=selected,
            strategy_hash=strategy,
            passport_hash=passport,
            promotion_hash=selected_promotion,
            authorized_instrument=instrument,
        )
        evidence = json.loads(canonical_json(binding.evidence()))
        # Resolution pages contain a fresh request nonce, so retain only the
        # stable, cryptographically authenticated identity for the sink's
        # independent revalidation.
        evidence.pop("passport_resolution_sha256", None)
        evidence.pop("promotion_resolution_sha256", None)
        lineage_id = sha256_json(evidence)
        self.journal.append(
            "capital.lineage.verified",
            {
                "lineage_id": lineage_id,
                "binding": evidence,
            },
            outbox_id=f"capital-lineage:{lineage_id}",
        )
        return {
            "capital_envelope_id": selected.envelope_id,
            "capital_strategy_hash": strategy,
            "capital_passport_hash": passport,
            "capital_promotion_hash": selected_promotion,
            "capital_fencing_generation": selected.fencing_generation,
        }

    @staticmethod
    def _correlation_key(market_ticker: str) -> str:
        return market_ticker.split("-", 1)[0].upper()

    @staticmethod
    def _request_order_terms(request: Any) -> dict[str, Any]:
        return {
            "proposal_id": str(request.proposal_id),
            "market_ticker": str(request.market_ticker),
            "contract_ticker": str(request.contract_ticker),
            "side": str(request.side),
            "size": int(request.size),
            "price_cents": int(request.price_cents),
            "expiration_ts": (
                int(request.expiration_ts)
                if getattr(request, "expiration_ts", None) is not None
                else None
            ),
            "liquidity_role": str(
                getattr(request, "liquidity_role", "maker") or "maker"
            ),
            "capital_envelope_id": str(
                getattr(request, "capital_envelope_id", "") or ""
            ),
            "capital_strategy_hash": str(
                getattr(request, "capital_strategy_hash", "") or ""
            ),
            "capital_passport_hash": str(
                getattr(request, "capital_passport_hash", "") or ""
            ),
            "capital_promotion_hash": str(
                getattr(request, "capital_promotion_hash", "") or ""
            ),
            "capital_fencing_generation": int(
                getattr(request, "capital_fencing_generation")
            ),
        }

    @staticmethod
    def _expected_broker_order(request: Any) -> dict[str, Any]:
        """Reconstruct the exact order payload authorized by the request.

        A dispatch claim is a broker-send capability, so hashing an arbitrary
        caller-supplied mapping is insufficient. Keep this fail-closed mirror
        of ``LiveBrokerFirewall._build_order`` until the broker wire contract
        is migrated as one atomic change.
        """
        side = str(request.side)
        if side not in {"yes", "no"}:
            raise ValueError("dispatch request side is invalid")
        count = _require_int(request.size, field="dispatch count", minimum=1)
        price = _require_int(
            request.price_cents,
            field="dispatch price_cents",
            minimum=1,
        )
        if price > 99:
            raise ValueError("dispatch price_cents must be <= 99")
        yes_price_cents = price if side == "yes" else 100 - price
        maker = (
            str(getattr(request, "liquidity_role", "maker") or "maker")
            == "maker"
        )
        expected: dict[str, Any] = {
            "ticker": _require_identifier(
                request.contract_ticker,
                field="dispatch ticker",
            ),
            "client_order_id": _require_identifier(
                request.proposal_id,
                field="dispatch client_order_id",
            ),
            "side": "bid" if side == "yes" else "ask",
            "count": f"{count}.00",
            "price": f"0.{yes_price_cents:02d}00",
            "time_in_force": (
                "good_till_canceled" if maker else "fill_or_kill"
            ),
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": maker,
            "cancel_order_on_pause": True,
            "reduce_only": False,
            "subaccount": 0,
            "exchange_index": 0,
        }
        expiration = getattr(request, "expiration_ts", None)
        if maker:
            if expiration is None:
                raise ValueError(
                    "dispatch maker order lacks exchange-enforced expiration"
                )
            expected["expiration_time"] = _require_int(
                expiration,
                field="dispatch expiration_time",
                minimum=1,
            )
        return expected

    def _resolve_envelope_for_request(self, request: Any) -> VerifiedCapitalEnvelope:
        envelope_id = str(getattr(request, "capital_envelope_id", "") or "")
        strategy_hash = str(getattr(request, "capital_strategy_hash", "") or "")
        passport_hash = str(getattr(request, "capital_passport_hash", "") or "")
        promotion_hash = str(getattr(request, "capital_promotion_hash", "") or "")
        contract_ticker = _require_identifier(
            str(getattr(request, "contract_ticker", "") or ""),
            field="contract_ticker",
        )
        authorized_instrument = f"event_contract:{contract_ticker}"
        try:
            fence = int(getattr(request, "capital_fencing_generation"))
        except (TypeError, ValueError):
            raise ValueError("capital fencing generation missing") from None
        candidates = [
            envelope
            for envelope in self._accepted_envelopes()
            if envelope.envelope_id == envelope_id
            and envelope.fencing_generation == fence
        ]
        if not candidates:
            raise ValueError("capital envelope is missing, expired, or fenced")
        envelope = max(candidates, key=lambda item: item.source_sequence)
        if envelope.authorized_mode != "LIVE":
            raise ValueError("capital envelope does not authorize LIVE mode")
        if strategy_hash not in envelope.strategy_hashes:
            raise ValueError("capital strategy hash mismatch")
        if passport_hash not in envelope.passport_hashes:
            raise ValueError("capital passport hash mismatch")
        if promotion_hash not in envelope.promotion_hashes:
            raise ValueError("capital promotion hash mismatch")
        if authorized_instrument not in envelope.authorized_instruments:
            raise ValueError("capital instrument is not authorized")
        highest_fence = self._maximum_accepted_fence()
        if fence != highest_fence:
            raise ValueError("capital envelope fencing generation is stale")
        prior_bindings = [
            row["payload"]["binding"]
            for row in self._events("capital.lineage.verified")
            if isinstance(row.get("payload", {}).get("binding"), dict)
        ]
        expected_binding = next(
            (
                binding
                for binding in reversed(prior_bindings)
                if binding.get("capital_envelope_id") == envelope.envelope_id
                and binding.get("capital_event_id") == envelope.event_id
                and binding.get("capital_body_digest")
                == sha256_json(envelope.body)
                and binding.get("capital_fencing_generation") == fence
                and binding.get("policy_epoch") == envelope.policy_epoch
                and binding.get("strategy_hash") == strategy_hash
                and binding.get("passport_hash") == passport_hash
                and binding.get("promotion_hash") == promotion_hash
                and binding.get("authorized_instrument")
                == authorized_instrument
            ),
            None,
        )
        binding = self.lineage_resolver.resolve_lineage(
            capital=envelope,
            strategy_hash=strategy_hash,
            passport_hash=passport_hash,
            promotion_hash=promotion_hash,
            authorized_instrument=authorized_instrument,
            expected_binding=expected_binding,
        )
        if expected_binding is None:
            # A manually assembled request cannot self-assert lineage. The
            # sink may establish the missing durable receipt only by resolving
            # both original signed contracts through Core immediately now.
            evidence = json.loads(canonical_json(binding.evidence()))
            evidence.pop("passport_resolution_sha256", None)
            evidence.pop("promotion_resolution_sha256", None)
            lineage_id = sha256_json(evidence)
            self.journal.append(
                "capital.lineage.verified",
                {
                    "lineage_id": lineage_id,
                    "binding": evidence,
                },
                outbox_id=f"capital-lineage:{lineage_id}",
            )
        return envelope

    def _verdict(
        self,
        request: Any,
        *,
        current_daily_loss_cents: int,
        current_local_total_exposure_cents: int = 0,
        current_local_correlated_exposure_cents: int = 0,
        current_local_open_orders: int = 0,
        current_request_locally_reserved: bool = False,
    ) -> tuple[CapitalVerdict, VerifiedCapitalEnvelope | None, dict[str, Any] | None]:
        if self._cancel_only():
            return (
                CapitalVerdict(
                    False,
                    "DumbMoney adapter is in cancel-only degraded mode",
                    "capital_cancel_only",
                ),
                None,
                None,
            )
        bootstrap = self._latest_bootstrap()
        if bootstrap is None:
            return (
                CapitalVerdict(
                    False,
                    "Fresh broker bootstrap receipt required; local absence is not flat",
                    "capital_broker_bootstrap",
                ),
                None,
                None,
            )
        try:
            observed = _parse_utc(bootstrap["observed_at"], field="observed_at")
            if self._now_fn().astimezone(timezone.utc) - observed > self.max_bootstrap_age:
                raise ValueError("broker bootstrap receipt is stale")
            envelope = self._resolve_envelope_for_request(request)
            _, _, order_risk = self._fee_inclusive_order_risk(request)
            daily_loss = _require_int(
                current_daily_loss_cents,
                field="current_daily_loss_cents",
                minimum=0,
            )
            local_total = _require_int(
                current_local_total_exposure_cents,
                field="current_local_total_exposure_cents",
                minimum=0,
            )
            local_correlated = _require_int(
                current_local_correlated_exposure_cents,
                field="current_local_correlated_exposure_cents",
                minimum=0,
            )
            local_open_orders = _require_int(
                current_local_open_orders,
                field="current_local_open_orders",
                minimum=0,
            )
        except Exception as exc:
            return (
                CapitalVerdict(False, str(exc), "capital_envelope"),
                None,
                bootstrap,
            )
        active = self._active_reservations()
        active_positions = self._active_position_exposures()
        proposal_id = str(request.proposal_id)
        terminal_witness = next(
            (
                row["payload"]
                for row in self._events(
                    "capital.terminal_reconciliation.witnessed"
                )
                if row["payload"].get("proposal_id") == proposal_id
            ),
            None,
        )
        if terminal_witness is not None:
            return (
                CapitalVerdict(
                    False,
                    "proposal id has a broker terminal witness and cannot be reused",
                    "capital_idempotency",
                ),
                envelope,
                bootstrap,
            )
        existing = next(
            (
                item
                for item in active
                if item.get("proposal_id") == proposal_id
            ),
            None,
        )
        if existing is not None:
            request_terms_sha256 = sha256_json(
                self._request_order_terms(request)
            )
            matches = (
                existing.get("envelope_id") == envelope.envelope_id
                and existing.get("market_ticker") == request.market_ticker
                and existing.get("contract_ticker")
                == request.contract_ticker
                and existing.get("side") == request.side
                and int(existing.get("size", -1)) == int(request.size)
                and int(existing.get("price_cents", -1)) == int(request.price_cents)
                and existing.get("account_hash") == envelope.account_hash
                and existing.get("venue") == envelope.venue
                and existing.get("strategy_hash")
                == str(request.capital_strategy_hash)
                and existing.get("passport_hash")
                == str(request.capital_passport_hash)
                and existing.get("promotion_hash")
                == str(request.capital_promotion_hash)
                and existing.get("order_terms_sha256")
                == request_terms_sha256
            )
            if not matches:
                return (
                    CapitalVerdict(
                        False,
                        "proposal id already reserved for different order terms",
                        "capital_idempotency",
                    ),
                    envelope,
                    bootstrap,
                )
        else:
            prior_terminal = next(
                (
                    row["payload"]
                    for row in self._events("capital.reservation.created")
                    if row["payload"].get("proposal_id") == proposal_id
                ),
                None,
            )
            if prior_terminal is not None:
                return (
                    CapitalVerdict(
                        False,
                        "proposal id has a terminal capital reservation and cannot be reused",
                        "capital_idempotency",
                    ),
                    envelope,
                    bootstrap,
                )
        inherited_total = int(bootstrap["total_exposure_cents"])
        inherited_orders = int(bootstrap["open_order_count"])
        reserved_total = sum(int(item["risk_cents"]) for item in active)
        position_total = sum(
            int(item["risk_cents"]) for item in active_positions
        )
        correlation_key = self._correlation_key(str(request.market_ticker))
        inherited_correlated = int(
            bootstrap["correlated_exposure_cents"].get(correlation_key, 0)
        )
        reserved_correlated = sum(
            int(item["risk_cents"])
            for item in active
            if item.get("correlation_key") == correlation_key
        )
        position_correlated = sum(
            int(item["risk_cents"])
            for item in active_positions
            if item.get("correlation_key") == correlation_key
        )
        adjusted_local_total = local_total
        adjusted_local_correlated = local_correlated
        adjusted_local_orders = local_open_orders
        if existing is not None and current_request_locally_reserved:
            existing_risk = int(existing["risk_cents"])
            if (
                adjusted_local_total < existing_risk
                or adjusted_local_correlated < existing_risk
                or adjusted_local_orders < 1
            ):
                return (
                    CapitalVerdict(
                        False,
                        "local reservation witness is inconsistent",
                        "capital_local_reservation",
                    ),
                    envelope,
                    bootstrap,
                )
            # This is the only overlap we can prove: the exact proposal is
            # present in both Dummy's local submission ledger and this
            # adapter's reservation journal. Preserve conservative addition
            # for every other exposure.
            adjusted_local_total -= existing_risk
            adjusted_local_correlated -= existing_risk
            adjusted_local_orders -= 1
        limits = {
            "max_order_risk_cents": envelope.max_order_risk_cents,
            "max_open_risk_cents": envelope.max_open_risk_cents,
            "max_correlated_risk_cents": envelope.max_correlated_risk_cents,
            "max_daily_loss_cents": envelope.max_daily_loss_cents,
            "max_open_orders": envelope.max_open_orders,
        }
        # These three books have no signed overlap proof. Treat them as
        # disjoint until reconciliation supplies one: using max() can mask a
        # post-bootstrap fill behind a larger inherited baseline after its
        # reservation is released. Conservative addition may double count an
        # order represented in both local and adapter state, but never grants
        # capital against exposure whose overlap is merely assumed.
        effective_open_risk = (
            inherited_total
            + reserved_total
            + position_total
            + adjusted_local_total
        )
        effective_correlated_risk = (
            inherited_correlated
            + reserved_correlated
            + position_correlated
            + adjusted_local_correlated
        )
        effective_open_orders = (
            inherited_orders + len(active) + adjusted_local_orders
        )
        if order_risk > envelope.max_order_risk_cents:
            reason = "DumbMoney maximum order risk exceeded"
        elif (
            effective_open_risk
            + (0 if existing is not None else order_risk)
            > envelope.max_open_risk_cents
        ):
            reason = "DumbMoney maximum open risk exceeded"
        elif (
            effective_correlated_risk
            + (0 if existing is not None else order_risk)
            > envelope.max_correlated_risk_cents
        ):
            reason = "DumbMoney maximum correlated risk exceeded"
        elif (
            order_risk
            > envelope.max_daily_loss_cents - daily_loss
        ):
            reason = "DumbMoney daily loss capacity exceeded"
        elif (
            effective_open_orders
            + (0 if existing is not None else 1)
            > envelope.max_open_orders
        ):
            reason = "DumbMoney maximum open orders reached"
        else:
            return (
                CapitalVerdict(
                    True,
                    (
                        "Existing durable DumbMoney reservation verified"
                        if existing is not None
                        else "Signed DumbMoney capital grant bounds verified"
                    ),
                    reservation_id=(
                        str(existing["reservation_id"])
                        if existing is not None
                        else None
                    ),
                    effective_limits=limits,
                ),
                envelope,
                bootstrap,
            )
        return (
            CapitalVerdict(
                False,
                reason,
                "capital_limits",
                effective_limits=limits,
            ),
            envelope,
            bootstrap,
        )

    def evaluate_request(
        self,
        request: Any,
        *,
        current_daily_loss_cents: int,
        current_local_total_exposure_cents: int = 0,
        current_local_correlated_exposure_cents: int = 0,
        current_local_open_orders: int = 0,
        current_request_locally_reserved: bool = False,
    ) -> CapitalVerdict:
        verdict, _, _ = self._verdict(
            request,
            current_daily_loss_cents=current_daily_loss_cents,
            current_local_total_exposure_cents=(
                current_local_total_exposure_cents
            ),
            current_local_correlated_exposure_cents=(
                current_local_correlated_exposure_cents
            ),
            current_local_open_orders=current_local_open_orders,
            current_request_locally_reserved=(
                current_request_locally_reserved
            ),
        )
        return verdict

    def reserve_request(
        self,
        request: Any,
        *,
        current_daily_loss_cents: int,
        current_local_total_exposure_cents: int = 0,
        current_local_correlated_exposure_cents: int = 0,
        current_local_open_orders: int = 0,
    ) -> CapitalVerdict:
        verdict, envelope, bootstrap = self._verdict(
            request,
            current_daily_loss_cents=current_daily_loss_cents,
            current_local_total_exposure_cents=(
                current_local_total_exposure_cents
            ),
            current_local_correlated_exposure_cents=(
                current_local_correlated_exposure_cents
            ),
            current_local_open_orders=current_local_open_orders,
        )
        if (
            not verdict.allow
            or envelope is None
            or bootstrap is None
            or verdict.reservation_id is not None
        ):
            return verdict
        reservation_id = hashlib.sha256(
            (
                f"{envelope.envelope_id}|{envelope.fencing_generation}|"
                f"{request.proposal_id}"
            ).encode("utf-8")
        ).hexdigest()
        notional_cents, fee_reserve_cents, risk_cents = (
            self._fee_inclusive_order_risk(request)
        )
        payload = {
            "schema": CAPITAL_RESERVATION_SCHEMA,
            "reservation_id": reservation_id,
            "proposal_id": str(request.proposal_id),
            "envelope_id": envelope.envelope_id,
            "fencing_generation": envelope.fencing_generation,
            "market_ticker": str(request.market_ticker),
            "contract_ticker": str(request.contract_ticker),
            "correlation_key": self._correlation_key(str(request.market_ticker)),
            "side": str(request.side),
            "size": int(request.size),
            "price_cents": int(request.price_cents),
            "notional_cents": notional_cents,
            "fee_reserve_cents": fee_reserve_cents,
            "risk_cents": risk_cents,
            "venue": envelope.venue,
            "account_hash": envelope.account_hash,
            "subaccount_number": self.expected_subaccount_number,
            "strategy_hash": str(request.capital_strategy_hash),
            "passport_hash": str(request.capital_passport_hash),
            "promotion_hash": str(request.capital_promotion_hash),
            "expiration_ts": (
                int(request.expiration_ts)
                if getattr(request, "expiration_ts", None) is not None
                else None
            ),
            "liquidity_role": str(
                getattr(request, "liquidity_role", "maker") or "maker"
            ),
            "order_terms_sha256": sha256_json(
                self._request_order_terms(request)
            ),
        }
        daily_loss = _require_int(
            current_daily_loss_cents,
            field="current_daily_loss_cents",
            minimum=0,
        )
        local_total = _require_int(
            current_local_total_exposure_cents,
            field="current_local_total_exposure_cents",
            minimum=0,
        )
        local_correlated = _require_int(
            current_local_correlated_exposure_cents,
            field="current_local_correlated_exposure_cents",
            minimum=0,
        )
        local_open_orders = _require_int(
            current_local_open_orders,
            field="current_local_open_orders",
            minimum=0,
        )

        def validate_existing(rows: tuple[dict[str, Any], ...]) -> None:
            if any(
                row.get("kind") == "authority.cancel_only"
                for row in rows
            ):
                raise ValueError(
                    "DumbMoney adapter is in cancel-only degraded mode"
                )
            accepted = [
                row
                for row in rows
                if row.get("kind") == "capital.envelope.accepted"
            ]
            highest_fence = max(
                (
                    int(row["payload"]["fencing_generation"])
                    for row in accepted
                ),
                default=0,
            )
            if not any(
                row["payload"].get("envelope_id")
                == envelope.envelope_id
                and int(row["payload"]["fencing_generation"])
                == envelope.fencing_generation
                for row in accepted
            ):
                raise ValueError("capital envelope is no longer accepted")
            if highest_fence != envelope.fencing_generation:
                raise ValueError("capital envelope fencing generation is stale")
            now = self._now_fn()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("reservation clock must be timezone-aware")
            now = now.astimezone(timezone.utc)
            if now >= envelope.expires_at:
                raise ValueError("capital envelope expired before reservation")

            bootstrap_rows = [
                row
                for row in rows
                if row.get("kind") == "broker.bootstrap.recorded"
            ]
            if not bootstrap_rows:
                raise ValueError("broker bootstrap receipt disappeared")
            latest_bootstrap = bootstrap_rows[-1]["payload"]
            observed = _parse_utc(
                latest_bootstrap["observed_at"],
                field="observed_at",
            )
            if now - observed > self.max_bootstrap_age:
                raise ValueError("broker bootstrap receipt is stale")

            created = {
                str(row["payload"]["reservation_id"]): row["payload"]
                for row in rows
                if row.get("kind") == "capital.reservation.created"
            }
            released = {
                str(row["payload"]["reservation_id"])
                for row in rows
                if row.get("kind") == "capital.reservation.released"
            }
            if any(
                item.get("proposal_id") == payload["proposal_id"]
                for item in created.values()
            ):
                raise ValueError(
                    "proposal id already has a capital reservation"
                )
            active = [
                item
                for key, item in created.items()
                if key not in released
            ]
            position_created = {
                str(row["payload"]["position_exposure_id"]): row[
                    "payload"
                ]
                for row in rows
                if row.get("kind")
                == "capital.position.exposure.recorded"
            }
            position_released = {
                str(row["payload"]["position_exposure_id"])
                for row in rows
                if row.get("kind")
                == "capital.position.exposure.released"
            }
            active_positions = [
                item
                for key, item in position_created.items()
                if key not in position_released
            ]
            risk_value = payload["risk_cents"]
            if isinstance(risk_value, bool) or not isinstance(risk_value, int):
                raise ValueError("capital reservation risk is invalid")
            order_risk = risk_value
            inherited_total = int(
                latest_bootstrap["total_exposure_cents"]
            )
            inherited_orders = int(latest_bootstrap["open_order_count"])
            inherited_correlated = int(
                latest_bootstrap["correlated_exposure_cents"].get(
                    payload["correlation_key"],
                    0,
                )
            )
            reserved_total = sum(
                int(item["risk_cents"]) for item in active
            )
            position_total = sum(
                int(item["risk_cents"]) for item in active_positions
            )
            reserved_correlated = sum(
                int(item["risk_cents"])
                for item in active
                if item.get("correlation_key")
                == payload["correlation_key"]
            )
            position_correlated = sum(
                int(item["risk_cents"])
                for item in active_positions
                if item.get("correlation_key")
                == payload["correlation_key"]
            )
            effective_open_risk = (
                inherited_total
                + reserved_total
                + position_total
                + local_total
            )
            effective_correlated_risk = (
                inherited_correlated
                + reserved_correlated
                + position_correlated
                + local_correlated
            )
            effective_open_orders = (
                inherited_orders + len(active) + local_open_orders
            )
            if order_risk > envelope.max_order_risk_cents:
                raise ValueError("DumbMoney maximum order risk exceeded")
            if (
                effective_open_risk + order_risk
                > envelope.max_open_risk_cents
            ):
                raise ValueError("DumbMoney maximum open risk exceeded")
            if (
                effective_correlated_risk + order_risk
                > envelope.max_correlated_risk_cents
            ):
                raise ValueError(
                    "DumbMoney maximum correlated risk exceeded"
                )
            if (
                order_risk
                > envelope.max_daily_loss_cents - daily_loss
            ):
                raise ValueError("DumbMoney daily loss capacity exceeded")
            if effective_open_orders >= envelope.max_open_orders:
                raise ValueError("DumbMoney maximum open orders reached")

        try:
            self.journal.append(
                "capital.reservation.created",
                payload,
                outbox_id=f"capital-reservation:{reservation_id}",
                validate_existing=validate_existing,
            )
        except ValueError as exc:
            return CapitalVerdict(
                False,
                str(exc),
                "capital_atomic_reservation",
                effective_limits=verdict.effective_limits,
            )
        return CapitalVerdict(
            True,
            "DumbMoney capital reserved durably",
            reservation_id=reservation_id,
            effective_limits=verdict.effective_limits,
        )

    def _reservation_for_proposal(
        self,
        proposal_id: str,
    ) -> dict[str, Any] | None:
        normalized = str(proposal_id).strip()
        return next(
            (
                dict(row["payload"])
                for row in self._events("capital.reservation.created")
                if row["payload"].get("proposal_id") == normalized
            ),
            None,
        )

    def claim_broker_dispatch(
        self,
        request: Any,
        *,
        reservation_id: str,
        order: Mapping[str, Any],
        claimant_nonce: str,
    ) -> dict[str, Any]:
        """Acquire the one-shot cross-process broker-dispatch right.

        The deterministic outbox id is intentionally non-idempotent for this
        operation: a prior identical claim is still a consumed authority, not
        permission to retry a possibly successful broker request.
        """
        nonce = _require_sha256(
            claimant_nonce,
            field="dispatch claimant_nonce",
        )
        reservation = self._reservation_for_proposal(
            str(request.proposal_id)
        )
        if (
            reservation is None
            or reservation.get("reservation_id") != reservation_id
        ):
            raise ValueError(
                "dispatch claim lacks the exact capital reservation"
            )
        order_value = json.loads(canonical_json(dict(order)))
        expected_order = self._expected_broker_order(request)
        if canonical_json(order_value) != canonical_json(expected_order):
            raise ValueError(
                "dispatch order differs from the exact authorized wire payload"
            )
        order_digest = sha256_json(order_value)
        request_terms = self._request_order_terms(request)
        request_terms_digest = sha256_json(request_terms)
        if reservation.get("order_terms_sha256") != request_terms_digest:
            raise ValueError(
                "dispatch request differs from reserved order terms"
            )
        payload = {
            "schema": CAPITAL_DISPATCH_CLAIM_SCHEMA,
            "reservation_id": reservation_id,
            "proposal_id": str(request.proposal_id),
            "client_order_id": str(order_value.get("client_order_id") or ""),
            "venue": self.expected_venue,
            "account_hash": self.expected_account_hash,
            "subaccount_number": self.expected_subaccount_number,
            "envelope_id": reservation["envelope_id"],
            "fencing_generation": reservation["fencing_generation"],
            "strategy_hash": reservation["strategy_hash"],
            "passport_hash": reservation["passport_hash"],
            "promotion_hash": reservation["promotion_hash"],
            "authorized_instrument": (
                f"event_contract:{request.contract_ticker}"
            ),
            "request_terms_sha256": request_terms_digest,
            "order_sha256": order_digest,
            "order": order_value,
            "claimant_nonce": nonce,
        }
        if payload["client_order_id"] != str(request.proposal_id):
            raise ValueError(
                "dispatch order client_order_id differs from proposal"
            )

        def validate_existing(rows: tuple[dict[str, Any], ...]) -> None:
            if any(
                row.get("kind") == "authority.cancel_only"
                for row in rows
            ):
                raise ValueError(
                    "DumbMoney adapter is in cancel-only degraded mode"
                )
            created = {
                str(row["payload"]["reservation_id"]): row["payload"]
                for row in rows
                if row.get("kind") == "capital.reservation.created"
            }
            released = {
                str(row["payload"]["reservation_id"])
                for row in rows
                if row.get("kind") == "capital.reservation.released"
            }
            if reservation_id not in created or reservation_id in released:
                raise ValueError(
                    "dispatch capital reservation is not active"
                )
            if created[reservation_id] != reservation:
                raise ValueError(
                    "dispatch capital reservation changed"
                )
            if any(
                row.get("kind") == "capital.dispatch.claimed"
                and (
                    row["payload"].get("reservation_id") == reservation_id
                    or row["payload"].get("proposal_id")
                    == str(request.proposal_id)
                )
                for row in rows
            ):
                raise ValueError(
                    "broker dispatch was already claimed"
                )
            if any(
                row.get("kind")
                == "capital.terminal_reconciliation.witnessed"
                and row["payload"].get("proposal_id")
                == str(request.proposal_id)
                for row in rows
            ):
                raise ValueError(
                    "terminal proposal cannot acquire dispatch"
                )
            accepted = [
                row
                for row in rows
                if row.get("kind") == "capital.envelope.accepted"
            ]
            accepted_row = next(
                (
                    row
                    for row in reversed(accepted)
                    if row["payload"].get("envelope_id")
                    == reservation["envelope_id"]
                    and int(row["payload"]["fencing_generation"])
                    == int(reservation["fencing_generation"])
                ),
                None,
            )
            if accepted_row is None:
                raise ValueError(
                    "dispatch capital envelope is no longer accepted"
                )
            highest_fence = max(
                (
                    int(row["payload"]["fencing_generation"])
                    for row in accepted
                ),
                default=0,
            )
            if highest_fence != int(reservation["fencing_generation"]):
                raise ValueError(
                    "dispatch capital fence is stale"
                )
            now = self._now_fn()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("dispatch clock must be timezone-aware")
            now = now.astimezone(timezone.utc)
            verified = verify_signed_capital_envelope(
                accepted_row["payload"]["wrapper"],
                trusted_public_keys=self.trusted_public_keys,
                expected_venue=self.expected_venue,
                expected_account_hash=self.expected_account_hash,
                now=now,
                max_ttl=self.max_envelope_ttl,
            )
            if (
                verified.envelope_id != reservation["envelope_id"]
                or verified.fencing_generation
                != int(reservation["fencing_generation"])
                or verified.authorized_mode != "LIVE"
                or reservation["strategy_hash"]
                not in verified.strategy_hashes
                or reservation["passport_hash"]
                not in verified.passport_hashes
                or reservation["promotion_hash"]
                not in verified.promotion_hashes
                or payload["authorized_instrument"]
                not in verified.authorized_instruments
            ):
                raise ValueError(
                    "dispatch capital envelope binding is not active"
                )
            bootstrap_rows = [
                row
                for row in rows
                if row.get("kind") == "broker.bootstrap.recorded"
            ]
            if not bootstrap_rows:
                raise ValueError(
                    "dispatch requires a broker bootstrap receipt"
                )
            observed = _parse_utc(
                bootstrap_rows[-1]["payload"]["observed_at"],
                field="observed_at",
            )
            if now - observed > self.max_bootstrap_age:
                raise ValueError(
                    "broker bootstrap receipt expired before dispatch"
                )

        event = self.journal.append(
            "capital.dispatch.claimed",
            payload,
            outbox_id=f"capital-dispatch:{reservation_id}",
            allow_existing_outbox=False,
            validate_existing=validate_existing,
        )
        return dict(event)

    def pending_reconciliation_reservations(
        self,
    ) -> tuple[dict[str, Any], ...]:
        """Expose conservative active reservations to the read-only sweeper."""
        claims = {
            str(row["payload"]["reservation_id"])
            for row in self._events("capital.dispatch.claimed")
        }
        return tuple(
            {
                **item,
                "dispatch_claimed": (
                    str(item["reservation_id"]) in claims
                ),
            }
            for item in self._active_reservations()
        )

    def active_position_exposures(
        self,
    ) -> tuple[dict[str, Any], ...]:
        """Expose unsettled, independently charged capital positions."""
        return tuple(self._active_position_exposures())

    def _verify_broker_witness(
        self,
        wrapper: Mapping[str, Any],
        *,
        expected_schema: str,
    ) -> VerifiedSignedEnvelope:
        if not self.trusted_broker_witness_public_keys:
            raise ValueError(
                "trusted broker witness identity is unavailable"
            )
        signed = verify_signed_envelope(
            wrapper,
            trusted_public_keys=(
                self.trusted_broker_witness_public_keys
            ),
            expected_body_schema=expected_schema,
            max_ttl=WITNESS_TTL,
            require_active=False,
        )
        if signed.source_id != BROKER_WITNESS_SOURCE_ID:
            raise ValueError("broker witness source identity mismatch")
        body = signed.body
        if (
            body.get("venue") != self.expected_venue
            or body.get("account_hash") != self.expected_account_hash
            or body.get("subaccount_number")
            != self.expected_subaccount_number
        ):
            raise ValueError("broker witness account identity mismatch")
        observed = _parse_utc(
            body.get("observed_at"),
            field="broker witness observed_at",
        )
        if observed != signed.not_before:
            raise ValueError(
                "broker witness observation and signature window differ"
            )
        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("broker witness clock must be timezone-aware")
        if observed > now.astimezone(timezone.utc) + timedelta(seconds=5):
            raise ValueError("broker witness is from the future")
        return signed

    def verify_terminal_reconciliation_witness(
        self,
        wrapper: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Verify a service-signed terminal order/fill projection."""
        signed = self._verify_broker_witness(
            wrapper,
            expected_schema=TERMINAL_WITNESS_SCHEMA,
        )
        body = signed.body
        required = {
            "schema",
            "witness_id",
            "venue",
            "account_hash",
            "subaccount_number",
            "reservation_id",
            "proposal_id",
            "order_id",
            "market_ticker",
            "contract_ticker",
            "side",
            "terminal_status",
            "initial_count",
            "fill_count",
            "remaining_count",
            "fill_cost_cents",
            "fee_cents",
            "average_fill_price_cents",
            "fill_ids",
            "observed_at",
            "broker_projection_sha256",
        }
        if set(body) != required:
            raise ValueError("terminal broker witness fields mismatch")
        witness_id = _require_sha256(
            body["witness_id"],
            field="terminal witness_id",
        )
        reservation_id = _require_sha256(
            body["reservation_id"],
            field="terminal reservation_id",
        )
        proposal_id = _require_identifier(
            body["proposal_id"],
            field="terminal proposal_id",
        )
        order_id = _require_identifier(
            body["order_id"],
            field="terminal order_id",
        )
        market_ticker = _require_identifier(
            body["market_ticker"],
            field="terminal market_ticker",
        )
        contract_ticker = _require_identifier(
            body["contract_ticker"],
            field="terminal contract_ticker",
        )
        side = body["side"]
        if side not in {"yes", "no"}:
            raise ValueError("terminal witness side is invalid")
        status = body["terminal_status"]
        if status not in {"canceled", "executed"}:
            raise ValueError("terminal witness status is invalid")
        initial_count = _require_int(
            body["initial_count"],
            field="terminal initial_count",
            minimum=1,
        )
        fill_count = _require_int(
            body["fill_count"],
            field="terminal fill_count",
            minimum=0,
        )
        remaining_count = _require_int(
            body["remaining_count"],
            field="terminal remaining_count",
            minimum=0,
        )
        fill_cost = _require_int(
            body["fill_cost_cents"],
            field="terminal fill_cost_cents",
            minimum=0,
        )
        fee = _require_int(
            body["fee_cents"],
            field="terminal fee_cents",
            minimum=0,
        )
        average = body["average_fill_price_cents"]
        fill_ids = body["fill_ids"]
        if (
            not isinstance(fill_ids, list)
            or fill_ids != sorted(set(fill_ids))
            or any(
                not isinstance(item, str) or not item
                for item in fill_ids
            )
        ):
            raise ValueError("terminal fill_ids are invalid")
        if (
            fill_count > initial_count
            or remaining_count != 0
            or (
                status == "executed"
                and fill_count != initial_count
            )
            or (
                fill_count == 0
                and (
                    fill_cost != 0
                    or fee != 0
                    or average is not None
                    or fill_ids
                )
            )
            or (
                fill_count > 0
                and (
                    isinstance(average, bool)
                    or not isinstance(average, int)
                    or not 1 <= average <= 99
                    or not fill_ids
                    or fill_cost < fill_count
                    or fill_cost > fill_count * 100
                )
            )
        ):
            raise ValueError("terminal fill projection is inconsistent")
        _require_sha256(
            body["broker_projection_sha256"],
            field="terminal broker_projection_sha256",
        )
        reservation = self._reservation_for_proposal(proposal_id)
        if (
            reservation is None
            or reservation.get("reservation_id") != reservation_id
            or reservation.get("market_ticker") != market_ticker
            or reservation.get("contract_ticker") != contract_ticker
            or reservation.get("side") != side
            or int(reservation.get("size", -1)) != initial_count
        ):
            raise ValueError(
                "terminal witness differs from the capital reservation"
            )
        claims = [
            row
            for row in self._events("capital.dispatch.claimed")
            if row["payload"].get("reservation_id") == reservation_id
        ]
        if len(claims) != 1:
            raise ValueError(
                "terminal witness lacks one exact dispatch claim"
            )
        if (
            claims[0]["payload"].get("proposal_id") != proposal_id
            or claims[0]["payload"].get("client_order_id")
            != proposal_id
        ):
            raise ValueError("terminal dispatch identity mismatch")
        observed = _parse_utc(
            body["observed_at"],
            field="terminal observed_at",
        )
        dispatched = _parse_utc(
            claims[0]["recorded_at"],
            field="dispatch recorded_at",
        )
        if observed < dispatched:
            raise ValueError(
                "terminal witness predates broker dispatch"
            )
        if fill_cost + fee > int(reservation["risk_cents"]):
            raise ValueError(
                "terminal filled risk exceeds the fee-inclusive reservation"
            )
        return {
            **json.loads(canonical_json(body)),
            "signed_event_id": signed.event_id,
            "signed_wrapper": signed.wrapper,
            "witness_id": witness_id,
            "order_id": order_id,
        }

    def record_signed_terminal_reconciliation(
        self,
        wrapper: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist terminal evidence, then move reservation risk to position."""
        witness = self.verify_terminal_reconciliation_witness(wrapper)
        reservation_id = str(witness["reservation_id"])
        proposal_id = str(witness["proposal_id"])
        witness_id = str(witness["witness_id"])

        def validate_terminal(rows: tuple[dict[str, Any], ...]) -> None:
            matching = [
                row["payload"]
                for row in rows
                if row.get("kind")
                == "capital.terminal_reconciliation.witnessed"
                and row["payload"].get("proposal_id")
                == proposal_id
            ]
            if matching and matching[-1].get("witness_id") != witness_id:
                raise ValueError(
                    "proposal already has a conflicting terminal witness"
                )
            if not any(
                row.get("kind") == "capital.dispatch.claimed"
                and row["payload"].get("reservation_id")
                == reservation_id
                for row in rows
            ):
                raise ValueError(
                    "terminal witness dispatch claim disappeared"
                )

        self.journal.append(
            "capital.terminal_reconciliation.witnessed",
            {
                "witness_id": witness_id,
                "proposal_id": proposal_id,
                "reservation_id": reservation_id,
                "order_id": witness["order_id"],
                "terminal_status": witness["terminal_status"],
                "fill_count": witness["fill_count"],
                "fill_cost_cents": witness["fill_cost_cents"],
                "fee_cents": witness["fee_cents"],
                "observed_at": witness["observed_at"],
                "signed_event_id": witness["signed_event_id"],
                "signed_wrapper": witness["signed_wrapper"],
            },
            outbox_id=f"capital-terminal-witness:{witness_id}",
            validate_existing=validate_terminal,
        )
        position: dict[str, Any] | None = None
        if int(witness["fill_count"]) > 0:
            reservation = self._reservation_for_proposal(proposal_id)
            assert reservation is not None
            position_id = sha256_json(
                {
                    "schema": CAPITAL_POSITION_EXPOSURE_SCHEMA,
                    "reservation_id": reservation_id,
                    "order_id": witness["order_id"],
                    "terminal_witness_id": witness_id,
                }
            )
            position = {
                "schema": CAPITAL_POSITION_EXPOSURE_SCHEMA,
                "position_exposure_id": position_id,
                "reservation_id": reservation_id,
                "proposal_id": proposal_id,
                "order_id": witness["order_id"],
                "venue": self.expected_venue,
                "account_hash": self.expected_account_hash,
                "subaccount_number": self.expected_subaccount_number,
                "market_ticker": reservation["market_ticker"],
                "contract_ticker": reservation["contract_ticker"],
                "correlation_key": reservation["correlation_key"],
                "side": reservation["side"],
                "fill_count": witness["fill_count"],
                "fill_cost_cents": witness["fill_cost_cents"],
                "fee_cents": witness["fee_cents"],
                "risk_cents": (
                    int(witness["fill_cost_cents"])
                    + int(witness["fee_cents"])
                ),
                "average_fill_price_cents": witness[
                    "average_fill_price_cents"
                ],
                "terminal_witness_id": witness_id,
                "observed_at": witness["observed_at"],
            }
            self.journal.append(
                "capital.position.exposure.recorded",
                position,
                outbox_id=f"capital-position:{position_id}",
            )

        terminal_reservation = self._reservation_for_proposal(proposal_id)
        if terminal_reservation is None:
            raise ValueError(
                "terminal capital reservation disappeared"
            )
        release = {
            "schema": CAPITAL_TERMINAL_RELEASE_SCHEMA,
            "reservation_id": reservation_id,
            "proposal_id": proposal_id,
            "terminal_witness_id": witness_id,
            "terminal_status": witness["terminal_status"],
            "released_risk_cents": int(
                terminal_reservation["risk_cents"]
            ),
            "position_exposure_id": (
                position["position_exposure_id"]
                if position is not None
                else None
            ),
        }

        def validate_release(rows: tuple[dict[str, Any], ...]) -> None:
            if not any(
                row.get("kind")
                == "capital.terminal_reconciliation.witnessed"
                and row["payload"].get("witness_id") == witness_id
                for row in rows
            ):
                raise ValueError("terminal witness is not durable")
            if position is not None and not any(
                row.get("kind")
                == "capital.position.exposure.recorded"
                and row["payload"].get("position_exposure_id")
                == position["position_exposure_id"]
                for row in rows
            ):
                raise ValueError(
                    "filled position exposure is not durable"
                )

        self.journal.append(
            "capital.reservation.released",
            release,
            outbox_id=f"capital-terminal-release:{reservation_id}",
            validate_existing=validate_release,
        )
        return {
            "status": "TERMINAL_RECONCILED",
            "witness_id": witness_id,
            "reservation_id": reservation_id,
            "position_exposure_id": (
                position["position_exposure_id"]
                if position is not None
                else None
            ),
        }

    def verify_settlement_reconciliation_witness(
        self,
        wrapper: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Verify stable position absence plus a service-signed settlement."""
        signed = self._verify_broker_witness(
            wrapper,
            expected_schema=SETTLEMENT_WITNESS_SCHEMA,
        )
        body = signed.body
        required = {
            "schema",
            "witness_id",
            "venue",
            "account_hash",
            "subaccount_number",
            "position_exposure_id",
            "reservation_id",
            "proposal_id",
            "contract_ticker",
            "side",
            "fill_count",
            "market_result",
            "settled_at",
            "revenue_cents",
            "settlement_fee_cents",
            "position_absent",
            "observed_at",
            "broker_projection_sha256",
        }
        if set(body) != required:
            raise ValueError("settlement broker witness fields mismatch")
        witness_id = _require_sha256(
            body["witness_id"],
            field="settlement witness_id",
        )
        position_id = _require_sha256(
            body["position_exposure_id"],
            field="position_exposure_id",
        )
        _require_sha256(
            body["reservation_id"],
            field="settlement reservation_id",
        )
        _require_identifier(
            body["proposal_id"],
            field="settlement proposal_id",
        )
        _require_identifier(
            body["contract_ticker"],
            field="settlement contract_ticker",
        )
        if body["side"] not in {"yes", "no"}:
            raise ValueError("settlement side is invalid")
        fill_count = _require_int(
            body["fill_count"],
            field="settlement fill_count",
            minimum=1,
        )
        if body["market_result"] not in {"yes", "no"}:
            raise ValueError("settlement result is invalid")
        settled = _parse_utc(
            body["settled_at"],
            field="settled_at",
        )
        observed = _parse_utc(
            body["observed_at"],
            field="settlement observed_at",
        )
        if settled > observed:
            raise ValueError(
                "settlement observation predates settlement"
            )
        _require_int(
            body["revenue_cents"],
            field="settlement revenue_cents",
            minimum=0,
        )
        _require_int(
            body["settlement_fee_cents"],
            field="settlement fee_cents",
            minimum=0,
        )
        if body["position_absent"] is not True:
            raise ValueError(
                "settlement witness lacks stable position absence"
            )
        _require_sha256(
            body["broker_projection_sha256"],
            field="settlement broker_projection_sha256",
        )
        positions = [
            row["payload"]
            for row in self._events(
                "capital.position.exposure.recorded"
            )
            if row["payload"].get("position_exposure_id")
            == position_id
        ]
        if len(positions) != 1:
            raise ValueError(
                "settlement witness lacks one exact capital position"
            )
        position = positions[0]
        position_observed = _parse_utc(
            position.get("observed_at"),
            field="capital position observed_at",
        )
        if (
            position.get("reservation_id") != body["reservation_id"]
            or position.get("proposal_id") != body["proposal_id"]
            or position.get("contract_ticker")
            != body["contract_ticker"]
            or position.get("side") != body["side"]
            or int(position.get("fill_count", -1)) != fill_count
        ):
            raise ValueError(
                "settlement witness differs from capital position"
            )
        if settled < position_observed:
            raise ValueError(
                "settlement predates the capital position exposure"
            )
        return {
            **json.loads(canonical_json(body)),
            "signed_event_id": signed.event_id,
            "signed_wrapper": signed.wrapper,
            "witness_id": witness_id,
        }

    def record_signed_settlement_reconciliation(
        self,
        wrapper: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist settlement evidence before releasing position exposure."""
        witness = self.verify_settlement_reconciliation_witness(wrapper)
        witness_id = str(witness["witness_id"])
        position_id = str(witness["position_exposure_id"])
        self.journal.append(
            "capital.settlement_reconciliation.witnessed",
            {
                "witness_id": witness_id,
                "position_exposure_id": position_id,
                "proposal_id": witness["proposal_id"],
                "market_result": witness["market_result"],
                "settled_at": witness["settled_at"],
                "position_absent": True,
                "signed_event_id": witness["signed_event_id"],
                "signed_wrapper": witness["signed_wrapper"],
            },
            outbox_id=f"capital-settlement-witness:{witness_id}",
        )
        position = next(
            item
            for item in self._events(
                "capital.position.exposure.recorded"
            )
            if item["payload"].get("position_exposure_id")
            == position_id
        )["payload"]
        release = {
            "schema": CAPITAL_POSITION_RELEASE_SCHEMA,
            "position_exposure_id": position_id,
            "reservation_id": position["reservation_id"],
            "proposal_id": position["proposal_id"],
            "settlement_witness_id": witness_id,
            "released_risk_cents": position["risk_cents"],
            "market_result": witness["market_result"],
            "settled_at": witness["settled_at"],
        }

        def validate_release(rows: tuple[dict[str, Any], ...]) -> None:
            if not any(
                row.get("kind")
                == "capital.settlement_reconciliation.witnessed"
                and row["payload"].get("witness_id") == witness_id
                for row in rows
            ):
                raise ValueError("settlement witness is not durable")

        self.journal.append(
            "capital.position.exposure.released",
            release,
            outbox_id=f"capital-position-release:{position_id}",
            validate_existing=validate_release,
        )
        return {
            "status": "POSITION_SETTLED",
            "witness_id": witness_id,
            "position_exposure_id": position_id,
        }

    def release_after_local_reservation_failure(
        self,
        request: Any,
        *,
        reservation_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Retain capital until a sealed broker/local CAS witness exists.

        A caller assertion that transport did not occur is not proof across
        process crashes. This recovery surface is intentionally disabled; the
        central firewall already retains the reservation on local failure.
        """
        del request, reservation_id, reason
        raise ValueError(
            "local-failure capital release is disabled pending sealed CAS proof"
        )

    def release_from_terminal_reconciliation(
        self,
        *,
        proposal_id: str,
        terminal_status: str,
        reconciliation_receipt: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Reject caller-authored terminal facts until broker truth is sealed."""
        del proposal_id, terminal_status, reconciliation_receipt
        raise ValueError(
            "terminal capital release requires a sealed broker witness"
        )

    def enter_cancel_only(
        self,
        *,
        reason: str,
        kill_asserted_at: str,
        cancel_authorized: bool = False,
        cancel_authority_receipt: str | None = None,
    ) -> dict[str, Any]:
        """Disable submissions without inventing cancellation authority."""
        _parse_utc(kill_asserted_at, field="kill_asserted_at")
        authority_receipt = (
            str(cancel_authority_receipt).strip()
            if cancel_authority_receipt is not None
            else ""
        )
        payload = {
            "reason": _require_text(reason, field="reason"),
            "kill_asserted_at": kill_asserted_at,
            "submission_authority": False,
            "cancel_authority": False,
            "cancel_authority_receipt": None,
            "broker_contacted": False,
            "status": "CANCEL_AUTHORITY_REQUIRED",
        }
        event = self.journal.append("authority.cancel_only", payload)
        if cancel_authorized or authority_receipt:
            raise ValueError(
                "cancellation authority requires a verified broker "
                "capability; opaque receipt strings are not authority"
            )
        return dict(event)


__all__ = [
    "CAPITAL_ENVELOPE_SCHEMA",
    "CAPITAL_DISPATCH_CLAIM_SCHEMA",
    "CAPITAL_RESERVATION_SCHEMA",
    "CAPITAL_POSITION_EXPOSURE_SCHEMA",
    "CAPITAL_TERMINAL_RELEASE_SCHEMA",
    "CAPITAL_POSITION_RELEASE_SCHEMA",
    "CapitalEnvelopeAdapter",
    "CapitalLineageResolver",
    "CapitalVerdict",
    "FLAT_BOOTSTRAP_SCHEMA",
    "INHERITED_BOOTSTRAP_SCHEMA",
    "SIGNED_ENVELOPE_SCHEMA",
    "VerifiedCapitalEnvelope",
    "VerifiedSignedEnvelope",
    "flat_book_receipt",
    "inherited_exposure_receipt",
    "strategy_binding_hash",
    "verify_signed_capital_envelope",
    "verify_signed_envelope",
]
