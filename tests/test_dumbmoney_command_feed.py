from __future__ import annotations

import base64
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from live_firewall.dumbmoney_capital import (
    CAPITAL_ENVELOPE_SCHEMA,
    SIGNED_ENVELOPE_SCHEMA,
    CapitalEnvelopeAdapter,
)
from live_firewall.dumbmoney_command_feed import (
    DESIRED_MODE_SCHEMA,
    KILL_STATE_SCHEMA,
    CommandFeedResponse,
    CoreCommandFeedConsumer,
    ZERO_DIGEST,
)
from live_firewall.operational_journal import (
    AppendOnlyOperationalJournal,
    canonical_json,
    sha256_json,
)


NOW = datetime(2026, 7, 26, 21, 0, 0, tzinfo=timezone.utc)
CORE_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
CORE_PUBLIC_KEY = CORE_PRIVATE_KEY.public_key().public_bytes_raw()
CORE_SIGNER_KEY_ID = hashlib.sha256(CORE_PUBLIC_KEY).hexdigest()
OPERATOR_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(
    bytes(range(1, 33))
)
OPERATOR_PUBLIC_KEY = OPERATOR_PRIVATE_KEY.public_key().public_bytes_raw()
OPERATOR_SIGNER_KEY_ID = hashlib.sha256(OPERATOR_PUBLIC_KEY).hexdigest()
ACCOUNT_HASH = hashlib.sha256(b"dummy-command-feed-account").hexdigest()
STRATEGY_HASH = hashlib.sha256(b"strategy").hexdigest()
PASSPORT_HASH = hashlib.sha256(b"passport").hexdigest()
PROMOTION_HASH = hashlib.sha256(b"promotion").hexdigest()
INSTRUMENT = "event_contract:KXTEST-26JUL"
REQUEST_NONCE_1 = "1" * 64
REQUEST_NONCE_2 = "2" * 64
REQUEST_NONCE_3 = "3" * 64


class _UnusedLineageResolver:
    def resolve_lineage(self, **_kwargs):
        raise AssertionError("command-feed tests must not resolve live lineage")


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sign(
    body: dict,
    *,
    source_sequence: int,
    not_before: datetime,
    expires_at: datetime,
    signer_role: str | None = None,
) -> dict:
    role = signer_role or (
        "core" if body["schema"] == CAPITAL_ENVELOPE_SCHEMA else "operator"
    )
    if role == "core":
        private_key = CORE_PRIVATE_KEY
        signer_key_id = CORE_SIGNER_KEY_ID
    elif role == "operator":
        private_key = OPERATOR_PRIVATE_KEY
        signer_key_id = OPERATOR_SIGNER_KEY_ID
    else:
        raise ValueError(f"unsupported signer role: {role}")
    identity = {
        "schema": SIGNED_ENVELOPE_SCHEMA,
        "source_id": "dumbmoney-control",
        "source_sequence": source_sequence,
        "correlation_id": "dummy-command-feed-test",
        "causation_id": None,
        "nonce": f"command-nonce-{source_sequence}",
        "not_before": _z(not_before),
        "expires_at": _z(expires_at),
        "body_schema": body["schema"],
        "body_digest": sha256_json(body),
        "body": body,
        "signature_algorithm": "Ed25519",
        "signer_key_id": signer_key_id,
    }
    wrapper = {**identity, "event_id": sha256_json(identity)}
    wrapper["signature"] = (
        base64.urlsafe_b64encode(
            private_key.sign(canonical_json(wrapper).encode("utf-8"))
        )
        .decode("ascii")
        .rstrip("=")
    )
    return wrapper


def _kill(
    *,
    sequence: int,
    active: bool,
    generation: int,
    not_before: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(minutes=5),
    signer_role: str | None = None,
) -> dict:
    body = {
        "schema": KILL_STATE_SCHEMA,
        "active": active,
        "generation": generation,
        "reason": "test kill state",
        "changed_by": "test-operator",
        "policy_epoch": 1,
        "changed_at": _z(min(NOW, expires_at - timedelta(seconds=1))),
    }
    return _sign(
        body,
        source_sequence=sequence,
        not_before=not_before,
        expires_at=expires_at,
        signer_role=signer_role,
    )


def _mode(
    *,
    sequence: int,
    mode: str,
    revision: int,
    not_before: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(minutes=5),
    signer_role: str | None = None,
) -> dict:
    body = {
        "schema": DESIRED_MODE_SCHEMA,
        "venue": "dummy_kalshi",
        "mode": mode,
        "revision": revision,
        "reason": "test desired mode",
        "policy_epoch": 1,
        "not_before": _z(not_before),
        "expires_at": _z(expires_at),
    }
    return _sign(
        body,
        source_sequence=sequence,
        not_before=not_before,
        expires_at=expires_at,
        signer_role=signer_role,
    )


def _capital(
    *,
    sequence: int,
    fence: int = 1,
    not_before: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(seconds=50),
    signer_role: str | None = None,
) -> dict:
    body = {
        "schema": CAPITAL_ENVELOPE_SCHEMA,
        "envelope_id": _hash(f"capital-envelope:{sequence}"),
        "mandate_id": _hash("mandate"),
        "venue": "dummy_kalshi",
        "account_hash": ACCOUNT_HASH,
        "strategy_hashes": [STRATEGY_HASH],
        "passport_hashes": [PASSPORT_HASH],
        "promotion_hashes": [PROMOTION_HASH],
        "authorized_instruments": [INSTRUMENT],
        "authorized_mode": "LIVE",
        "max_order_risk_cents": 100,
        "max_open_risk_cents": 500,
        "max_correlated_risk_cents": 300,
        "max_daily_loss_cents": 200,
        "max_open_orders": 3,
        "fencing_generation": fence,
        "policy_epoch": 1,
        "not_before": _z(not_before),
        "expires_at": _z(expires_at),
    }
    return _sign(
        body,
        source_sequence=sequence,
        not_before=not_before,
        expires_at=expires_at,
        signer_role=signer_role,
    )


def _command(
    envelope: dict,
    *,
    global_sequence: int,
) -> dict:
    return {
        "global_sequence": global_sequence,
        "event_id": envelope["event_id"],
        "event_digest": ZERO_DIGEST,
        "body_schema": envelope["body_schema"],
        "valid_now": False,
        "transport_window_current": False,
        "authority_effect": "HISTORICAL_ONLY",
        "ledger_proof": {},
        "envelope": envelope,
    }


def _parse_z(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _decorate_commands(
    commands: list[dict],
    *,
    after_sequence: int,
    after_digest: str,
    observed_at: datetime,
) -> None:
    previous_command: dict | None = None
    source_heads: dict[str, dict] = {}
    for command in commands:
        envelope = command["envelope"]
        body = envelope["body"]
        wrapper_not_before = _parse_z(envelope["not_before"])
        wrapper_expires_at = _parse_z(envelope["expires_at"])
        transport_current = (
            wrapper_not_before <= observed_at < wrapper_expires_at
        )
        if envelope["body_schema"] == KILL_STATE_SCHEMA:
            body_current = (
                _parse_z(body["changed_at"])
                <= observed_at + timedelta(seconds=5)
            )
            positive_grant = body["active"] is False
        elif envelope["body_schema"] in {
            DESIRED_MODE_SCHEMA,
            CAPITAL_ENVELOPE_SCHEMA,
        }:
            body_current = (
                _parse_z(body["not_before"])
                <= observed_at
                < _parse_z(body["expires_at"])
            )
            positive_grant = (
                envelope["body_schema"] == CAPITAL_ENVELOPE_SCHEMA
                or body["mode"] == "LIVE"
            )
        else:
            body_current = transport_current
            positive_grant = True
        valid_now = transport_current and body_current
        command["transport_window_current"] = transport_current
        command["valid_now"] = valid_now
        command["authority_effect"] = (
            "APPLY_FAIL_CLOSED"
            if not positive_grant
            else "APPLY_POSITIVE"
            if valid_now
            else "HISTORICAL_ONLY"
        )

        sequence = command["global_sequence"]
        if sequence == 1:
            previous_global_digest = ZERO_DIGEST
        elif sequence == after_sequence + 1:
            previous_global_digest = after_digest
        elif (
            previous_command is not None
            and sequence == previous_command["global_sequence"] + 1
        ):
            previous_global_digest = previous_command["event_digest"]
        else:
            previous_global_digest = _hash(
                f"unprojected-global-event:{sequence - 1}"
            )

        source_id = envelope["source_id"]
        source_sequence = envelope["source_sequence"]
        prior_source = source_heads.get(source_id)
        if source_sequence == 1:
            previous_source_digest = ZERO_DIGEST
        elif (
            prior_source is not None
            and source_sequence
            == prior_source["envelope"]["source_sequence"] + 1
        ):
            previous_source_digest = prior_source["event_digest"]
        elif sequence == after_sequence + 1:
            previous_source_digest = after_digest
        else:
            previous_source_digest = _hash(
                f"unprojected-source-event:{source_id}:{source_sequence - 1}"
            )

        received_at = observed_at - timedelta(seconds=1)
        record_observed_at = max(received_at, wrapper_not_before)
        event_material = {
            "global_sequence": sequence,
            "event_id": envelope["event_id"],
            "source_id": source_id,
            "source_sequence": source_sequence,
            "signer_key_id": envelope["signer_key_id"],
            "nonce": envelope["nonce"],
            "event_schema": envelope["body_schema"],
            "observed_at": _z(record_observed_at),
            "received_at": _z(received_at),
            "correlation_id": envelope["correlation_id"],
            "causation_id": envelope["causation_id"],
            "payload_digest": envelope["body_digest"],
            "previous_source_digest": previous_source_digest,
            "previous_global_digest": previous_global_digest,
        }
        event_digest = sha256_json(event_material)
        command["event_digest"] = event_digest
        command["ledger_proof"] = {
            "schema": "dumbmoney.ledger-event-proof.v1",
            **event_material,
            "event_digest": event_digest,
        }
        source_heads[source_id] = command
        previous_command = command


def _checkpoint_signature(checkpoint: dict) -> dict:
    signature = CORE_PRIVATE_KEY.sign(
        canonical_json(checkpoint).encode("utf-8")
    )
    return {
        "algorithm": "Ed25519",
        "signer_key_id": CORE_SIGNER_KEY_ID,
        "signature": (
            base64.urlsafe_b64encode(signature)
            .decode("ascii")
            .rstrip("=")
        ),
    }


def _page(
    commands: list[dict],
    *,
    after_sequence: int = 0,
    after_digest: str = ZERO_DIGEST,
    next_sequence: int | None = None,
    next_digest: str | None = None,
    ledger_head_sequence: int | None = None,
    ledger_head_digest: str | None = None,
    required_action: str,
    observed_at: datetime = NOW,
    request_nonce: str = REQUEST_NONCE_1,
) -> bytes:
    _decorate_commands(
        commands,
        after_sequence=after_sequence,
        after_digest=after_digest,
        observed_at=observed_at,
    )
    resolved_next = (
        commands[-1]["global_sequence"]
        if next_sequence is None and commands
        else after_sequence
        if next_sequence is None
        else next_sequence
    )
    if next_digest is not None:
        resolved_digest = next_digest
    elif commands and commands[-1]["global_sequence"] == resolved_next:
        resolved_digest = commands[-1]["event_digest"]
    elif resolved_next == after_sequence:
        resolved_digest = after_digest
    else:
        resolved_digest = _hash(f"ledger-event:{resolved_next}")
    head = resolved_next if ledger_head_sequence is None else ledger_head_sequence
    resolved_head_digest = (
        ledger_head_digest
        if ledger_head_digest is not None
        else resolved_digest
        if head == resolved_next
        else _hash(f"ledger-head:{head}")
    )
    ordered_commands = [
        {
            key: copy.deepcopy(item)
            for key, item in command.items()
            if key != "envelope"
        }
        for command in commands
    ]
    checkpoint = {
        "schema": "dumbmoney.cell-command-checkpoint.v1",
        "cell_id": "dummy_kalshi",
        "request_nonce": request_nonce,
        "after_sequence": after_sequence,
        "after_digest": after_digest,
        "ordered_commands": ordered_commands,
        "next_sequence": resolved_next,
        "next_digest": resolved_digest,
        "ledger_head_sequence": head,
        "ledger_head_digest": resolved_head_digest,
        "observed_at": _z(observed_at),
        "required_action": required_action,
    }
    value = {
        "schema": "dumbmoney.cell-command-page.v1",
        "cell_id": "dummy_kalshi",
        "request_nonce": request_nonce,
        "observed_at": _z(observed_at),
        "after_sequence": after_sequence,
        "after_digest": after_digest,
        "next_sequence": resolved_next,
        "next_digest": resolved_digest,
        "ledger_head_sequence": head,
        "ledger_head_digest": resolved_head_digest,
        "has_more": resolved_next < head,
        "required_action": required_action,
        "commands": commands,
        "checkpoint": checkpoint,
        "checkpoint_signature": _checkpoint_signature(checkpoint),
    }
    return canonical_json(value).encode("utf-8")


class _Transport:
    def __init__(self, responses: list[CommandFeedResponse | Exception]):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, path: str, headers: dict[str, str]) -> CommandFeedResponse:
        self.calls.append((path, dict(headers)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _consumer(
    tmp_path: Path,
    transport: _Transport,
    *,
    kill_events: list | None = None,
    mode_events: list | None = None,
    failures: list | None = None,
    state_journal: AppendOnlyOperationalJournal | None = None,
    capital_adapter: CapitalEnvelopeAdapter | None = None,
    now_fn=None,
    request_nonces: list[str] | None = None,
) -> tuple[
    CoreCommandFeedConsumer,
    AppendOnlyOperationalJournal,
    CapitalEnvelopeAdapter,
    list,
    list,
    list,
]:
    clock = now_fn or (lambda: NOW)
    nonce_values = iter(
        request_nonces
        or [REQUEST_NONCE_1, REQUEST_NONCE_2, REQUEST_NONCE_3]
    )
    state = state_journal or AppendOnlyOperationalJournal(
        tmp_path / "command-feed.jsonl",
        now_fn=clock,
    )
    adapter = capital_adapter or CapitalEnvelopeAdapter(
        journal=AppendOnlyOperationalJournal(
            tmp_path / "capital.jsonl",
            now_fn=lambda: NOW,
        ),
        trusted_public_keys={CORE_SIGNER_KEY_ID: CORE_PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=_UnusedLineageResolver(),
        now_fn=clock,
    )
    kills = [] if kill_events is None else kill_events
    modes = [] if mode_events is None else mode_events
    closed = [] if failures is None else failures
    consumer = CoreCommandFeedConsumer(
        transport=transport,
        cell_token_provider=lambda: "dummy-cell-secret-token",
        state_journal=state,
        trusted_operator_public_keys={
            OPERATOR_SIGNER_KEY_ID: OPERATOR_PUBLIC_KEY
        },
        trusted_checkpoint_public_keys={
            CORE_SIGNER_KEY_ID: CORE_PUBLIC_KEY
        },
        capital_adapter=adapter,
        kill_handler=kills.append,
        mode_handler=modes.append,
        fail_closed_handler=closed.append,
        now_fn=clock,
        request_nonce_fn=lambda: next(nonce_values),
    )
    return consumer, state, adapter, kills, modes, closed


def test_signed_kill_is_delivered_and_restart_uses_durable_cursor(tmp_path):
    kill = _command(_kill(sequence=1, active=True, generation=1), global_sequence=1)
    first_transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page([kill], required_action="CANCEL_AND_RECONCILE"),
            )
        ]
    )
    consumer, state, adapter, kills, _, closed = _consumer(
        tmp_path,
        first_transport,
    )

    first = consumer.poll_once()

    assert first.page_accepted is True
    assert first.cursor_sequence == 1
    assert first.submission_allowed is False
    assert len(kills) == 1
    assert kills[0].body["active"] is True
    assert closed

    next_transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page(
                    [],
                    after_sequence=1,
                    after_digest=kill["event_digest"],
                    required_action="CANCEL_AND_RECONCILE",
                ),
            )
        ]
    )
    restarted, *_ = _consumer(
        tmp_path,
        next_transport,
        state_journal=AppendOnlyOperationalJournal(
            state.path,
            now_fn=lambda: NOW,
        ),
        capital_adapter=adapter,
    )
    second = restarted.poll_once()

    assert second.page_accepted is True
    assert f"after=1&cursor={kill['event_digest']}" in next_transport.calls[0][0]
    assert restarted.snapshot()["kill_envelope"]["body"]["active"] is True


def test_two_consumers_cannot_commit_from_the_same_cursor(tmp_path):
    command = _command(
        _kill(sequence=1, active=True, generation=1),
        global_sequence=1,
    )
    response = CommandFeedResponse(
        200,
        _page([command], required_action="CANCEL_AND_RECONCILE"),
    )
    state_path = tmp_path / "shared-command-feed.jsonl"
    first, *_ = _consumer(
        tmp_path,
        _Transport([response]),
        state_journal=AppendOnlyOperationalJournal(
            state_path,
            now_fn=lambda: NOW,
        ),
    )
    second, *_ = _consumer(
        tmp_path,
        _Transport([response]),
        state_journal=AppendOnlyOperationalJournal(
            state_path,
            now_fn=lambda: NOW,
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda consumer: consumer.poll_once(), [first, second])
        )

    assert sorted(result.page_accepted for result in results) == [False, True]
    restarted = AppendOnlyOperationalJournal(
        state_path,
        now_fn=lambda: NOW,
    )
    states = restarted.events(kind="dumbmoney.command-feed.state")
    assert restarted.healthy is True
    assert len(states) == 2
    assert states[-1]["payload"]["cursor"]["sequence"] == 1
    assert states[-1]["payload"]["status"] == "FAIL_CLOSED"


def test_mode_and_capital_are_dispatched_without_positive_callbacks(tmp_path):
    capital = _command(_capital(sequence=1), global_sequence=1)
    mode = _command(
        _mode(sequence=2, mode="PAUSED", revision=1),
        global_sequence=2,
    )
    inactive_kill = _command(
        _kill(sequence=3, active=False, generation=1),
        global_sequence=3,
    )
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page(
                    [capital, mode, inactive_kill],
                    required_action="PAUSE_NEW_RISK",
                ),
            )
        ]
    )
    consumer, _, adapter, kills, modes, _ = _consumer(tmp_path, transport)

    result = consumer.poll_once()

    assert result.page_accepted is True
    assert result.commands_applied == 3
    assert result.submission_allowed is False
    assert kills == []
    assert [item.body["mode"] for item in modes] == ["PAUSED"]
    accepted = adapter.journal.events(kind="capital.envelope.accepted")
    assert len(accepted) == 1
    assert accepted[0]["payload"]["wrapper"] == capital["envelope"]


def test_current_live_mode_kill_clear_and_capital_create_durable_readiness(
    tmp_path,
):
    commands = [
        _command(_capital(sequence=1), global_sequence=1),
        _command(
            _mode(sequence=2, mode="LIVE", revision=1),
            global_sequence=2,
        ),
        _command(
            _kill(sequence=3, active=False, generation=1),
            global_sequence=3,
        ),
    ]
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page(commands, required_action="APPLY_SIGNED_CONTROLS"),
            )
        ]
    )
    consumer, _, adapter, kills, modes, closed = _consumer(
        tmp_path,
        transport,
    )

    result = consumer.poll_once()

    assert result.page_accepted is True
    assert result.commands_applied == 3
    assert result.submission_allowed is True
    assert consumer.submission_allowed() is True
    assert consumer.snapshot()["status"] == "READY"
    assert len(adapter.journal.events(kind="capital.envelope.accepted")) == 1
    assert kills == []
    assert modes == []
    assert closed == []


def test_expired_kill_clear_cannot_leave_submission_ready(tmp_path):
    clock = [NOW]
    commands = [
        _command(
            _mode(
                sequence=1,
                mode="LIVE",
                revision=1,
                expires_at=NOW + timedelta(minutes=5),
            ),
            global_sequence=1,
        ),
        _command(
            _kill(
                sequence=2,
                active=False,
                generation=1,
                expires_at=NOW + timedelta(seconds=5),
            ),
            global_sequence=2,
        ),
    ]
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page(commands, required_action="APPLY_SIGNED_CONTROLS"),
            )
        ]
    )
    consumer, *_ = _consumer(
        tmp_path,
        transport,
        now_fn=lambda: clock[0],
    )

    assert consumer.poll_once().submission_allowed is True
    clock[0] = NOW + timedelta(seconds=6)

    assert consumer.submission_allowed() is False


def test_positive_controls_expiring_during_get_never_commit_ready(tmp_path):
    clock = [NOW]
    commands = [
        _command(
            _mode(
                sequence=1,
                mode="LIVE",
                revision=1,
                expires_at=NOW + timedelta(seconds=1),
            ),
            global_sequence=1,
        ),
        _command(
            _kill(
                sequence=2,
                active=False,
                generation=1,
                expires_at=NOW + timedelta(seconds=1),
            ),
            global_sequence=2,
        ),
    ]
    response = CommandFeedResponse(
        200,
        _page(commands, required_action="APPLY_SIGNED_CONTROLS"),
    )

    class SlowTransport:
        def __call__(self, path, headers):
            clock[0] = NOW + timedelta(seconds=2)
            return response

    consumer, *_ = _consumer(
        tmp_path,
        SlowTransport(),
        now_fn=lambda: clock[0],
    )

    result = consumer.poll_once()

    assert result.page_accepted is True
    assert result.cursor_sequence == 2
    assert result.submission_allowed is False
    assert consumer.snapshot()["status"] == "FAIL_CLOSED"


@pytest.mark.parametrize(
    "tamper_kind",
    ["unsigned_page_field", "signed_checkpoint", "command_projection"],
)
def test_checkpoint_tampering_never_advances_the_cursor(
    tmp_path,
    tamper_kind,
):
    command = _command(
        _kill(sequence=1, active=True, generation=1),
        global_sequence=1,
    )
    raw_page = _page(
        [command],
        required_action="CANCEL_AND_RECONCILE",
    )
    page = json.loads(raw_page)
    if tamper_kind == "unsigned_page_field":
        page["required_action"] = "PAUSE_NEW_RISK"
    elif tamper_kind == "signed_checkpoint":
        page["checkpoint"]["required_action"] = "PAUSE_NEW_RISK"
    else:
        page["commands"][0]["authority_effect"] = "HISTORICAL_ONLY"
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                canonical_json(page).encode("utf-8"),
            )
        ]
    )
    consumer, _, _, kills, _, closed = _consumer(tmp_path, transport)

    result = consumer.poll_once()

    assert result.page_accepted is False
    assert result.cursor_sequence == 0
    assert kills == []
    assert len(closed) == 1


def test_core_signed_malformed_ledger_proof_is_recomputed_and_rejected(
    tmp_path,
):
    command = _command(
        _kill(sequence=1, active=True, generation=1),
        global_sequence=1,
    )
    page = json.loads(
        _page([command], required_action="CANCEL_AND_RECONCILE")
    )
    replacement = _hash("malformed-payload")
    page["commands"][0]["ledger_proof"]["payload_digest"] = replacement
    page["checkpoint"]["ordered_commands"][0]["ledger_proof"][
        "payload_digest"
    ] = replacement
    page["checkpoint_signature"] = _checkpoint_signature(page["checkpoint"])
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                canonical_json(page).encode("utf-8"),
            )
        ]
    )
    consumer, _, _, kills, _, closed = _consumer(tmp_path, transport)

    result = consumer.poll_once()

    assert result.page_accepted is False
    assert result.cursor_sequence == 0
    assert kills == []
    assert len(closed) == 1


def test_page_replayed_under_a_different_request_nonce_is_rejected(tmp_path):
    command = _command(
        _kill(sequence=1, active=True, generation=1),
        global_sequence=1,
    )
    captured_page = _page(
        [command],
        required_action="CANCEL_AND_RECONCILE",
        request_nonce=REQUEST_NONCE_1,
    )
    transport = _Transport([CommandFeedResponse(200, captured_page)])
    consumer, _, _, kills, _, closed = _consumer(
        tmp_path,
        transport,
        request_nonces=[REQUEST_NONCE_2],
    )

    result = consumer.poll_once()

    assert result.page_accepted is False
    assert result.cursor_sequence == 0
    assert kills == []
    assert f"request_nonce={REQUEST_NONCE_2}" in transport.calls[0][0]
    assert len(closed) == 1


@pytest.mark.parametrize("schema", ["kill", "capital"])
def test_command_signer_roles_are_separate_and_fail_closed(tmp_path, schema):
    if schema == "kill":
        envelope = _kill(
            sequence=1,
            active=True,
            generation=1,
            signer_role="core",
        )
        required_action = "CANCEL_AND_RECONCILE"
    else:
        envelope = _capital(
            sequence=1,
            signer_role="operator",
        )
        required_action = "PAUSE_NEW_RISK"
    command = _command(envelope, global_sequence=1)
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page([command], required_action=required_action),
            )
        ]
    )
    consumer, _, adapter, kills, modes, closed = _consumer(
        tmp_path,
        transport,
    )

    result = consumer.poll_once()

    assert result.page_accepted is False
    assert result.cursor_sequence == 0
    assert kills == []
    assert modes == []
    assert adapter.journal.events(kind="capital.envelope.accepted") == ()
    assert len(closed) == 1


def test_backlog_and_irrelevant_ledger_gap_require_explicit_second_poll(
    tmp_path,
):
    mode = _command(
        _mode(sequence=1, mode="LIVE", revision=1),
        global_sequence=2,
    )
    kill_clear = _command(
        _kill(sequence=2, active=False, generation=1),
        global_sequence=3,
    )
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page(
                    [mode],
                    next_sequence=2,
                    ledger_head_sequence=3,
                    required_action="APPLY_SIGNED_CONTROLS",
                ),
            ),
            CommandFeedResponse(
                200,
                _page(
                    [kill_clear],
                    after_sequence=2,
                    after_digest=mode["event_digest"],
                    required_action="APPLY_SIGNED_CONTROLS",
                    request_nonce=REQUEST_NONCE_2,
                ),
            ),
        ]
    )
    consumer, *_ = _consumer(tmp_path, transport)

    catching_up = consumer.poll_once()
    ready = consumer.poll_once()

    assert catching_up.page_accepted is True
    assert catching_up.cursor_sequence == 2
    assert catching_up.submission_allowed is False
    assert ready.page_accepted is True
    assert ready.cursor_sequence == 3
    assert ready.submission_allowed is True
    assert len(transport.calls) == 2


@pytest.mark.parametrize(
    "failure_kind",
    ["tamper", "digest", "gap", "stale", "future", "unknown"],
)
def test_tamper_gap_and_stale_pages_retain_cursor_and_fail_closed(
    tmp_path,
    failure_kind,
):
    envelope = _kill(sequence=1, active=True, generation=1)
    command = _command(envelope, global_sequence=1)
    if failure_kind == "tamper":
        command["envelope"] = copy.deepcopy(envelope)
        command["envelope"]["body"]["reason"] = "tampered"
        body = _page([command], required_action="CANCEL_AND_RECONCILE")
    elif failure_kind == "digest":
        body = _page(
            [command],
            next_digest=_hash("wrong-ledger-digest"),
            required_action="CANCEL_AND_RECONCILE",
        )
    elif failure_kind == "gap":
        body = _page(
            [],
            next_sequence=251,
            next_digest=_hash("ledger-event:251"),
            ledger_head_sequence=251,
            required_action="PAUSE_NEW_RISK",
        )
    elif failure_kind == "stale":
        body = _page(
            [],
            required_action="PAUSE_NEW_RISK",
            observed_at=NOW - timedelta(minutes=2),
        )
    elif failure_kind == "future":
        body = _page(
            [],
            required_action="PAUSE_NEW_RISK",
            observed_at=NOW + timedelta(seconds=6),
        )
    else:
        command["body_schema"] = "dumbmoney.unknown-command.v1"
        body = _page([command], required_action="CANCEL_AND_RECONCILE")
    transport = _Transport([CommandFeedResponse(200, body)])
    consumer, _, _, kills, _, closed = _consumer(tmp_path, transport)

    result = consumer.poll_once()

    assert result.page_accepted is False
    assert result.cursor_sequence == 0
    assert result.cursor_digest == ZERO_DIGEST
    assert kills == []
    assert len(closed) == 1


@pytest.mark.parametrize(
    "response",
    [
        CommandFeedResponse(401, b"not inspected"),
        RuntimeError("loopback unavailable"),
    ],
)
def test_auth_and_transport_failures_make_one_get_and_never_advance(
    tmp_path,
    response,
):
    transport = _Transport([response])
    consumer, _, _, _, _, closed = _consumer(tmp_path, transport)

    result = consumer.poll_once()

    assert result.page_accepted is False
    assert result.cursor_sequence == 0
    assert len(transport.calls) == 1
    assert transport.calls[0][1] == {
        "Authorization": "Bearer dummy-cell-secret-token"
    }
    assert len(closed) == 1


def test_expired_active_kill_advances_cursor_and_survives_restart_failure(
    tmp_path,
):
    expired = _kill(
        sequence=1,
        active=True,
        generation=4,
        not_before=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(minutes=5),
    )
    command = _command(expired, global_sequence=1)
    expired_clear = _command(
        _kill(
            sequence=2,
            active=False,
            generation=5,
            not_before=NOW - timedelta(minutes=4),
            expires_at=NOW - timedelta(minutes=3),
        ),
        global_sequence=2,
    )
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page([command], required_action="CANCEL_AND_RECONCILE"),
            ),
            CommandFeedResponse(
                200,
                _page(
                    [expired_clear],
                    after_sequence=1,
                    after_digest=command["event_digest"],
                    required_action="CANCEL_AND_RECONCILE",
                    request_nonce=REQUEST_NONCE_2,
                ),
            ),
        ]
    )
    consumer, state, adapter, kills, _, _ = _consumer(tmp_path, transport)

    result = consumer.poll_once()

    assert result.page_accepted is True
    assert result.cursor_sequence == 1
    assert result.commands_applied == 1
    assert len(kills) == 1
    assert consumer.snapshot()["kill_generation_high_water"] == 4
    ignored_clear = consumer.poll_once()
    assert ignored_clear.page_accepted is True
    assert ignored_clear.cursor_sequence == 2
    assert ignored_clear.submission_allowed is False
    assert consumer.snapshot()["kill_generation_high_water"] == 5
    assert consumer.snapshot()["kill_envelope"]["body"]["active"] is True

    failed_transport = _Transport([OSError("offline")])
    restarted, *_ = _consumer(
        tmp_path,
        failed_transport,
        state_journal=AppendOnlyOperationalJournal(
            state.path,
            now_fn=lambda: NOW,
        ),
        capital_adapter=adapter,
    )
    failed = restarted.poll_once()

    assert failed.page_accepted is False
    assert failed.cursor_sequence == 2
    assert restarted.snapshot()["kill_envelope"]["body"]["active"] is True
    assert restarted.submission_allowed() is False


def test_expired_pause_persists_while_live_and_future_capital_never_activate(
    tmp_path,
):
    expired_mode = _mode(
        sequence=1,
        mode="LIVE",
        revision=7,
        not_before=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(minutes=5),
    )
    future_capital = _capital(
        sequence=2,
        fence=9,
        not_before=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=2),
    )
    expired_pause = _mode(
        sequence=3,
        mode="PAUSED",
        revision=8,
        not_before=NOW - timedelta(minutes=8),
        expires_at=NOW - timedelta(minutes=4),
    )
    commands = [
        _command(expired_mode, global_sequence=1),
        _command(future_capital, global_sequence=2),
        _command(expired_pause, global_sequence=3),
    ]
    transport = _Transport(
        [
            CommandFeedResponse(
                200,
                _page(commands, required_action="PAUSE_NEW_RISK"),
            )
        ]
    )
    consumer, _, adapter, _, modes, closed = _consumer(tmp_path, transport)

    result = consumer.poll_once()
    snapshot = consumer.snapshot()

    assert result.page_accepted is True
    assert result.cursor_sequence == 3
    assert result.commands_applied == 1
    assert result.submission_allowed is False
    assert snapshot["desired_mode_envelope"]["body"]["mode"] == "PAUSED"
    assert snapshot["mode_revision_high_water"] == 8
    assert snapshot["capital_fencing_high_water"] == 9
    assert adapter.journal.events(kind="capital.envelope.accepted") == ()
    assert [item.body["mode"] for item in modes] == ["PAUSED"]
    assert closed
