"""Local-only DumbMoney Core command-feed consumer.

The consumer has no scheduler, background thread, HTTP client, or broker
interface. A supervised local runner injects one loopback GET transport and
calls :meth:`CoreCommandFeedConsumer.poll_once` explicitly. Every cursor and
its resulting control state are persisted together in the hash-chained,
fsynced operational journal.

Positive authority is never dispatched through callbacks. Signed LIVE and
kill-clear state becomes visible only through the durable snapshot; injected
handlers are invoked solely for authority-reducing kill/paused controls.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from live_firewall.dumbmoney_capital import (
    CAPITAL_ENVELOPE_SCHEMA,
    CapitalEnvelopeAdapter,
    VerifiedCapitalEnvelope,
    VerifiedSignedEnvelope,
    verify_signed_capital_envelope,
    verify_signed_envelope,
)
from live_firewall.operational_journal import (
    AppendOnlyOperationalJournal,
    canonical_json,
    sha256_json,
)


CELL_ID = "dummy_kalshi"
PAGE_SCHEMA = "dumbmoney.cell-command-page.v1"
CHECKPOINT_SCHEMA = "dumbmoney.cell-command-checkpoint.v1"
STATE_SCHEMA = "dummy.dumbmoney-command-feed-state.v1"
STATE_EVENT_KIND = "dumbmoney.command-feed.state"
KILL_STATE_SCHEMA = "dumbmoney.kill-state.v1"
DESIRED_MODE_SCHEMA = "dumbmoney.desired-mode.v1"
ZERO_DIGEST = "0" * 64

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_PAGE_FIELDS = {
    "schema",
    "cell_id",
    "request_nonce",
    "observed_at",
    "after_sequence",
    "after_digest",
    "next_sequence",
    "next_digest",
    "ledger_head_sequence",
    "ledger_head_digest",
    "has_more",
    "required_action",
    "commands",
    "checkpoint",
    "checkpoint_signature",
}
_COMMAND_FIELDS = {
    "global_sequence",
    "event_id",
    "event_digest",
    "body_schema",
    "valid_now",
    "transport_window_current",
    "authority_effect",
    "ledger_proof",
    "envelope",
}
_CHECKPOINT_FIELDS = {
    "schema",
    "cell_id",
    "request_nonce",
    "after_sequence",
    "after_digest",
    "ordered_commands",
    "next_sequence",
    "next_digest",
    "ledger_head_sequence",
    "ledger_head_digest",
    "observed_at",
    "required_action",
}
_CHECKPOINT_COMMAND_FIELDS = _COMMAND_FIELDS - {"envelope"}
_CHECKPOINT_SIGNATURE_FIELDS = {"algorithm", "signer_key_id", "signature"}
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
_LEDGER_PROOF_SCHEMA = "dumbmoney.ledger-event-proof.v1"
_STATE_FIELDS = {
    "schema",
    "cell_id",
    "cursor",
    "status",
    "reason",
    "policy_epoch",
    "kill_generation_high_water",
    "mode_revision_high_water",
    "capital_fencing_high_water",
    "kill_envelope",
    "desired_mode_envelope",
    "required_action",
    "updated_at",
}
_ACTIONS = {
    "APPLY_SIGNED_CONTROLS",
    "PAUSE_NEW_RISK",
    "CANCEL_AND_RECONCILE",
}
_MODES = {"READ_ONLY", "PAPER", "LIVE", "PAUSED"}
_AUTHORITY_EFFECTS = {
    "APPLY_FAIL_CLOSED",
    "APPLY_POSITIVE",
    "HISTORICAL_ONLY",
}
_CORE_COMMAND_FUTURE_SKEW = timedelta(seconds=5)
_SUPPORTED_BODY_SCHEMAS = {
    KILL_STATE_SCHEMA,
    DESIRED_MODE_SCHEMA,
    CAPITAL_ENVELOPE_SCHEMA,
}


class CommandFeedError(RuntimeError):
    """A feed, cursor, signature, or dispatch failure that removes authority."""


@dataclass(frozen=True)
class CommandFeedResponse:
    """One injected loopback GET response."""

    status_code: int
    body: bytes


class CommandFeedTransport(Protocol):
    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
    ) -> CommandFeedResponse: ...


@dataclass(frozen=True)
class VerifiedFeedCommand:
    global_sequence: int
    event_digest: str
    envelope: VerifiedSignedEnvelope
    ledger_proof: dict[str, Any]
    capital: VerifiedCapitalEnvelope | None = None
    authority_current: bool = False
    authority_current_at_core: bool = False
    narrows_authority: bool = False

    @property
    def body(self) -> dict[str, Any]:
        return deepcopy(self.envelope.body)


@dataclass(frozen=True)
class CommandFeedPollResult:
    page_accepted: bool
    cursor_sequence: int
    cursor_digest: str
    commands_applied: int
    required_action: str | None
    submission_allowed: bool
    reason: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC_RE.fullmatch(value):
        raise CommandFeedError(f"{field} must be canonical RFC3339 UTC")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(timezone.utc)


def _require_int(value: Any, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CommandFeedError(f"{field} must be an integer >= {minimum}")
    return value


def _require_digest(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise CommandFeedError(f"{field} must be a lowercase sha256")
    return value


def _require_identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise CommandFeedError(f"{field} must be a canonical identifier")
    return value


def _decode_base64url_signature(value: Any) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or "=" in value
        or re.search(r"[^A-Za-z0-9_-]", value)
    ):
        raise CommandFeedError(
            "checkpoint signature must be unpadded base64url"
        )
    try:
        decoded = base64.urlsafe_b64decode(
            value + "=" * (-len(value) % 4)
        )
    except Exception as exc:
        raise CommandFeedError("checkpoint signature is invalid base64url") from exc
    canonical = (
        base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    )
    if canonical != value or len(decoded) != 64:
        raise CommandFeedError("checkpoint signature encoding is invalid")
    return decoded


def _public_key_bytes(value: bytes | Ed25519PublicKey) -> bytes:
    if isinstance(value, Ed25519PublicKey):
        return bytes(value.public_bytes_raw())
    raw = bytes(value)
    if len(raw) != 32:
        raise CommandFeedError("checkpoint Ed25519 public key must be 32 bytes")
    return raw


def _strict_json(raw: bytes, *, maximum_bytes: int) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise CommandFeedError("command feed response body must be bytes")
    if len(raw) > maximum_bytes:
        raise CommandFeedError("command feed response exceeds maximum size")

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise CommandFeedError("command feed JSON contains duplicate keys")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise CommandFeedError(
            f"command feed JSON contains non-finite constant {value}"
        )

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except CommandFeedError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandFeedError("command feed response is not strict UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise CommandFeedError("command feed response must be an object")
    return parsed


def _validate_kill_body(
    body: Mapping[str, Any],
    *,
    now: datetime,
    require_current: bool,
    future_skew: timedelta,
) -> dict[str, Any]:
    required = {
        "schema",
        "active",
        "generation",
        "reason",
        "changed_by",
        "policy_epoch",
        "changed_at",
    }
    if set(body) != required or body.get("schema") != KILL_STATE_SCHEMA:
        raise CommandFeedError("kill-state body fields mismatch")
    if not isinstance(body["active"], bool):
        raise CommandFeedError("kill-state active must be boolean")
    _require_int(body["generation"], field="kill-state generation", minimum=1)
    if not isinstance(body["reason"], str) or not body["reason"].strip():
        raise CommandFeedError("kill-state reason must be nonempty")
    _require_identifier(body["changed_by"], field="kill-state changed_by")
    _require_int(body["policy_epoch"], field="kill-state policy_epoch", minimum=1)
    changed_at = _parse_utc(body["changed_at"], field="kill-state changed_at")
    if require_current and changed_at > now + future_skew:
        raise CommandFeedError("kill-state changed_at is from the future")
    return cast(
        dict[str, Any],
        json.loads(canonical_json(dict(body))),
    )


def _validate_mode_body(
    body: Mapping[str, Any],
    *,
    now: datetime,
    require_current: bool,
) -> dict[str, Any]:
    required = {
        "schema",
        "venue",
        "mode",
        "revision",
        "reason",
        "policy_epoch",
        "not_before",
        "expires_at",
    }
    if set(body) != required or body.get("schema") != DESIRED_MODE_SCHEMA:
        raise CommandFeedError("desired-mode body fields mismatch")
    if body["venue"] != CELL_ID:
        raise CommandFeedError("desired-mode venue mismatch")
    if body["mode"] not in _MODES:
        raise CommandFeedError("desired-mode value is unsupported")
    _require_int(body["revision"], field="desired-mode revision", minimum=1)
    if not isinstance(body["reason"], str) or not body["reason"].strip():
        raise CommandFeedError("desired-mode reason must be nonempty")
    _require_int(body["policy_epoch"], field="desired-mode policy_epoch", minimum=1)
    not_before = _parse_utc(
        body["not_before"],
        field="desired-mode not_before",
    )
    expires_at = _parse_utc(
        body["expires_at"],
        field="desired-mode expires_at",
    )
    if expires_at <= not_before:
        raise CommandFeedError("desired-mode authority window is invalid")
    if require_current:
        if now < not_before:
            raise CommandFeedError("desired-mode is not active yet")
        if now >= expires_at:
            raise CommandFeedError("desired-mode expired")
    return cast(
        dict[str, Any],
        json.loads(canonical_json(dict(body))),
    )


class CoreCommandFeedConsumer:
    """Consume one authenticated Core page without any automatic polling."""

    def __init__(
        self,
        *,
        transport: CommandFeedTransport,
        cell_token_provider: Callable[[], str],
        state_journal: AppendOnlyOperationalJournal,
        trusted_operator_public_keys: Mapping[
            str,
            bytes | Ed25519PublicKey,
        ],
        trusted_checkpoint_public_keys: Mapping[
            str,
            bytes | Ed25519PublicKey,
        ],
        capital_adapter: CapitalEnvelopeAdapter,
        kill_handler: Callable[[VerifiedFeedCommand], None],
        mode_handler: Callable[[VerifiedFeedCommand], None],
        fail_closed_handler: Callable[[str], None],
        now_fn: Callable[[], datetime] | None = None,
        request_nonce_fn: Callable[[], str] | None = None,
        page_limit: int = 250,
        maximum_response_bytes: int = 1_048_576,
        maximum_page_age: timedelta = timedelta(seconds=60),
        maximum_future_skew: timedelta = timedelta(seconds=5),
    ) -> None:
        if not callable(transport):
            raise TypeError("transport must be callable")
        if not callable(cell_token_provider):
            raise TypeError("cell_token_provider must be callable")
        if not callable(kill_handler) or not callable(mode_handler):
            raise TypeError("authority-reducing handlers must be callable")
        if not callable(fail_closed_handler):
            raise TypeError("fail_closed_handler must be callable")
        if request_nonce_fn is not None and not callable(request_nonce_fn):
            raise TypeError("request_nonce_fn must be callable")
        if isinstance(page_limit, bool) or not 1 <= page_limit <= 1000:
            raise ValueError("page_limit must be between 1 and 1000")
        if maximum_response_bytes < 1:
            raise ValueError("maximum_response_bytes must be positive")
        if maximum_page_age <= timedelta(0):
            raise ValueError("maximum_page_age must be positive")
        if maximum_future_skew < timedelta(0):
            raise ValueError("maximum_future_skew cannot be negative")
        if capital_adapter.expected_venue != CELL_ID:
            raise ValueError("capital adapter must be pinned to dummy_kalshi")
        if not trusted_checkpoint_public_keys:
            raise ValueError("at least one pinned Core checkpoint key is required")
        if not trusted_operator_public_keys:
            raise ValueError(
                "at least one pinned operator command key is required"
            )
        checkpoint_keys: dict[str, bytes] = {}
        for key_id, key_material in trusted_checkpoint_public_keys.items():
            normalized_key_id = _require_digest(
                key_id,
                field="checkpoint signer key id",
            )
            raw_key = _public_key_bytes(key_material)
            if hashlib.sha256(raw_key).hexdigest() != normalized_key_id:
                raise ValueError(
                    "checkpoint signer key id does not match public key"
                )
            checkpoint_keys[normalized_key_id] = raw_key
        operator_keys: dict[str, bytes] = {}
        for key_id, key_material in trusted_operator_public_keys.items():
            normalized_key_id = _require_digest(
                key_id,
                field="operator signer key id",
            )
            raw_key = _public_key_bytes(key_material)
            if hashlib.sha256(raw_key).hexdigest() != normalized_key_id:
                raise ValueError(
                    "operator signer key id does not match public key"
                )
            operator_keys[normalized_key_id] = raw_key
        if set(checkpoint_keys) & set(operator_keys):
            raise ValueError(
                "Core checkpoint and operator command keys must be disjoint"
            )
        if not set(checkpoint_keys) <= set(
            capital_adapter.trusted_public_keys
        ):
            raise ValueError(
                "capital adapter must trust every pinned Core checkpoint key"
            )

        self._transport = transport
        self._cell_token_provider = cell_token_provider
        self._journal = state_journal
        self._trusted_operator_public_keys = operator_keys
        self._trusted_checkpoint_public_keys = checkpoint_keys
        self._capital_adapter = capital_adapter
        self._kill_handler = kill_handler
        self._mode_handler = mode_handler
        self._fail_closed_handler = fail_closed_handler
        self._now_fn = now_fn or _utc_now
        self._request_nonce_fn = request_nonce_fn or (
            lambda: secrets.token_hex(32)
        )
        self._last_request_nonce: str | None = None
        self.page_limit = page_limit
        self.maximum_response_bytes = maximum_response_bytes
        self.maximum_page_age = maximum_page_age
        self.maximum_future_skew = maximum_future_skew

    def _now(self) -> datetime:
        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            raise CommandFeedError("command-feed clock must be timezone-aware")
        return now.astimezone(timezone.utc)

    def _bootstrap_state(self, now: datetime) -> dict[str, Any]:
        return {
            "schema": STATE_SCHEMA,
            "cell_id": CELL_ID,
            "cursor": {"sequence": 0, "digest": ZERO_DIGEST},
            "status": "FAIL_CLOSED",
            "reason": "explicit bootstrap cursor has not been polled",
            "policy_epoch": 0,
            "kill_generation_high_water": 0,
            "mode_revision_high_water": 0,
            "capital_fencing_high_water": 0,
            "kill_envelope": None,
            "desired_mode_envelope": None,
            "required_action": None,
            "updated_at": _format_utc(now),
        }

    def _validate_stored_state(
        self,
        raw: Mapping[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        state = json.loads(canonical_json(dict(raw)))
        if set(state) != _STATE_FIELDS:
            raise CommandFeedError("persisted command-feed state fields mismatch")
        if state["schema"] != STATE_SCHEMA or state["cell_id"] != CELL_ID:
            raise CommandFeedError("persisted command-feed state identity mismatch")
        cursor = state["cursor"]
        if not isinstance(cursor, dict) or set(cursor) != {"sequence", "digest"}:
            raise CommandFeedError("persisted command-feed cursor fields mismatch")
        _require_int(cursor["sequence"], field="cursor sequence")
        _require_digest(cursor["digest"], field="cursor digest")
        if cursor["sequence"] == 0 and cursor["digest"] != ZERO_DIGEST:
            raise CommandFeedError("bootstrap cursor digest mismatch")
        if cursor["sequence"] > 0 and cursor["digest"] == ZERO_DIGEST:
            raise CommandFeedError("non-bootstrap cursor cannot use zero digest")
        if state["status"] not in {"READY", "CATCHING_UP", "FAIL_CLOSED"}:
            raise CommandFeedError("persisted command-feed status is unsupported")
        if not isinstance(state["reason"], str) or not state["reason"].strip():
            raise CommandFeedError("persisted command-feed reason is missing")
        _require_int(state["policy_epoch"], field="persisted policy_epoch")
        _require_int(
            state["kill_generation_high_water"],
            field="persisted kill generation high-water",
        )
        _require_int(
            state["mode_revision_high_water"],
            field="persisted mode revision high-water",
        )
        _require_int(
            state["capital_fencing_high_water"],
            field="persisted capital fence high-water",
        )
        if state["required_action"] is not None:
            if state["required_action"] not in _ACTIONS:
                raise CommandFeedError("persisted required_action is unsupported")
        _parse_utc(state["updated_at"], field="persisted updated_at")

        kill = state["kill_envelope"]
        if kill is not None:
            signed = verify_signed_envelope(
                kill,
                trusted_public_keys=self._trusted_operator_public_keys,
                expected_body_schema=KILL_STATE_SCHEMA,
                require_active=False,
            )
            _validate_kill_body(
                signed.body,
                now=now,
                require_current=False,
                future_skew=self.maximum_future_skew,
            )
            if (
                int(signed.body["generation"])
                > int(state["kill_generation_high_water"])
            ):
                raise CommandFeedError(
                    "persisted kill generation exceeds high-water"
                )
        mode = state["desired_mode_envelope"]
        if mode is not None:
            signed = verify_signed_envelope(
                mode,
                trusted_public_keys=self._trusted_operator_public_keys,
                expected_body_schema=DESIRED_MODE_SCHEMA,
                require_active=False,
            )
            _validate_mode_body(
                signed.body,
                now=now,
                require_current=False,
            )
            if (
                int(signed.body["revision"])
                > int(state["mode_revision_high_water"])
            ):
                raise CommandFeedError(
                    "persisted mode revision exceeds high-water"
                )
        return cast(dict[str, Any], state)

    def _load_state(self, *, now: datetime) -> dict[str, Any]:
        rows = self._journal.events(kind=STATE_EVENT_KIND)
        if not rows:
            return self._bootstrap_state(now)
        return self._validate_stored_state(rows[-1]["payload"], now=now)

    @staticmethod
    def _cursor(state: Mapping[str, Any]) -> tuple[int, str]:
        cursor = state["cursor"]
        return int(cursor["sequence"]), str(cursor["digest"])

    def snapshot(self) -> dict[str, Any]:
        """Return the latest durable state; an invalid journal raises closed."""
        return deepcopy(self._load_state(now=self._now()))

    def submission_allowed(self) -> bool:
        """Return only durable, current mode/kill authority.

        Capital, Dummy-local risk, and broker/session gates remain independent
        mandatory checks at the execution sink.
        """
        try:
            now = self._now()
            state = self._load_state(now=now)
            return (
                state["status"] == "READY"
                and self._state_action(state, now=now)
                == "APPLY_SIGNED_CONTROLS"
            )
        except Exception:
            return False

    def _request_path(
        self,
        sequence: int,
        digest: str,
        request_nonce: str,
    ) -> str:
        return (
            f"/v1/cells/{CELL_ID}/commands"
            f"?after={sequence}&cursor={digest}"
            f"&request_nonce={request_nonce}&limit={self.page_limit}"
        )

    def _verify_checkpoint(
        self,
        checkpoint_raw: Any,
        signature_raw: Any,
    ) -> dict[str, Any]:
        if not isinstance(checkpoint_raw, dict):
            raise CommandFeedError("command checkpoint must be an object")
        if not isinstance(signature_raw, dict):
            raise CommandFeedError(
                "command checkpoint signature must be an object"
            )
        checkpoint = json.loads(canonical_json(checkpoint_raw))
        signature = json.loads(canonical_json(signature_raw))
        if (
            set(checkpoint) != _CHECKPOINT_FIELDS
            or checkpoint.get("schema") != CHECKPOINT_SCHEMA
        ):
            raise CommandFeedError("command checkpoint fields mismatch")
        if set(signature) != _CHECKPOINT_SIGNATURE_FIELDS:
            raise CommandFeedError(
                "command checkpoint signature fields mismatch"
            )
        if signature["algorithm"] != "Ed25519":
            raise CommandFeedError(
                "command checkpoint signature algorithm mismatch"
            )
        signer_key_id = _require_digest(
            signature["signer_key_id"],
            field="checkpoint signer_key_id",
        )
        public_key = self._trusted_checkpoint_public_keys.get(signer_key_id)
        if public_key is None:
            raise CommandFeedError("command checkpoint signer is not pinned")
        encoded_signature = _decode_base64url_signature(
            signature["signature"]
        )
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                encoded_signature,
                canonical_json(checkpoint).encode("utf-8"),
            )
        except (InvalidSignature, ValueError) as exc:
            raise CommandFeedError(
                "command checkpoint signature is invalid"
            ) from exc
        return cast(dict[str, Any], checkpoint)

    @staticmethod
    def _validate_ledger_proof(
        proof_raw: Any,
        *,
        sequence: int,
        event_id: str,
        event_digest: str,
        body_schema: str,
        envelope: VerifiedSignedEnvelope,
        page_observed_at: datetime,
    ) -> dict[str, Any]:
        if not isinstance(proof_raw, dict):
            raise CommandFeedError("command ledger_proof must be an object")
        proof = json.loads(canonical_json(proof_raw))
        if (
            set(proof) != _LEDGER_PROOF_FIELDS
            or proof.get("schema") != _LEDGER_PROOF_SCHEMA
        ):
            raise CommandFeedError("command ledger_proof fields mismatch")
        proof_sequence = _require_int(
            proof["global_sequence"],
            field="ledger proof global_sequence",
            minimum=1,
        )
        proof_event_id = _require_digest(
            proof["event_id"],
            field="ledger proof event_id",
        )
        proof_event_digest = _require_digest(
            proof["event_digest"],
            field="ledger proof event_digest",
        )
        proof_source_id = _require_identifier(
            proof["source_id"],
            field="ledger proof source_id",
        )
        proof_source_sequence = _require_int(
            proof["source_sequence"],
            field="ledger proof source_sequence",
            minimum=1,
        )
        proof_signer = _require_digest(
            proof["signer_key_id"],
            field="ledger proof signer_key_id",
        )
        proof_nonce = _require_identifier(
            proof["nonce"],
            field="ledger proof nonce",
        )
        proof_schema = _require_identifier(
            proof["event_schema"],
            field="ledger proof event_schema",
        )
        proof_correlation = _require_identifier(
            proof["correlation_id"],
            field="ledger proof correlation_id",
        )
        proof_causation = proof["causation_id"]
        if proof_causation is not None:
            _require_digest(
                proof_causation,
                field="ledger proof causation_id",
            )
        payload_digest = _require_digest(
            proof["payload_digest"],
            field="ledger proof payload_digest",
        )
        previous_source_digest = _require_digest(
            proof["previous_source_digest"],
            field="ledger proof previous_source_digest",
        )
        previous_global_digest = _require_digest(
            proof["previous_global_digest"],
            field="ledger proof previous_global_digest",
        )
        record_observed_at = _parse_utc(
            proof["observed_at"],
            field="ledger proof observed_at",
        )
        received_at = _parse_utc(
            proof["received_at"],
            field="ledger proof received_at",
        )
        if received_at > page_observed_at:
            raise CommandFeedError(
                "ledger proof was received after page observation"
            )
        if record_observed_at != max(received_at, envelope.not_before):
            raise CommandFeedError(
                "ledger proof observed_at differs from ingestion semantics"
            )
        if proof_sequence == 1 and previous_global_digest != ZERO_DIGEST:
            raise CommandFeedError(
                "first ledger event previous_global_digest mismatch"
            )
        if proof_sequence > 1 and previous_global_digest == ZERO_DIGEST:
            raise CommandFeedError(
                "noninitial ledger event has zero previous_global_digest"
            )
        if proof_source_sequence == 1 and previous_source_digest != ZERO_DIGEST:
            raise CommandFeedError(
                "first source event previous_source_digest mismatch"
            )
        if proof_source_sequence > 1 and previous_source_digest == ZERO_DIGEST:
            raise CommandFeedError(
                "noninitial source event has zero previous_source_digest"
            )

        wrapper = envelope.wrapper
        duplicated = {
            "global_sequence": (proof_sequence, sequence),
            "event_id": (proof_event_id, event_id),
            "event_digest": (proof_event_digest, event_digest),
            "source_id": (proof_source_id, envelope.source_id),
            "source_sequence": (
                proof_source_sequence,
                envelope.source_sequence,
            ),
            "signer_key_id": (proof_signer, envelope.signer_key_id),
            "nonce": (proof_nonce, envelope.nonce),
            "event_schema": (proof_schema, body_schema),
            "correlation_id": (
                proof_correlation,
                wrapper["correlation_id"],
            ),
            "causation_id": (
                proof_causation,
                wrapper["causation_id"],
            ),
            "payload_digest": (
                payload_digest,
                wrapper["body_digest"],
            ),
        }
        for field, (proof_value, expected_value) in duplicated.items():
            if proof_value != expected_value:
                raise CommandFeedError(
                    f"ledger proof {field} differs from command envelope"
                )

        event_material = {
            key: value
            for key, value in proof.items()
            if key not in {"schema", "event_digest"}
        }
        if sha256_json(event_material) != proof_event_digest:
            raise CommandFeedError(
                "ledger proof event_digest does not match event material"
            )
        return cast(dict[str, Any], proof)

    def _decode_command(
        self,
        raw: Any,
        *,
        now: datetime,
        observed_at: datetime,
        after_sequence: int,
        next_sequence: int,
    ) -> VerifiedFeedCommand:
        if not isinstance(raw, dict) or set(raw) != _COMMAND_FIELDS:
            raise CommandFeedError("command record fields mismatch")
        sequence = _require_int(
            raw["global_sequence"],
            field="command global_sequence",
            minimum=1,
        )
        if not after_sequence < sequence <= next_sequence:
            raise CommandFeedError("command sequence falls outside page cursor range")
        event_id = _require_digest(raw["event_id"], field="command event_id")
        event_digest = _require_digest(
            raw["event_digest"],
            field="command event_digest",
        )
        body_schema = _require_identifier(
            raw["body_schema"],
            field="command body_schema",
        )
        if body_schema not in _SUPPORTED_BODY_SCHEMAS:
            raise CommandFeedError("command body schema is unsupported")
        if not isinstance(raw["valid_now"], bool):
            raise CommandFeedError("command valid_now must be boolean")
        if not isinstance(raw["transport_window_current"], bool):
            raise CommandFeedError(
                "command transport_window_current must be boolean"
            )
        if raw["authority_effect"] not in _AUTHORITY_EFFECTS:
            raise CommandFeedError("command authority_effect is unsupported")
        envelope_raw = raw["envelope"]
        if not isinstance(envelope_raw, dict):
            raise CommandFeedError("command envelope must be an object")
        try:
            command_keys = (
                self._trusted_checkpoint_public_keys
                if body_schema == CAPITAL_ENVELOPE_SCHEMA
                else self._trusted_operator_public_keys
            )
            signed = verify_signed_envelope(
                envelope_raw,
                trusted_public_keys=command_keys,
                expected_body_schema=body_schema,
                require_active=False,
            )
        except ValueError as exc:
            raise CommandFeedError(f"signed command invalid: {exc}") from exc
        if signed.event_id != event_id:
            raise CommandFeedError("command event_id differs from signed envelope")
        ledger_proof = self._validate_ledger_proof(
            raw["ledger_proof"],
            sequence=sequence,
            event_id=event_id,
            event_digest=event_digest,
            body_schema=body_schema,
            envelope=signed,
            page_observed_at=observed_at,
        )
        core_window_active = (
            signed.not_before <= observed_at < signed.expires_at
        )
        if raw["transport_window_current"] is not core_window_active:
            raise CommandFeedError(
                "transport_window_current differs from signed envelope"
            )
        local_window_active = signed.not_before <= now < signed.expires_at

        capital: VerifiedCapitalEnvelope | None = None
        narrows_authority = False
        body_current_at_core = True
        body_current_locally = True
        if body_schema == KILL_STATE_SCHEMA:
            _validate_kill_body(
                signed.body,
                now=now,
                require_current=False,
                future_skew=self.maximum_future_skew,
            )
            narrows_authority = signed.body["active"] is True
            changed_at = _parse_utc(
                signed.body["changed_at"],
                field="kill-state changed_at",
            )
            body_current_at_core = (
                changed_at <= observed_at + _CORE_COMMAND_FUTURE_SKEW
            )
            body_current_locally = (
                changed_at <= now + _CORE_COMMAND_FUTURE_SKEW
            )
        elif body_schema == DESIRED_MODE_SCHEMA:
            _validate_mode_body(
                signed.body,
                now=now,
                require_current=False,
            )
            narrows_authority = signed.body["mode"] != "LIVE"
            body_not_before = _parse_utc(
                signed.body["not_before"],
                field="desired-mode not_before",
            )
            body_expires_at = _parse_utc(
                signed.body["expires_at"],
                field="desired-mode expires_at",
            )
            body_current_at_core = (
                body_not_before <= observed_at < body_expires_at
            )
            body_current_locally = (
                body_not_before <= now < body_expires_at
            )
        else:
            try:
                capital = verify_signed_capital_envelope(
                    envelope_raw,
                    trusted_public_keys=self._trusted_checkpoint_public_keys,
                    expected_venue=CELL_ID,
                    expected_account_hash=(
                        self._capital_adapter.expected_account_hash
                    ),
                    now=now,
                    max_ttl=self._capital_adapter.max_envelope_ttl,
                    require_active=False,
                )
            except ValueError as exc:
                raise CommandFeedError(
                    f"signed capital command invalid: {exc}"
                ) from exc
            body_current_at_core = (
                capital.not_before <= observed_at < capital.expires_at
            )
            body_current_locally = (
                capital.not_before <= now < capital.expires_at
            )
        valid_at_core = core_window_active and body_current_at_core
        if raw["valid_now"] is not valid_at_core:
            raise CommandFeedError(
                "command valid_now differs from signed authority state"
            )
        positive_grant = not narrows_authority
        expected_effect = (
            "APPLY_FAIL_CLOSED"
            if not positive_grant
            else "APPLY_POSITIVE"
            if valid_at_core
            else "HISTORICAL_ONLY"
        )
        if raw["authority_effect"] != expected_effect:
            raise CommandFeedError(
                "command authority_effect differs from signed authority state"
            )
        authority_current = (
            local_window_active and body_current_locally
        )
        return VerifiedFeedCommand(
            global_sequence=sequence,
            event_digest=event_digest,
            envelope=signed,
            ledger_proof=ledger_proof,
            capital=capital,
            authority_current=authority_current,
            authority_current_at_core=valid_at_core,
            narrows_authority=narrows_authority,
        )

    def _decode_page(
        self,
        response: CommandFeedResponse,
        *,
        state: Mapping[str, Any],
        now: datetime,
        expected_request_nonce: str,
    ) -> tuple[dict[str, Any], list[VerifiedFeedCommand]]:
        if isinstance(response.status_code, bool) or not isinstance(
            response.status_code,
            int,
        ):
            raise CommandFeedError("command feed response status is invalid")
        if response.status_code in {401, 403}:
            raise CommandFeedError("cell bearer authentication failed")
        if response.status_code == 409:
            raise CommandFeedError("Core rejected the persisted cursor")
        if response.status_code != 200:
            raise CommandFeedError(
                f"command feed returned HTTP {response.status_code}"
            )
        page = _strict_json(
            response.body,
            maximum_bytes=self.maximum_response_bytes,
        )
        if set(page) != _PAGE_FIELDS:
            raise CommandFeedError("command page fields mismatch")
        if page["schema"] != PAGE_SCHEMA:
            raise CommandFeedError("command page schema mismatch")

        # The checkpoint authenticates every authority-bearing projection
        # except the independently signed command envelopes. Verify it before
        # trusting cursors, action, timing, or command metadata.
        checkpoint = self._verify_checkpoint(
            page["checkpoint"],
            page["checkpoint_signature"],
        )
        mirrored_fields = {
            "cell_id",
            "request_nonce",
            "observed_at",
            "after_sequence",
            "after_digest",
            "next_sequence",
            "next_digest",
            "ledger_head_sequence",
            "ledger_head_digest",
            "required_action",
        }
        for field in mirrored_fields:
            if canonical_json(page[field]) != canonical_json(checkpoint[field]):
                raise CommandFeedError(
                    f"command page {field} differs from signed checkpoint"
                )
        if checkpoint["cell_id"] != CELL_ID:
            raise CommandFeedError("command page identity mismatch")
        request_nonce = _require_digest(
            checkpoint["request_nonce"],
            field="checkpoint request_nonce",
        )
        if request_nonce != expected_request_nonce:
            raise CommandFeedError(
                "checkpoint request_nonce differs from current request"
            )

        if not isinstance(page["commands"], list):
            raise CommandFeedError("command page commands must be an array")
        ordered_commands = checkpoint["ordered_commands"]
        if not isinstance(ordered_commands, list):
            raise CommandFeedError(
                "checkpoint ordered_commands must be an array"
            )
        if len(ordered_commands) != len(page["commands"]):
            raise CommandFeedError(
                "checkpoint command count differs from page"
            )
        for raw_command, projected in zip(
            page["commands"],
            ordered_commands,
            strict=True,
        ):
            if not isinstance(raw_command, dict):
                raise CommandFeedError("command record must be an object")
            if (
                not isinstance(projected, dict)
                or set(projected) != _CHECKPOINT_COMMAND_FIELDS
            ):
                raise CommandFeedError(
                    "checkpoint command projection fields mismatch"
                )
            projection = {
                key: value
                for key, value in raw_command.items()
                if key != "envelope"
            }
            if canonical_json(projection) != canonical_json(projected):
                raise CommandFeedError(
                    "page command differs from signed checkpoint projection"
                )

        observed_at = _parse_utc(page["observed_at"], field="page observed_at")
        if observed_at > now + self.maximum_future_skew:
            raise CommandFeedError("command page observation is from the future")
        if now - observed_at > self.maximum_page_age:
            raise CommandFeedError("command page observation is stale")

        current_sequence, current_digest = self._cursor(state)
        after_sequence = _require_int(
            page["after_sequence"],
            field="page after_sequence",
        )
        after_digest = _require_digest(
            page["after_digest"],
            field="page after_digest",
        )
        if (after_sequence, after_digest) != (
            current_sequence,
            current_digest,
        ):
            raise CommandFeedError("command page does not continue persisted cursor")
        next_sequence = _require_int(
            page["next_sequence"],
            field="page next_sequence",
        )
        next_digest = _require_digest(
            page["next_digest"],
            field="page next_digest",
        )
        ledger_head = _require_int(
            page["ledger_head_sequence"],
            field="page ledger_head_sequence",
        )
        ledger_head_digest = _require_digest(
            page["ledger_head_digest"],
            field="page ledger_head_digest",
        )
        if not after_sequence <= next_sequence <= ledger_head:
            raise CommandFeedError("command page cursor range is invalid")
        if after_sequence == 0 and after_digest != ZERO_DIGEST:
            raise CommandFeedError("bootstrap cursor digest mismatch")
        if after_sequence > 0 and after_digest == ZERO_DIGEST:
            raise CommandFeedError("non-bootstrap cursor has zero digest")
        if ledger_head == 0 and ledger_head_digest != ZERO_DIGEST:
            raise CommandFeedError("empty ledger head digest mismatch")
        if ledger_head > 0 and ledger_head_digest == ZERO_DIGEST:
            raise CommandFeedError("nonempty ledger head has zero digest")
        if ledger_head == next_sequence and ledger_head_digest != next_digest:
            raise CommandFeedError(
                "page cursor digest differs from ledger head"
            )
        if next_sequence - after_sequence > self.page_limit:
            raise CommandFeedError("command page contains a ledger sequence gap")
        if next_sequence == after_sequence and next_digest != after_digest:
            raise CommandFeedError("stationary cursor digest mismatch")
        if next_sequence > after_sequence and next_digest == after_digest:
            raise CommandFeedError("advancing cursor digest did not change")
        if next_sequence > 0 and next_digest == ZERO_DIGEST:
            raise CommandFeedError("advancing cursor cannot use zero digest")
        if page["has_more"] is not (next_sequence < ledger_head):
            raise CommandFeedError("command page has_more is inconsistent")
        if page["required_action"] not in _ACTIONS:
            raise CommandFeedError("command page required_action is unsupported")
        if len(page["commands"]) > self.page_limit:
            raise CommandFeedError("command page exceeds requested limit")

        commands = [
            self._decode_command(
                item,
                now=now,
                observed_at=observed_at,
                after_sequence=after_sequence,
                next_sequence=next_sequence,
            )
            for item in page["commands"]
        ]
        sequences = [command.global_sequence for command in commands]
        if sequences != sorted(set(sequences)):
            raise CommandFeedError("command sequences are not strictly increasing")
        previous_command: VerifiedFeedCommand | None = None
        latest_source_command: dict[
            str,
            VerifiedFeedCommand,
        ] = {}
        for command in commands:
            proof = command.ledger_proof
            if (
                previous_command is None
                and command.global_sequence == after_sequence + 1
                and proof["previous_global_digest"] != after_digest
            ):
                raise CommandFeedError(
                    "first command does not extend persisted cursor"
                )
            if (
                previous_command is not None
                and command.global_sequence
                == previous_command.global_sequence + 1
                and proof["previous_global_digest"]
                != previous_command.event_digest
            ):
                raise CommandFeedError(
                    "adjacent command ledger chain is discontinuous"
                )
            prior_source = latest_source_command.get(command.envelope.source_id)
            if prior_source is not None:
                current_source_sequence = command.envelope.source_sequence
                prior_source_sequence = prior_source.envelope.source_sequence
                if current_source_sequence <= prior_source_sequence:
                    raise CommandFeedError(
                        "command source sequence is not increasing"
                    )
                if (
                    current_source_sequence == prior_source_sequence + 1
                    and proof["previous_source_digest"]
                    != prior_source.event_digest
                ):
                    raise CommandFeedError(
                        "adjacent source command chain is discontinuous"
                    )
            latest_source_command[command.envelope.source_id] = command
            previous_command = command
        if next_sequence == after_sequence and commands:
            raise CommandFeedError("stationary command page cannot contain commands")
        last_at_cursor = next(
            (
                command
                for command in reversed(commands)
                if command.global_sequence == next_sequence
            ),
            None,
        )
        if last_at_cursor is not None and last_at_cursor.event_digest != next_digest:
            raise CommandFeedError("command event digest differs from page cursor")
        return page, commands

    def _stage_commands(
        self,
        state: Mapping[str, Any],
        commands: list[VerifiedFeedCommand],
        *,
        now: datetime,
        use_core_authority: bool = False,
    ) -> tuple[dict[str, Any], int, bool]:
        staged = deepcopy(dict(state))
        policy_epoch = int(staged["policy_epoch"])
        applied_count = 0
        ignored_positive = False
        for command in commands:
            authority_current = (
                command.authority_current_at_core
                if use_core_authority
                else command.authority_current
            )
            body = command.envelope.body
            command_epoch = _require_int(
                body["policy_epoch"],
                field="command policy_epoch",
                minimum=1,
            )
            if command_epoch < policy_epoch:
                raise CommandFeedError("command policy epoch regressed")
            policy_epoch = max(policy_epoch, command_epoch)
            if command.envelope.body_schema == KILL_STATE_SCHEMA:
                generation = int(body["generation"])
                high_water = int(staged["kill_generation_high_water"])
                if generation <= high_water:
                    raise CommandFeedError(
                        "kill-state generation did not advance"
                    )
                staged["kill_generation_high_water"] = generation
                if command.narrows_authority or authority_current:
                    staged["kill_envelope"] = command.envelope.wrapper
                    applied_count += 1
                else:
                    ignored_positive = True
            elif command.envelope.body_schema == DESIRED_MODE_SCHEMA:
                revision = int(body["revision"])
                high_water = int(staged["mode_revision_high_water"])
                if revision <= high_water:
                    raise CommandFeedError(
                        "desired-mode revision did not advance"
                    )
                staged["mode_revision_high_water"] = revision
                if command.narrows_authority or authority_current:
                    staged["desired_mode_envelope"] = command.envelope.wrapper
                    applied_count += 1
                else:
                    ignored_positive = True
            else:
                if command.capital is None:
                    raise CommandFeedError(
                        "capital command lacks verified body"
                    )
                fence = command.capital.fencing_generation
                high_water = int(staged["capital_fencing_high_water"])
                if fence <= high_water:
                    raise CommandFeedError(
                        "capital fencing generation did not advance"
                    )
                staged["capital_fencing_high_water"] = fence
                if authority_current:
                    applied_count += 1
                else:
                    ignored_positive = True
        staged["policy_epoch"] = policy_epoch
        staged["updated_at"] = _format_utc(now)
        return staged, applied_count, ignored_positive

    def _state_action(
        self,
        state: Mapping[str, Any],
        *,
        now: datetime,
    ) -> str:
        kill = state["kill_envelope"]
        mode = state["desired_mode_envelope"]
        if kill is not None and kill["body"]["active"] is True:
            return "CANCEL_AND_RECONCILE"
        if mode is None:
            return "PAUSE_NEW_RISK"
        if mode["body"]["mode"] != "LIVE":
            return "PAUSE_NEW_RISK"
        mode_not_before = _parse_utc(
            mode["not_before"],
            field="desired-mode wrapper not_before",
        )
        mode_expires_at = _parse_utc(
            mode["expires_at"],
            field="desired-mode wrapper expires_at",
        )
        if not mode_not_before <= now < mode_expires_at:
            return "PAUSE_NEW_RISK"
        try:
            _validate_mode_body(
                mode["body"],
                now=now,
                require_current=True,
            )
        except CommandFeedError:
            return "PAUSE_NEW_RISK"
        if kill is None or kill["body"]["active"] is not False:
            return "PAUSE_NEW_RISK"
        kill_not_before = _parse_utc(
            kill["not_before"],
            field="kill-state wrapper not_before",
        )
        kill_expires_at = _parse_utc(
            kill["expires_at"],
            field="kill-state wrapper expires_at",
        )
        if not kill_not_before <= now < kill_expires_at:
            return "PAUSE_NEW_RISK"
        _validate_kill_body(
            kill["body"],
            now=now,
            require_current=True,
            future_skew=self.maximum_future_skew,
        )
        return "APPLY_SIGNED_CONTROLS"

    def _persist_state(
        self,
        state: Mapping[str, Any],
        *,
        expected_cursor: tuple[int, str],
    ) -> None:
        next_cursor = self._cursor(state)

        def validate_existing(rows: tuple[dict[str, Any], ...]) -> None:
            prior_states = [
                row
                for row in rows
                if row.get("kind") == STATE_EVENT_KIND
            ]
            actual_cursor = (
                (0, ZERO_DIGEST)
                if not prior_states
                else self._cursor(prior_states[-1]["payload"])
            )
            if actual_cursor != expected_cursor:
                raise CommandFeedError(
                    "command-feed cursor changed during poll"
                )
            if next_cursor[0] < actual_cursor[0]:
                raise CommandFeedError("command-feed cursor cannot regress")
            if (
                next_cursor[0] == actual_cursor[0]
                and next_cursor[1] != actual_cursor[1]
            ):
                raise CommandFeedError(
                    "stationary command-feed cursor digest changed"
                )

        self._journal.append(
            STATE_EVENT_KIND,
            dict(state),
            validate_existing=validate_existing,
            validate_existing_latest_kinds=(STATE_EVENT_KIND,),
        )

    def _fail_closed(
        self,
        *,
        state: Mapping[str, Any],
        reason: str,
        now: datetime,
    ) -> CommandFeedPollResult:
        safe_reason = str(reason).strip()[:512] or "command feed failed closed"
        try:
            self._fail_closed_handler(safe_reason)
        except Exception as exc:
            safe_reason = (
                f"{safe_reason}; fail-closed handler failed:{type(exc).__name__}"
            )[:512]
        failed = deepcopy(dict(state))
        failed["status"] = "FAIL_CLOSED"
        failed["reason"] = safe_reason
        failed["updated_at"] = _format_utc(now)
        try:
            self._persist_state(
                failed,
                expected_cursor=self._cursor(state),
            )
        except Exception as exc:
            safe_reason = (
                f"{safe_reason}; state persistence failed:{type(exc).__name__}"
            )[:512]
        sequence, digest = self._cursor(state)
        return CommandFeedPollResult(
            page_accepted=False,
            cursor_sequence=sequence,
            cursor_digest=digest,
            commands_applied=0,
            required_action=state.get("required_action"),
            submission_allowed=False,
            reason=safe_reason,
        )

    def poll_once(self) -> CommandFeedPollResult:
        """Serialize and apply at most one page across local runner processes."""
        try:
            with self._journal.serialized_operation():
                return self._poll_once_serialized()
        except Exception as exc:
            try:
                self._fail_closed_handler(
                    f"command operation lock failed:{type(exc).__name__}"
                )
            except Exception:
                pass
            return CommandFeedPollResult(
                page_accepted=False,
                cursor_sequence=0,
                cursor_digest=ZERO_DIGEST,
                commands_applied=0,
                required_action=None,
                submission_allowed=False,
                reason=(
                    f"command operation lock failed:{type(exc).__name__}"
                ),
            )

    def _poll_once_serialized(self) -> CommandFeedPollResult:
        """Fetch, verify, dispatch, and durably advance at most one page.

        There are no retries. The injected transport is called exactly once,
        and no method in this module can submit or cancel a broker order.
        """
        now = self._now()
        try:
            state = self._load_state(now=now)
        except Exception as exc:
            bootstrap = self._bootstrap_state(now)
            return self._fail_closed(
                state=bootstrap,
                reason=f"persisted cursor unavailable:{type(exc).__name__}",
                now=now,
            )

        try:
            token = self._cell_token_provider()
        except Exception as exc:
            return self._fail_closed(
                state=state,
                reason=f"cell token unavailable:{type(exc).__name__}",
                now=now,
            )
        if (
            not isinstance(token, str)
            or not token
            or token != token.strip()
            or "\r" in token
            or "\n" in token
        ):
            return self._fail_closed(
                state=state,
                reason="cell token is not a canonical secret",
                now=now,
            )

        sequence, digest = self._cursor(state)
        try:
            request_nonce = self._request_nonce_fn()
        except Exception as exc:
            return self._fail_closed(
                state=state,
                reason=f"request nonce unavailable:{type(exc).__name__}",
                now=now,
            )
        try:
            request_nonce = _require_digest(
                request_nonce,
                field="request nonce",
            )
        except CommandFeedError as exc:
            return self._fail_closed(
                state=state,
                reason=str(exc),
                now=now,
            )
        if request_nonce == self._last_request_nonce:
            return self._fail_closed(
                state=state,
                reason="request nonce generator repeated a nonce",
                now=now,
            )
        self._last_request_nonce = request_nonce
        path = self._request_path(sequence, digest, request_nonce)
        try:
            response = self._transport(
                path,
                {"Authorization": f"Bearer {token}"},
            )
        except Exception as exc:
            return self._fail_closed(
                state=state,
                reason=f"command feed transport failed:{type(exc).__name__}",
                now=now,
            )
        finally:
            token = ""
        if not isinstance(response, CommandFeedResponse):
            return self._fail_closed(
                state=state,
                reason="command feed transport returned an unsupported response",
                now=now,
            )

        try:
            received_now = self._now()
            page, commands = self._decode_page(
                response,
                state=state,
                now=received_now,
                expected_request_nonce=request_nonce,
            )
            page_observed_at = _parse_utc(
                page["observed_at"],
                field="page observed_at",
            )
            core_staged, _, _ = self._stage_commands(
                state,
                commands,
                now=page_observed_at,
                use_core_authority=True,
            )
            expected_core_action = self._state_action(
                core_staged,
                now=page_observed_at,
            )
            if (
                page["has_more"] is False
                and page["required_action"] != expected_core_action
            ):
                raise CommandFeedError(
                    "Core required_action differs from verified local state"
                )
            staged, applied_count, ignored_positive = self._stage_commands(
                state,
                commands,
                now=received_now,
            )

            # Only narrowing transitions leave the durable feed snapshot.
            # Inactive kill and LIVE mode never clear a local latch here.
            # Apply every reduction before exposing any positive capital from
            # the same page.
            for command in commands:
                if (
                    command.envelope.body_schema == KILL_STATE_SCHEMA
                    and command.envelope.body["active"] is True
                ):
                    self._kill_handler(command)
                elif (
                    command.envelope.body_schema == DESIRED_MODE_SCHEMA
                    and command.envelope.body["mode"] != "LIVE"
                ):
                    self._mode_handler(command)

            # Capital acceptance is a local ceiling only. Replays caused by a
            # crash before cursor persistence are exact-event idempotent.
            for command in commands:
                if (
                    command.envelope.body_schema == CAPITAL_ENVELOPE_SCHEMA
                    and command.authority_current
                ):
                    self._capital_adapter.accept_signed_envelope(
                        command.envelope.wrapper,
                        ledger_event_digest=command.event_digest,
                        ledger_global_sequence=command.global_sequence,
                    )

            staged["cursor"] = {
                "sequence": page["next_sequence"],
                "digest": page["next_digest"],
            }
            staged["required_action"] = page["required_action"]
            commit_now = self._now()
            if ignored_positive:
                staged["status"] = "FAIL_CLOSED"
                staged["reason"] = (
                    "expired or future positive authority was ignored"
                )
                self._fail_closed_handler(staged["reason"])
                submission_allowed = False
            elif page["has_more"] is True:
                staged["status"] = "CATCHING_UP"
                staged["reason"] = "verified command backlog remains"
                self._fail_closed_handler(staged["reason"])
                submission_allowed = False
            else:
                expected_action = self._state_action(
                    staged,
                    now=commit_now,
                )
                submission_allowed = (
                    expected_action == "APPLY_SIGNED_CONTROLS"
                )
                staged["status"] = (
                    "READY" if submission_allowed else "FAIL_CLOSED"
                )
                staged["reason"] = (
                    "signed controls verified and cursor synchronized"
                    if submission_allowed
                    else f"local controls require {expected_action}"
                )
                if not submission_allowed:
                    self._fail_closed_handler(staged["reason"])
            staged["updated_at"] = _format_utc(commit_now)
            self._persist_state(
                staged,
                expected_cursor=self._cursor(state),
            )
            post_commit_now = self._now()
            if (
                submission_allowed
                and self._state_action(staged, now=post_commit_now)
                != "APPLY_SIGNED_CONTROLS"
            ):
                downgraded = deepcopy(staged)
                downgraded["status"] = "FAIL_CLOSED"
                downgraded["reason"] = (
                    "positive authority expired during state commit"
                )
                downgraded["updated_at"] = _format_utc(post_commit_now)
                self._fail_closed_handler(downgraded["reason"])
                self._persist_state(
                    downgraded,
                    expected_cursor=self._cursor(staged),
                )
                staged = downgraded
                submission_allowed = False
        except Exception as exc:
            try:
                failure_now = self._now()
            except Exception:
                failure_now = now
            return self._fail_closed(
                state=state,
                reason=f"command page rejected:{type(exc).__name__}:{exc}",
                now=failure_now,
            )

        next_sequence, next_digest = self._cursor(staged)
        return CommandFeedPollResult(
            page_accepted=True,
            cursor_sequence=next_sequence,
            cursor_digest=next_digest,
            commands_applied=applied_count,
            required_action=page["required_action"],
            submission_allowed=submission_allowed,
            reason=str(staged["reason"]),
        )


__all__ = [
    "CELL_ID",
    "CommandFeedError",
    "CommandFeedPollResult",
    "CommandFeedResponse",
    "CoreCommandFeedConsumer",
    "DESIRED_MODE_SCHEMA",
    "KILL_STATE_SCHEMA",
    "PAGE_SCHEMA",
    "STATE_EVENT_KIND",
    "STATE_SCHEMA",
    "VerifiedFeedCommand",
    "ZERO_DIGEST",
]
