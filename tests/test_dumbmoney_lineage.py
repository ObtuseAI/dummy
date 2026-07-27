from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from live_firewall.dumbmoney_capital import (
    CAPITAL_ENVELOPE_SCHEMA,
    SIGNED_ENVELOPE_SCHEMA,
    verify_signed_capital_envelope,
)
from live_firewall.dumbmoney_lineage import (
    ALPHA_PASSPORT_SCHEMA,
    CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA,
    CONTRACT_RESOLUTION_SCHEMA,
    PROMOTION_CERTIFICATE_SCHEMA,
    ContractResolutionResponse,
    CoreAuthorityContractResolver,
    LineageResolutionError,
)
from live_firewall.operational_journal import canonical_json, sha256_json


NOW = datetime(2026, 7, 26, 22, 30, 0, tzinfo=timezone.utc)
ACCOUNT_HASH = "c" * 64
STRATEGY_HASH = "a" * 64
INSTRUMENT = "event_contract:KXTEST-26JUL"
ZERO_DIGEST = "0" * 64


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sign(
    private_key: Ed25519PrivateKey,
    body: dict,
    *,
    source_id: str,
    source_sequence: int = 1,
    not_before: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(minutes=10),
) -> dict:
    public = private_key.public_key().public_bytes_raw()
    identity = {
        "schema": SIGNED_ENVELOPE_SCHEMA,
        "source_id": source_id,
        "source_sequence": source_sequence,
        "correlation_id": "dummy-lineage-fixture",
        "causation_id": None,
        "nonce": f"{source_id}-nonce-{source_sequence}",
        "not_before": _z(not_before),
        "expires_at": _z(expires_at),
        "body_schema": body["schema"],
        "body_digest": sha256_json(body),
        "body": body,
        "signature_algorithm": "Ed25519",
        "signer_key_id": hashlib.sha256(public).hexdigest(),
    }
    wrapper = {**identity, "event_id": sha256_json(identity)}
    wrapper["signature"] = (
        base64.urlsafe_b64encode(
            private_key.sign(canonical_json(wrapper).encode())
        )
        .decode()
        .rstrip("=")
    )
    return wrapper


def _passport() -> dict:
    return {
        "schema": ALPHA_PASSPORT_SCHEMA,
        "passport_id": "passport-dummy-1",
        "strategy_lineage_id": "lineage-dummy-1",
        "venue": "dummy_kalshi",
        "strategy_hash": STRATEGY_HASH,
        "artifact_hashes": ["1" * 64],
        "evidence_verdict_hashes": ["2" * 64],
        "intended_instruments": [INSTRUMENT],
        "maximum_loss_cents": 100,
        "evidence_class": "FORWARD",
        "created_at": _z(NOW - timedelta(days=1)),
        "expires_at": _z(NOW + timedelta(days=1)),
    }


def _promotion(passport_digest: str, *, policy_epoch: int = 1) -> dict:
    return {
        "schema": PROMOTION_CERTIFICATE_SCHEMA,
        "certificate_id": "promotion-dummy-1",
        "passport_digest": passport_digest,
        "verdict_digests": ["3" * 64],
        "stage": "EXPLORATORY_LIVE",
        "venue": "dummy_kalshi",
        "instruments": [INSTRUMENT],
        "maximum_loss_cents": 100,
        "rollback_triggers": ["AMBIGUOUS_OUTCOME", "KILL_ACTIVE"],
        "policy_epoch": policy_epoch,
        "not_before": _z(NOW - timedelta(days=1)),
        "expires_at": _z(NOW + timedelta(days=1)),
    }


def _capital(passport_digest: str, promotion_digest: str) -> dict:
    return {
        "schema": CAPITAL_ENVELOPE_SCHEMA,
        "envelope_id": "e" * 64,
        "mandate_id": "d" * 64,
        "venue": "dummy_kalshi",
        "account_hash": ACCOUNT_HASH,
        "strategy_hashes": [STRATEGY_HASH],
        "passport_hashes": [passport_digest],
        "promotion_hashes": [promotion_digest],
        "authorized_instruments": [INSTRUMENT],
        "authorized_mode": "LIVE",
        "max_order_risk_cents": 100,
        "max_open_risk_cents": 500,
        "max_correlated_risk_cents": 300,
        "max_daily_loss_cents": 300,
        "max_open_orders": 5,
        "fencing_generation": 7,
        "policy_epoch": 1,
        "not_before": _z(NOW - timedelta(seconds=5)),
        "expires_at": _z(NOW + timedelta(seconds=60)),
    }


def _proof(envelope: dict, *, sequence: int) -> dict:
    received = NOW - timedelta(seconds=1)
    observed = max(
        received,
        datetime.fromisoformat(
            envelope["not_before"].replace("Z", "+00:00")
        ),
    )
    proof = {
        "schema": "dumbmoney.ledger-event-proof.v1",
        "global_sequence": sequence,
        "event_id": envelope["event_id"],
        "source_id": envelope["source_id"],
        "source_sequence": envelope["source_sequence"],
        "signer_key_id": envelope["signer_key_id"],
        "nonce": envelope["nonce"],
        "event_schema": envelope["body_schema"],
        "observed_at": _z(observed),
        "received_at": _z(received),
        "correlation_id": envelope["correlation_id"],
        "causation_id": envelope["causation_id"],
        "payload_digest": envelope["body_digest"],
        "previous_source_digest": ZERO_DIGEST,
        "previous_global_digest": (
            ZERO_DIGEST if sequence == 1 else "9" * 64
        ),
    }
    proof["event_digest"] = sha256_json(
        {
            key: value
            for key, value in proof.items()
            if key != "schema"
        }
    )
    return proof


def _resolution(
    core: Ed25519PrivateKey,
    envelope: dict,
    *,
    nonce: str,
    capital_digest: str,
    sequence: int,
    authority_state: dict,
) -> dict:
    checkpoint = {
        "schema": CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA,
        "cell_id": "dummy_kalshi",
        "request_nonce": nonce,
        "requested_body_digest": envelope["body_digest"],
        "capital_envelope_digest": capital_digest,
        "fencing_generation": 7,
        "observed_at": _z(NOW),
        "contract_schema": envelope["body_schema"],
        "transport_window_current": True,
        "body_window_current": True,
        "eligible_live_input": True,
        "authority_state": authority_state,
        "ledger_proof": _proof(envelope, sequence=sequence),
        "envelope": envelope,
    }
    public = core.public_key().public_bytes_raw()
    signature = core.sign(canonical_json(checkpoint).encode())
    return {
        "schema": CONTRACT_RESOLUTION_SCHEMA,
        **{
            key: value
            for key, value in checkpoint.items()
            if key != "schema"
        },
        "checkpoint": checkpoint,
        "checkpoint_signature": {
            "algorithm": "Ed25519",
            "signer_key_id": hashlib.sha256(public).hexdigest(),
            "signature": base64.urlsafe_b64encode(signature)
            .decode()
            .rstrip("="),
        },
    }


class _Transport:
    def __init__(
        self,
        core: Ed25519PrivateKey,
        capital_digest: str,
        envelopes: dict[str, dict],
        authority_state: dict,
        *,
        mutate=None,
        after_call=None,
        resign_mutation: bool = False,
    ) -> None:
        self.core = core
        self.capital_digest = capital_digest
        self.envelopes = envelopes
        self.authority_state = authority_state
        self.mutate = mutate
        self.after_call = after_call
        self.resign_mutation = resign_mutation
        self.requests: list[tuple[str, dict[str, str]]] = []

    def __call__(self, path: str, headers) -> ContractResolutionResponse:
        self.requests.append((path, dict(headers)))
        parsed = urlsplit(path)
        query = parse_qs(parsed.query)
        assert query["capital_envelope_digest"] == [self.capital_digest]
        digest = parsed.path.rsplit("/", 1)[-1]
        envelope = self.envelopes[digest]
        response = _resolution(
            self.core,
            envelope,
            nonce=query["request_nonce"][0],
            capital_digest=self.capital_digest,
            sequence=(
                1
                if envelope["body_schema"] == ALPHA_PASSPORT_SCHEMA
                else 2
            ),
            authority_state=self.authority_state,
        )
        if self.mutate is not None:
            response = self.mutate(response)
            if self.resign_mutation:
                checkpoint = {
                    "schema": CONTRACT_RESOLUTION_CHECKPOINT_SCHEMA,
                    **{
                        key: value
                        for key, value in response.items()
                        if key
                        not in {
                            "schema",
                            "checkpoint",
                            "checkpoint_signature",
                        }
                    },
                }
                public = self.core.public_key().public_bytes_raw()
                response["checkpoint"] = checkpoint
                response["checkpoint_signature"] = {
                    "algorithm": "Ed25519",
                    "signer_key_id": hashlib.sha256(public).hexdigest(),
                    "signature": base64.urlsafe_b64encode(
                        self.core.sign(canonical_json(checkpoint).encode())
                    )
                    .decode()
                    .rstrip("="),
                }
        if self.after_call is not None:
            self.after_call()
        return ContractResolutionResponse(
            status_code=200,
            body=json.dumps(response, separators=(",", ":")).encode(),
        )


def _runtime(
    *,
    promotion_role: str = "promoter",
    mutate=None,
    clock=None,
    resign_mutation: bool = False,
):
    core = Ed25519PrivateKey.generate()
    research = Ed25519PrivateKey.generate()
    promoter = Ed25519PrivateKey.generate()
    evaluator_integrity = Ed25519PrivateKey.generate()
    evaluator_statistics = Ed25519PrivateKey.generate()
    passport = _sign(research, _passport(), source_id="research")
    promotion_key = research if promotion_role == "research" else promoter
    promotion = _sign(
        promotion_key,
        _promotion(passport["body_digest"]),
        source_id="promoter",
    )
    capital_wrapper = _sign(
        core,
        _capital(passport["body_digest"], promotion["body_digest"]),
        source_id="dumbmoney-core",
        not_before=NOW - timedelta(seconds=5),
        expires_at=NOW + timedelta(seconds=60),
    )
    core_public = core.public_key().public_bytes_raw()
    capital = verify_signed_capital_envelope(
        capital_wrapper,
        trusted_public_keys={
            hashlib.sha256(core_public).hexdigest(): core_public
        },
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        now=NOW,
    )
    capital = replace(
        capital,
        ledger_event_digest="c" * 64,
        ledger_global_sequence=3,
    )
    evaluator_publics = [
        evaluator_integrity.public_key().public_bytes_raw(),
        evaluator_statistics.public_key().public_bytes_raw(),
    ]
    authority_state = {
        "schema": "dumbmoney.cell-authority-state.v1",
        "evaluated_at": _z(NOW),
        "authority_valid_until": _z(NOW + timedelta(seconds=30)),
        "policy_epoch": capital.policy_epoch,
        "mandate_id": capital.body["mandate_id"],
        "mandate_event_digest": "4" * 64,
        "kill_clear": True,
        "kill_generation": 1,
        "kill_event_digest": "5" * 64,
        "desired_mode": "LIVE",
        "desired_mode_revision": 1,
        "desired_mode_event_digest": "6" * 64,
        "capital_envelope_digest": sha256_json(capital.body),
        "capital_event_digest": capital.ledger_event_digest,
        "fencing_generation": capital.fencing_generation,
        "strategy_hash": STRATEGY_HASH,
        "passport_digest": passport["body_digest"],
        "passport_event_digest": _proof(
            passport,
            sequence=1,
        )["event_digest"],
        "promotion_digest": promotion["body_digest"],
        "promotion_event_digest": _proof(
            promotion,
            sequence=2,
        )["event_digest"],
        "verdicts": [
            {
                "verdict_digest": "7" * 64,
                "verdict_event_digest": "8" * 64,
                "verdict_id": "verdict-integrity-1",
                "court": "integrity",
                "decision": "PASS",
                "signer_key_id": hashlib.sha256(
                    evaluator_publics[0]
                ).hexdigest(),
                "evaluated_at": _z(NOW - timedelta(seconds=5)),
                "expires_at": _z(NOW + timedelta(minutes=5)),
                "transport_expires_at": _z(NOW + timedelta(minutes=5)),
            },
            {
                "verdict_digest": "9" * 64,
                "verdict_event_digest": "a" * 64,
                "verdict_id": "verdict-statistics-1",
                "court": "statistics",
                "decision": "PASS",
                "signer_key_id": hashlib.sha256(
                    evaluator_publics[1]
                ).hexdigest(),
                "evaluated_at": _z(NOW - timedelta(seconds=4)),
                "expires_at": _z(NOW + timedelta(minutes=5)),
                "transport_expires_at": _z(NOW + timedelta(minutes=5)),
            },
        ],
        "ledger_head_sequence": 4,
        "ledger_head_digest": "b" * 64,
    }
    transport = _Transport(
        core,
        sha256_json(capital.body),
        {
            passport["body_digest"]: passport,
            promotion["body_digest"]: promotion,
        },
        authority_state,
        mutate=mutate,
        after_call=(
            None if clock is None else clock.get("after_call")
        ),
        resign_mutation=resign_mutation,
    )
    research_public = research.public_key().public_bytes_raw()
    promoter_public = promoter.public_key().public_bytes_raw()
    resolver = CoreAuthorityContractResolver(
        transport=transport,
        cell_token_provider=lambda: "t" * 64,
        trusted_core_public_keys={
            hashlib.sha256(core_public).hexdigest(): core_public
        },
        trusted_research_public_keys={
            hashlib.sha256(research_public).hexdigest(): research_public
        },
        trusted_promoter_public_keys={
            hashlib.sha256(promoter_public).hexdigest(): promoter_public
        },
        trusted_evaluator_public_keys={
            hashlib.sha256(public).hexdigest(): public
            for public in evaluator_publics
        },
        now_fn=(lambda: NOW) if clock is None else clock["now"],
    )
    return resolver, capital, transport


def test_nonce_fence_and_role_bound_lineage_resolves() -> None:
    resolver, capital, transport = _runtime()

    binding = resolver.resolve_lineage(
        capital=capital,
        strategy_hash=STRATEGY_HASH,
        passport_hash=capital.passport_hashes[0],
        promotion_hash=capital.promotion_hashes[0],
        authorized_instrument=INSTRUMENT,
    )

    assert binding.capital_body_digest == sha256_json(capital.body)
    assert binding.capital_fencing_generation == 7
    assert binding.authorized_instrument == INSTRUMENT
    assert len(transport.requests) == 2
    nonces = [
        parse_qs(urlsplit(path).query)["request_nonce"][0]
        for path, _ in transport.requests
    ]
    assert len(set(nonces)) == 2
    assert all(
        headers["Authorization"] == f"Bearer {'t' * 64}"
        for _, headers in transport.requests
    )


def test_wrong_role_promotion_is_rejected() -> None:
    resolver, capital, _ = _runtime(promotion_role="research")

    with pytest.raises(LineageResolutionError, match="signer"):
        resolver.resolve_lineage(
            capital=capital,
            strategy_hash=STRATEGY_HASH,
            passport_hash=capital.passport_hashes[0],
            promotion_hash=capital.promotion_hashes[0],
            authorized_instrument=INSTRUMENT,
        )


def test_unsigned_capital_digest_transplant_is_rejected() -> None:
    def mutate(response: dict) -> dict:
        response["capital_envelope_digest"] = "8" * 64
        return response

    resolver, capital, _ = _runtime(mutate=mutate)

    with pytest.raises(LineageResolutionError, match="checkpoint"):
        resolver.resolve_lineage(
            capital=capital,
            strategy_hash=STRATEGY_HASH,
            passport_hash=capital.passport_hashes[0],
            promotion_hash=capital.promotion_hashes[0],
            authorized_instrument=INSTRUMENT,
        )


def test_slow_transport_cannot_return_expired_resolution() -> None:
    state = {"value": NOW}

    def after_call() -> None:
        state["value"] = NOW + timedelta(minutes=2)

    resolver, capital, _ = _runtime(
        clock={
            "now": lambda: state["value"],
            "after_call": after_call,
        }
    )

    with pytest.raises(LineageResolutionError, match="stale"):
        resolver.resolve_lineage(
            capital=capital,
            strategy_hash=STRATEGY_HASH,
            passport_hash=capital.passport_hashes[0],
            promotion_hash=capital.promotion_hashes[0],
            authorized_instrument=INSTRUMENT,
        )


def test_core_signed_authority_rejects_unsealed_evaluator() -> None:
    def mutate(response: dict) -> dict:
        response["authority_state"]["verdicts"][0][
            "signer_key_id"
        ] = "f" * 64
        return response

    resolver, capital, _ = _runtime(
        mutate=mutate,
        resign_mutation=True,
    )

    with pytest.raises(LineageResolutionError, match="signer is not sealed"):
        resolver.resolve_lineage(
            capital=capital,
            strategy_hash=STRATEGY_HASH,
            passport_hash=capital.passport_hashes[0],
            promotion_hash=capital.promotion_hashes[0],
            authorized_instrument=INSTRUMENT,
        )


def test_passport_and_promotion_require_one_authority_state() -> None:
    calls = 0

    def mutate(response: dict) -> dict:
        nonlocal calls
        calls += 1
        if calls == 2:
            response["authority_state"]["kill_generation"] = 2
        return response

    resolver, capital, _ = _runtime(
        mutate=mutate,
        resign_mutation=True,
    )

    with pytest.raises(LineageResolutionError, match="one authority state"):
        resolver.resolve_lineage(
            capital=capital,
            strategy_hash=STRATEGY_HASH,
            passport_hash=capital.passport_hashes[0],
            promotion_hash=capital.promotion_hashes[0],
            authorized_instrument=INSTRUMENT,
        )


def test_capital_requires_authenticated_core_ledger_event() -> None:
    resolver, capital, _ = _runtime()
    unbound = replace(
        capital,
        ledger_event_digest=None,
        ledger_global_sequence=None,
    )

    with pytest.raises(LineageResolutionError, match="ledger binding"):
        resolver.resolve_lineage(
            capital=unbound,
            strategy_hash=STRATEGY_HASH,
            passport_hash=capital.passport_hashes[0],
            promotion_hash=capital.promotion_hashes[0],
            authorized_instrument=INSTRUMENT,
        )
