from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from live_firewall.dumbmoney_journal_anchor import (
    ANCHOR_BODY_SCHEMA,
    ANCHOR_CHECKPOINT_SCHEMA,
    ANCHOR_REQUEST_SCHEMA,
    ANCHOR_RESPONSE_SCHEMA,
    CoreJournalAnchorClient,
    JournalAnchorError,
    JournalAnchorResponse,
)
from live_firewall.operational_journal import canonical_json, sha256_json


NOW = datetime(2026, 7, 26, 22, 0, 0, tzinfo=timezone.utc)
ACCOUNT_HASH = hashlib.sha256(b"dummy-account").hexdigest()
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes_raw()
SIGNER_KEY_ID = hashlib.sha256(PUBLIC_KEY).hexdigest()
ZERO_DIGEST = "0" * 64


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _signature(value: dict[str, Any]) -> str:
    return (
        base64.urlsafe_b64encode(
            PRIVATE_KEY.sign(canonical_json(value).encode("utf-8"))
        )
        .decode("ascii")
        .rstrip("=")
    )


def _signed_anchor(
    body: dict[str, Any],
    *,
    observed_at: datetime,
) -> dict[str, Any]:
    identity = {
        "schema": "dumbmoney.signed-envelope.v1",
        "source_id": "dumbmoney-core",
        "source_sequence": 1,
        "correlation_id": "journal-anchor:dummy_kalshi:test-journal",
        "causation_id": None,
        "nonce": _hash("anchor-event-nonce"),
        "not_before": _z(observed_at),
        "expires_at": _z(observed_at + timedelta(seconds=120)),
        "body_schema": ANCHOR_BODY_SCHEMA,
        "body_digest": sha256_json(body),
        "body": body,
        "signature_algorithm": "Ed25519",
        "signer_key_id": SIGNER_KEY_ID,
    }
    envelope = {**identity, "event_id": sha256_json(identity)}
    envelope["signature"] = _signature(envelope)
    return envelope


def _response(
    request: dict[str, Any],
    *,
    observed_at: datetime = NOW,
    reused: bool = False,
) -> dict[str, Any]:
    previous = ZERO_DIGEST
    anchor_identity = {
        "schema": ANCHOR_BODY_SCHEMA,
        "venue": "dummy_kalshi",
        "account_hash": request["account_hash"],
        "journal_name": request["journal_name"],
        "journal_schema": request["journal_schema"],
        "journal_stream_id": request["journal_stream_id"],
        "journal_sequence": request["journal_sequence"],
        "journal_head_sha256": request["journal_head_sha256"],
        "previous_anchor_body_digest": previous,
    }
    body = {
        **anchor_identity,
        "anchor_id": sha256_json(anchor_identity),
        "anchored_at": _z(observed_at),
    }
    envelope = _signed_anchor(body, observed_at=observed_at)
    event_material = {
        "global_sequence": 1,
        "event_id": envelope["event_id"],
        "source_id": envelope["source_id"],
        "source_sequence": envelope["source_sequence"],
        "signer_key_id": envelope["signer_key_id"],
        "nonce": envelope["nonce"],
        "event_schema": envelope["body_schema"],
        "observed_at": _z(observed_at),
        "received_at": _z(observed_at),
        "correlation_id": envelope["correlation_id"],
        "causation_id": envelope["causation_id"],
        "payload_digest": envelope["body_digest"],
        "previous_source_digest": ZERO_DIGEST,
        "previous_global_digest": ZERO_DIGEST,
    }
    event_digest = sha256_json(event_material)
    proof = {
        "schema": "dumbmoney.ledger-event-proof.v1",
        **event_material,
        "event_digest": event_digest,
    }
    checkpoint = {
        "schema": ANCHOR_CHECKPOINT_SCHEMA,
        "cell_id": "dummy_kalshi",
        "request_nonce": request["request_nonce"],
        "account_hash": request["account_hash"],
        "journal_name": request["journal_name"],
        "journal_schema": request["journal_schema"],
        "journal_stream_id": request["journal_stream_id"],
        "journal_sequence": request["journal_sequence"],
        "journal_head_sha256": request["journal_head_sha256"],
        "anchor_body_digest": envelope["body_digest"],
        "anchor_event_digest": event_digest,
        "reused": reused,
        "observed_at": _z(observed_at),
    }
    return {
        "schema": ANCHOR_RESPONSE_SCHEMA,
        "cell_id": "dummy_kalshi",
        "request_nonce": request["request_nonce"],
        "observed_at": _z(observed_at),
        "reused": reused,
        "anchor_envelope": envelope,
        "ledger_proof": proof,
        "checkpoint": checkpoint,
        "checkpoint_signature": {
            "algorithm": "Ed25519",
            "signer_key_id": SIGNER_KEY_ID,
            "signature": _signature(checkpoint),
        },
    }


class _Transport:
    def __init__(
        self,
        mutate: Any = None,
        *,
        status_code: int = 200,
    ) -> None:
        self.mutate = mutate
        self.status_code = status_code
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def __call__(
        self,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> JournalAnchorResponse:
        request = json.loads(body)
        self.calls.append((path, dict(headers), request))
        payload = _response(request)
        if self.mutate is not None:
            self.mutate(payload)
        return JournalAnchorResponse(
            status_code=self.status_code,
            body=canonical_json(payload).encode("utf-8"),
        )


def _client(transport: Any, *, now: datetime = NOW) -> CoreJournalAnchorClient:
    return CoreJournalAnchorClient(
        transport=transport,
        cell_token_provider=lambda: "t" * 64,
        trusted_core_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_account_hash=ACCOUNT_HASH,
        request_nonce_fn=lambda: _hash("request-nonce"),
        now_fn=lambda: now,
    )


def test_exact_core_anchor_checkpoint_and_ledger_proof_are_accepted() -> None:
    transport = _Transport()
    client = _client(transport)
    head = _hash("journal-head")

    result = client.anchor(
        journal_name="capital-operational",
        journal_schema="dummy.sqlite-operational-journal.v1",
        journal_sequence=7,
        journal_head_sha256=head,
    )

    assert result.journal_sequence == 7
    assert result.journal_head_sha256 == head
    assert result.reused is False
    path, headers, request = transport.calls[0]
    assert path == "/v1/cells/dummy_kalshi/journal-heads:anchor"
    assert headers == {
        "Authorization": f"Bearer {'t' * 64}",
        "Content-Type": "application/json",
    }
    assert request["schema"] == ANCHOR_REQUEST_SCHEMA
    assert request["journal_stream_id"] == client.stream_id(
        "capital-operational"
    )


def test_checkpoint_tamper_fails_closed() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["checkpoint"]["journal_sequence"] = 6

    with pytest.raises(
        JournalAnchorError,
        match="signature is invalid",
    ):
        _client(_Transport(mutate)).anchor(
            journal_name="capital-operational",
            journal_schema="dummy.sqlite-operational-journal.v1",
            journal_sequence=7,
            journal_head_sha256=_hash("journal-head"),
        )


def test_envelope_tamper_is_normalized_to_anchor_error() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["anchor_envelope"]["body"]["journal_sequence"] = 6

    with pytest.raises(
        JournalAnchorError,
        match="anchor envelope is invalid",
    ):
        _client(_Transport(mutate)).anchor(
            journal_name="capital-operational",
            journal_schema="dummy.sqlite-operational-journal.v1",
            journal_sequence=7,
            journal_head_sha256=_hash("journal-head"),
        )


def test_stale_checkpoint_and_core_rejection_fail_closed() -> None:
    def stale(
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> JournalAnchorResponse:
        del path, headers
        request = json.loads(body)
        payload = _response(
            request,
            observed_at=NOW - timedelta(seconds=31),
        )
        return JournalAnchorResponse(
            200,
            canonical_json(payload).encode("utf-8"),
        )

    with pytest.raises(JournalAnchorError, match="is not current"):
        _client(stale).anchor(
            journal_name="command-feed",
            journal_schema="dummy.sqlite-operational-journal.v1",
            journal_sequence=0,
            journal_head_sha256=ZERO_DIGEST,
        )

    with pytest.raises(JournalAnchorError, match="rejected"):
        _client(_Transport(status_code=409)).anchor(
            journal_name="command-feed",
            journal_schema="dummy.sqlite-operational-journal.v1",
            journal_sequence=0,
            journal_head_sha256=ZERO_DIGEST,
        )


def test_sequence_zero_and_zero_head_must_match() -> None:
    client = _client(_Transport())
    with pytest.raises(JournalAnchorError, match="zero head"):
        client.anchor(
            journal_name="command-feed",
            journal_schema="dummy.sqlite-operational-journal.v1",
            journal_sequence=0,
            journal_head_sha256=_hash("not-empty"),
        )
    with pytest.raises(JournalAnchorError, match="zero head"):
        client.anchor(
            journal_name="command-feed",
            journal_schema="dummy.sqlite-operational-journal.v1",
            journal_sequence=1,
            journal_head_sha256=ZERO_DIGEST,
        )
