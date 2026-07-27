from __future__ import annotations

import base64
import copy
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from autonomy.kill_reconciliation import queue_kill_reconciliation
from autonomy.brain import PredatorBrain
from autonomy.ontology import OutcomeKind, SessionMode, TradeOutcome
from core.ontology import (
    AccountMode,
    CapConfig,
    Forecast,
    FirewallVerdict,
    LiveOrderRequest,
    OrderBook,
    OrderBookLevel,
)
from core.state import DummyState
from live_firewall.dumbmoney_capital import (
    CAPITAL_ENVELOPE_SCHEMA,
    SIGNED_ENVELOPE_SCHEMA,
    CapitalEnvelopeAdapter,
    flat_book_receipt,
    inherited_exposure_receipt,
    strategy_binding_hash,
    verify_signed_capital_envelope,
)
from live_firewall.dumbmoney_broker_witness import (
    SETTLEMENT_WITNESS_SCHEMA,
    TERMINAL_WITNESS_SCHEMA,
    sign_broker_witness,
)
from live_firewall.dumbmoney_reconciliation import (
    DumbMoneyKalshiReconciliationSweeper,
)
from live_firewall.exposure_tracker import ExposureTracker
from live_firewall.firewall import LiveBrokerFirewall
from live_firewall.operational_journal import (
    AppendOnlyOperationalJournal,
    OperationalJournalError,
    canonical_json,
    sha256_json,
)


NOW = datetime(2026, 7, 26, 20, 0, 0, tzinfo=timezone.utc)
ACCOUNT_HASH = hashlib.sha256(b"dummy-kalshi-fixture-account").hexdigest()
STRATEGY_REFERENCE = "autonomy_strategy_v2:test-decision"
PASSPORT_REFERENCE = "autonomy_forecast:test-decision"
STRATEGY_HASH = strategy_binding_hash(STRATEGY_REFERENCE)
PASSPORT_HASH = strategy_binding_hash(PASSPORT_REFERENCE)
PROMOTION_HASH = hashlib.sha256(b"promotion:fixture").hexdigest()
AUTHORIZED_INSTRUMENT = "event_contract:KXTEST-26JUL"
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes_raw()
SIGNER_KEY_ID = hashlib.sha256(PUBLIC_KEY).hexdigest()
WITNESS_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(
    bytes(range(31, -1, -1))
)
WITNESS_PUBLIC_KEY = (
    WITNESS_PRIVATE_KEY.public_key().public_bytes_raw()
)
WITNESS_KEY_ID = hashlib.sha256(WITNESS_PUBLIC_KEY).hexdigest()


class _FixtureLineageResolver:
    def resolve_lineage(
        self,
        *,
        capital,
        strategy_hash,
        passport_hash,
        promotion_hash,
        authorized_instrument,
        expected_binding=None,
    ):
        evidence = {
            "strategy_hash": strategy_hash,
            "passport_hash": passport_hash,
            "promotion_hash": promotion_hash,
            "authorized_instrument": authorized_instrument,
            "maximum_loss_cents": min(
                10_000,
                capital.max_order_risk_cents,
            ),
            "policy_epoch": capital.policy_epoch,
            "capital_envelope_id": capital.envelope_id,
            "capital_event_id": capital.event_id,
            "capital_body_digest": sha256_json(capital.body),
            "capital_fencing_generation": capital.fencing_generation,
            "passport_event_id": _hash(f"passport-event:{passport_hash}"),
            "promotion_event_id": _hash(f"promotion-event:{promotion_hash}"),
            "passport_signer_key_id": _hash("research-key"),
            "promotion_signer_key_id": _hash("promoter-key"),
            "expires_at": _z(capital.expires_at),
            "passport_resolution_sha256": _hash("passport-resolution"),
            "promotion_resolution_sha256": _hash("promotion-resolution"),
        }
        if expected_binding is not None:
            expected = dict(expected_binding)
            expected.pop("passport_resolution_sha256", None)
            expected.pop("promotion_resolution_sha256", None)
            actual = dict(evidence)
            actual.pop("passport_resolution_sha256", None)
            actual.pop("promotion_resolution_sha256", None)
            if expected != actual:
                raise ValueError("fixture lineage binding changed")
        return SimpleNamespace(evidence=lambda: evidence)


LINEAGE_RESOLVER = _FixtureLineageResolver()


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _signed_envelope(
    *,
    source_sequence: int = 1,
    nonce: str = "dummy-nonce-1",
    fencing_generation: int = 1,
    venue: str = "dummy_kalshi",
    account_hash: str = ACCOUNT_HASH,
    not_before: datetime = NOW - timedelta(seconds=10),
    expires_at: datetime = NOW + timedelta(seconds=50),
    max_order_risk_cents: int = 500,
    max_open_risk_cents: int = 1_000,
    max_correlated_risk_cents: int = 750,
    max_daily_loss_cents: int = 300,
    max_open_orders: int = 5,
    policy_epoch: int = 1,
    strategy_hashes: list[str] | None = None,
    passport_hashes: list[str] | None = None,
    promotion_hashes: list[str] | None = None,
    authorized_instruments: list[str] | None = None,
) -> dict:
    body = {
        "schema": CAPITAL_ENVELOPE_SCHEMA,
        "envelope_id": _hash(
            f"envelope:{source_sequence}:{nonce}:{fencing_generation}"
        ),
        "mandate_id": _hash("mandate:fixture"),
        "venue": venue,
        "account_hash": account_hash,
        "strategy_hashes": (
            [STRATEGY_HASH] if strategy_hashes is None else strategy_hashes
        ),
        "passport_hashes": (
            [PASSPORT_HASH] if passport_hashes is None else passport_hashes
        ),
        "promotion_hashes": (
            [PROMOTION_HASH] if promotion_hashes is None else promotion_hashes
        ),
        "authorized_instruments": (
            [AUTHORIZED_INSTRUMENT]
            if authorized_instruments is None
            else authorized_instruments
        ),
        "authorized_mode": "LIVE",
        "max_order_risk_cents": max_order_risk_cents,
        "max_open_risk_cents": max_open_risk_cents,
        "max_correlated_risk_cents": max_correlated_risk_cents,
        "max_daily_loss_cents": max_daily_loss_cents,
        "max_open_orders": max_open_orders,
        "fencing_generation": fencing_generation,
        "policy_epoch": policy_epoch,
        "not_before": _z(not_before),
        "expires_at": _z(expires_at),
    }
    event_material = {
        "schema": SIGNED_ENVELOPE_SCHEMA,
        "source_id": "dumbmoney-core",
        "source_sequence": source_sequence,
        "correlation_id": "dummy-fixture-correlation",
        "causation_id": None,
        "nonce": nonce,
        "not_before": body["not_before"],
        "expires_at": body["expires_at"],
        "body_schema": CAPITAL_ENVELOPE_SCHEMA,
        "body_digest": sha256_json(body),
        "body": body,
        "signature_algorithm": "Ed25519",
        "signer_key_id": SIGNER_KEY_ID,
    }
    wrapper = {
        **event_material,
        "event_id": sha256_json(event_material),
    }
    wrapper["signature"] = (
        base64.urlsafe_b64encode(
            PRIVATE_KEY.sign(canonical_json(wrapper).encode("utf-8"))
        )
        .decode("ascii")
        .rstrip("=")
    )
    return wrapper


def _adapter(
    tmp_path: Path,
    *,
    now: datetime = NOW,
) -> tuple[CapitalEnvelopeAdapter, AppendOnlyOperationalJournal]:
    def clock() -> datetime:
        return now

    journal = AppendOnlyOperationalJournal(
        tmp_path / "operational.jsonl",
        now_fn=clock,
    )
    adapter = CapitalEnvelopeAdapter(
        journal=journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        trusted_broker_witness_public_keys={
            WITNESS_KEY_ID: WITNESS_PUBLIC_KEY
        },
        now_fn=clock,
    )
    return adapter, journal


def _record_flat(adapter: CapitalEnvelopeAdapter) -> None:
    adapter.record_broker_bootstrap(
        flat_book_receipt(
            receipt_id=_hash("flat-receipt"),
            venue="dummy_kalshi",
            account_hash=ACCOUNT_HASH,
            observed_at=_z(NOW),
            broker_snapshot_sha256=_hash("flat-broker-snapshot"),
        )
    )


def _request(
    wrapper: dict,
    *,
    proposal_id: str = "proposal-1",
    market_ticker: str = "KXTEST-26JUL",
    price_cents: int = 50,
    size: int = 1,
) -> LiveOrderRequest:
    return LiveOrderRequest(
        proposal_id=proposal_id,
        market_ticker=market_ticker,
        contract_ticker=market_ticker,
        side="yes",
        price_cents=price_cents,
        size=size,
        strategy_proof_reference=STRATEGY_REFERENCE,
        forecast_proof_reference=PASSPORT_REFERENCE,
        adapter_name="kalshi_live_firewall_adapter",
        expiration_ts=int(
            (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        ),
        capital_envelope_id=wrapper["body"]["envelope_id"],
        capital_strategy_hash=STRATEGY_HASH,
        capital_passport_hash=PASSPORT_HASH,
        capital_promotion_hash=PROMOTION_HASH,
        capital_fencing_generation=wrapper["body"]["fencing_generation"],
    )


def _terminal_witness(
    reservation: dict,
    *,
    fill_count: int = 1,
    terminal_status: str = "executed",
) -> dict:
    fill_ids = ["fill-1"] if fill_count else []
    fill_cost = fill_count * int(reservation["price_cents"])
    fee = 2 if fill_count else 0
    body = {
        "schema": TERMINAL_WITNESS_SCHEMA,
        "witness_id": _hash(
            f"terminal:{reservation['reservation_id']}:{fill_count}"
        ),
        "venue": "dummy_kalshi",
        "account_hash": ACCOUNT_HASH,
        "subaccount_number": 0,
        "reservation_id": reservation["reservation_id"],
        "proposal_id": reservation["proposal_id"],
        "order_id": "broker-order-1",
        "market_ticker": reservation["market_ticker"],
        "contract_ticker": reservation["contract_ticker"],
        "side": reservation["side"],
        "terminal_status": terminal_status,
        "initial_count": reservation["size"],
        "fill_count": fill_count,
        "remaining_count": 0,
        "fill_cost_cents": fill_cost,
        "fee_cents": fee,
        "average_fill_price_cents": (
            int(reservation["price_cents"]) if fill_count else None
        ),
        "fill_ids": fill_ids,
        "observed_at": _z(NOW),
        "broker_projection_sha256": _hash(
            f"terminal-projection:{reservation['reservation_id']}"
        ),
    }
    return sign_broker_witness(
        body,
        private_key=WITNESS_PRIVATE_KEY,
        observed_at=NOW,
        correlation_id=str(reservation["proposal_id"]),
    )


def _settlement_witness(position: dict) -> dict:
    body = {
        "schema": SETTLEMENT_WITNESS_SCHEMA,
        "witness_id": _hash(
            f"settlement:{position['position_exposure_id']}"
        ),
        "venue": "dummy_kalshi",
        "account_hash": ACCOUNT_HASH,
        "subaccount_number": 0,
        "position_exposure_id": position["position_exposure_id"],
        "reservation_id": position["reservation_id"],
        "proposal_id": position["proposal_id"],
        "contract_ticker": position["contract_ticker"],
        "side": position["side"],
        "fill_count": position["fill_count"],
        "market_result": "yes",
        "settled_at": _z(NOW),
        "revenue_cents": 100,
        "settlement_fee_cents": 0,
        "position_absent": True,
        "observed_at": _z(NOW),
        "broker_projection_sha256": _hash(
            f"settlement-projection:{position['position_exposure_id']}"
        ),
    }
    return sign_broker_witness(
        body,
        private_key=WITNESS_PRIVATE_KEY,
        observed_at=NOW,
        correlation_id=str(position["proposal_id"]),
    )


def test_shared_blunder_fixture_verifies_byte_for_byte():
    fixture = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "dumbmoney"
            / "signed-capital-envelope.v1.json"
        ).read_text(encoding="utf-8")
    )
    wrapper = fixture["envelope"]
    public_key = base64.urlsafe_b64decode(
        fixture["public_key_base64url"]
        + "=" * (-len(fixture["public_key_base64url"]) % 4)
    )
    signed_material = {
        key: value for key, value in wrapper.items() if key != "signature"
    }
    assert hashlib.sha256(
        canonical_json(signed_material).encode("utf-8")
    ).hexdigest() == fixture["signing_payload_sha256"]

    verified = verify_signed_capital_envelope(
        wrapper,
        trusted_public_keys={wrapper["signer_key_id"]: public_key},
        expected_venue="dopey_robinhood",
        expected_account_hash=wrapper["body"]["account_hash"],
        now=datetime(2099, 1, 1, 0, 0, 30, tzinfo=timezone.utc),
    )

    assert verified.event_id == wrapper["event_id"]
    assert verified.envelope_id == wrapper["body"]["envelope_id"]
    assert verified.fencing_generation == 7
    assert verified.promotion_hashes == ("f" * 64,)
    assert verified.authorized_instruments == ("equity:ACME",)


def test_expired_envelope_and_bad_signature_fail_closed():
    wrapper = _signed_envelope()
    with pytest.raises(ValueError, match="expired"):
        verify_signed_capital_envelope(
            wrapper,
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            now=NOW + timedelta(minutes=2),
        )

    tampered = copy.deepcopy(wrapper)
    tampered["signature"] = (
        ("A" if wrapper["signature"][0] != "A" else "B")
        + wrapper["signature"][1:]
    )
    with pytest.raises(ValueError, match="signature invalid"):
        verify_signed_capital_envelope(
            tampered,
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            now=NOW,
        )


@pytest.mark.parametrize(
    ("venue", "account_hash", "message"),
    [
        ("dopey_robinhood", ACCOUNT_HASH, "venue mismatch"),
        ("dummy_kalshi", _hash("wrong-account"), "account mismatch"),
    ],
)
def test_signed_envelope_is_bound_to_exact_venue_and_account(
    venue,
    account_hash,
    message,
):
    wrapper = _signed_envelope(venue=venue, account_hash=account_hash)
    with pytest.raises(ValueError, match=message):
        verify_signed_capital_envelope(
            wrapper,
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            now=NOW,
        )


def test_capital_envelope_requires_complete_lineage_and_ordered_limits():
    mismatched_lineage = _signed_envelope(
        promotion_hashes=sorted(
            [PROMOTION_HASH, _hash("promotion:extra")]
        )
    )
    with pytest.raises(ValueError, match="hash counts must match"):
        verify_signed_capital_envelope(
            mismatched_lineage,
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            now=NOW,
        )

    multiple_lineages = _signed_envelope(
        strategy_hashes=sorted([STRATEGY_HASH, _hash("strategy:extra")]),
        passport_hashes=sorted([PASSPORT_HASH, _hash("passport:extra")]),
        promotion_hashes=sorted(
            [PROMOTION_HASH, _hash("promotion:extra")]
        ),
    )
    with pytest.raises(ValueError, match="exactly one"):
        verify_signed_capital_envelope(
            multiple_lineages,
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            now=NOW,
        )

    bad_limit_order = _signed_envelope(
        max_order_risk_cents=500,
        max_correlated_risk_cents=499,
    )
    with pytest.raises(ValueError, match="internally inconsistent"):
        verify_signed_capital_envelope(
            bad_limit_order,
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            now=NOW,
        )


def test_exact_instrument_and_promotion_are_rechecked_at_sink(tmp_path):
    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)

    unauthorized_instrument = _request(
        wrapper,
        market_ticker="KXOTHER-26JUL",
    )
    instrument_verdict = adapter.evaluate_request(
        unauthorized_instrument,
        current_daily_loss_cents=0,
    )
    assert instrument_verdict.allow is False
    assert "instrument is not authorized" in instrument_verdict.reason

    wrong_promotion = _request(wrapper).model_copy(
        update={"capital_promotion_hash": _hash("wrong-promotion")}
    )
    promotion_verdict = adapter.evaluate_request(
        wrong_promotion,
        current_daily_loss_cents=0,
    )
    assert promotion_verdict.allow is False
    assert "promotion hash mismatch" in promotion_verdict.reason


def test_replay_sequence_nonce_and_fencing_are_fail_closed(tmp_path):
    adapter, journal = _adapter(tmp_path)
    first = _signed_envelope()
    adapter.accept_signed_envelope(first)
    adapter.accept_signed_envelope(first)
    assert len(journal.events(kind="capital.envelope.accepted")) == 1

    with pytest.raises(ValueError, match="nonce replay"):
        adapter.accept_signed_envelope(
            _signed_envelope(source_sequence=2, nonce="dummy-nonce-1")
        )
    with pytest.raises(ValueError, match="source sequence replay"):
        adapter.accept_signed_envelope(
            _signed_envelope(source_sequence=1, nonce="dummy-nonce-2")
        )

    newest = _signed_envelope(
        source_sequence=2,
        nonce="dummy-nonce-2",
        fencing_generation=9,
    )
    adapter.accept_signed_envelope(newest)
    with pytest.raises(ValueError, match="not strictly increasing"):
        adapter.accept_signed_envelope(
            _signed_envelope(
                source_sequence=3,
                nonce="dummy-nonce-3",
                fencing_generation=8,
            )
        )

    _record_flat(adapter)
    stale = adapter.evaluate_request(first_request := _request(first), current_daily_loss_cents=0)
    assert first_request.capital_fencing_generation == 1
    assert stale.allow is False
    assert "stale" in stale.reason


def test_equal_fence_split_brain_is_rejected(tmp_path):
    adapter, _ = _adapter(tmp_path)
    adapter.accept_signed_envelope(
        _signed_envelope(
            source_sequence=1,
            nonce="equal-fence-a",
            fencing_generation=4,
        )
    )

    with pytest.raises(ValueError, match="not strictly increasing"):
        adapter.accept_signed_envelope(
            _signed_envelope(
                source_sequence=2,
                nonce="equal-fence-b",
                fencing_generation=4,
            )
        )


def test_two_adapters_cannot_accept_conflicting_equal_fences(tmp_path):
    path = tmp_path / "shared-capital.jsonl"
    first_journal = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    second_journal = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    first_adapter = CapitalEnvelopeAdapter(
        journal=first_journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    second_adapter = CapitalEnvelopeAdapter(
        journal=second_journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    first = _signed_envelope(
        source_sequence=1,
        nonce="concurrent-fence-a",
        fencing_generation=1,
    )
    second = _signed_envelope(
        source_sequence=2,
        nonce="concurrent-fence-b",
        fencing_generation=1,
    )
    barrier = threading.Barrier(3)

    def attempt(adapter, envelope):
        barrier.wait()
        try:
            adapter.accept_signed_envelope(envelope)
        except ValueError:
            return "rejected"
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, first_adapter, first),
            executor.submit(attempt, second_adapter, second),
        ]
        barrier.wait()
        outcomes = [future.result() for future in futures]

    assert sorted(outcomes) == ["accepted", "rejected"]
    restarted = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    accepted = restarted.events(kind="capital.envelope.accepted")
    assert restarted.healthy is True
    assert len(accepted) == 1
    assert [row["payload"]["fencing_generation"] for row in accepted] == [1]


def test_policy_epoch_cannot_regress_under_a_higher_fence(tmp_path):
    adapter, _ = _adapter(tmp_path)
    adapter.accept_signed_envelope(
        _signed_envelope(
            source_sequence=1,
            nonce="policy-two",
            fencing_generation=1,
            policy_epoch=2,
        )
    )

    with pytest.raises(ValueError, match="policy epoch regressed"):
        adapter.accept_signed_envelope(
            _signed_envelope(
                source_sequence=2,
                nonce="policy-one",
                fencing_generation=2,
                policy_epoch=1,
            )
        )


def test_expired_newer_fence_never_resurrects_older_grant(tmp_path):
    clock_state = {"now": NOW}

    def clock() -> datetime:
        return clock_state["now"]

    journal = AppendOnlyOperationalJournal(
        tmp_path / "operational.jsonl",
        now_fn=clock,
    )
    adapter = CapitalEnvelopeAdapter(
        journal=journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=clock,
    )
    older = _signed_envelope(
        source_sequence=1,
        nonce="older-fence",
        fencing_generation=1,
        expires_at=NOW + timedelta(seconds=50),
    )
    newer = _signed_envelope(
        source_sequence=2,
        nonce="newer-fence",
        fencing_generation=2,
        expires_at=NOW + timedelta(seconds=20),
    )
    adapter.accept_signed_envelope(older)
    adapter.accept_signed_envelope(newer)
    _record_flat(adapter)
    clock_state["now"] = NOW + timedelta(seconds=30)

    with pytest.raises(ValueError, match="no active capital envelope"):
        adapter.binding_for(
            strategy_hash=STRATEGY_HASH,
            passport_hash=PASSPORT_HASH,
            authorized_instrument=AUTHORIZED_INSTRUMENT,
        )
    stale = adapter.evaluate_request(
        _request(older),
        current_daily_loss_cents=0,
    )
    assert stale.allow is False
    assert "stale" in stale.reason


def test_missing_local_exposure_is_never_treated_as_flat(tmp_path):
    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)

    verdict = adapter.evaluate_request(
        _request(wrapper),
        current_daily_loss_cents=0,
    )

    assert verdict.allow is False
    assert verdict.rejected_by == "capital_broker_bootstrap"
    assert "local absence is not flat" in verdict.reason


def test_daily_loss_capacity_charges_proposed_order_at_exact_boundary(tmp_path):
    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope(max_daily_loss_cents=300)
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper, price_cents=100)

    exact = adapter.evaluate_request(
        request,
        current_daily_loss_cents=200,
    )
    over = adapter.evaluate_request(
        request,
        current_daily_loss_cents=201,
    )

    assert exact.allow is True
    assert over.allow is False
    assert "daily loss capacity" in over.reason


def test_broker_bootstrap_cannot_replay_an_older_snapshot(tmp_path):
    adapter, journal = _adapter(tmp_path)
    current = flat_book_receipt(
        receipt_id=_hash("bootstrap-current"),
        venue="dummy_kalshi",
        account_hash=ACCOUNT_HASH,
        observed_at=_z(NOW),
        broker_snapshot_sha256=_hash("bootstrap-current-snapshot"),
    )
    first = adapter.record_broker_bootstrap(current)
    repeated = adapter.record_broker_bootstrap(current)
    assert repeated["event_sha256"] == first["event_sha256"]

    older = flat_book_receipt(
        receipt_id=_hash("bootstrap-older"),
        venue="dummy_kalshi",
        account_hash=ACCOUNT_HASH,
        observed_at=_z(NOW - timedelta(seconds=1)),
        broker_snapshot_sha256=_hash("bootstrap-older-snapshot"),
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        adapter.record_broker_bootstrap(older)
    assert len(journal.events(kind="broker.bootstrap.recorded")) == 1


def test_two_adapters_cannot_record_conflicting_bootstrap_observations(
    tmp_path,
):
    path = tmp_path / "shared-bootstrap.jsonl"
    adapters = [
        CapitalEnvelopeAdapter(
            journal=AppendOnlyOperationalJournal(
                path,
                now_fn=lambda: NOW,
            ),
            trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
            expected_venue="dummy_kalshi",
            expected_account_hash=ACCOUNT_HASH,
            lineage_resolver=LINEAGE_RESOLVER,
            now_fn=lambda: NOW,
        )
        for _ in range(2)
    ]
    receipts = [
        flat_book_receipt(
            receipt_id=_hash(f"concurrent-bootstrap:{index}"),
            venue="dummy_kalshi",
            account_hash=ACCOUNT_HASH,
            observed_at=_z(NOW),
            broker_snapshot_sha256=_hash(
                f"concurrent-bootstrap-snapshot:{index}"
            ),
        )
        for index in range(2)
    ]
    barrier = threading.Barrier(3)

    def attempt(adapter, receipt):
        barrier.wait()
        try:
            adapter.record_broker_bootstrap(receipt)
        except ValueError:
            return "rejected"
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, adapter, receipt)
            for adapter, receipt in zip(adapters, receipts, strict=True)
        ]
        barrier.wait()
        outcomes = [future.result() for future in futures]

    assert sorted(outcomes) == ["accepted", "rejected"]
    restarted = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    assert restarted.healthy is True
    assert len(restarted.events(kind="broker.bootstrap.recorded")) == 1


def test_inherited_broker_exposure_consumes_grant_before_new_risk(tmp_path):
    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope(
        max_order_risk_cents=100,
        max_open_risk_cents=100,
        max_correlated_risk_cents=100,
    )
    adapter.accept_signed_envelope(wrapper)
    adapter.record_broker_bootstrap(
        inherited_exposure_receipt(
            receipt_id=_hash("inherited-receipt"),
            venue="dummy_kalshi",
            account_hash=ACCOUNT_HASH,
            observed_at=_z(NOW),
            broker_snapshot_sha256=_hash("inherited-snapshot"),
            total_exposure_cents=80,
            open_order_count=1,
            market_exposure_cents={"KXTEST-26JUL": 80},
            correlated_exposure_cents={"KXTEST": 80},
        )
    )

    verdict = adapter.evaluate_request(
        _request(wrapper, price_cents=30),
        current_daily_loss_cents=0,
    )

    assert verdict.allow is False
    assert verdict.rejected_by == "capital_limits"
    assert "open risk" in verdict.reason


def test_post_bootstrap_fill_cannot_hide_behind_inherited_exposure(tmp_path):
    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope(
        max_order_risk_cents=100,
        max_open_risk_cents=100,
        max_correlated_risk_cents=100,
    )
    adapter.accept_signed_envelope(wrapper)
    adapter.record_broker_bootstrap(
        inherited_exposure_receipt(
            receipt_id=_hash("inherited-plus-fill-receipt"),
            venue="dummy_kalshi",
            account_hash=ACCOUNT_HASH,
            observed_at=_z(NOW),
            broker_snapshot_sha256=_hash("inherited-plus-fill-snapshot"),
            total_exposure_cents=80,
            open_order_count=1,
            market_exposure_cents={"KXTEST-26JUL": 80},
            correlated_exposure_cents={"KXTEST": 80},
        )
    )

    verdict = adapter.reserve_request(
        _request(wrapper, price_cents=20),
        current_daily_loss_cents=0,
        current_local_total_exposure_cents=10,
        current_local_correlated_exposure_cents=10,
    )

    assert verdict.allow is False
    assert verdict.rejected_by == "capital_limits"
    assert "open risk" in verdict.reason


def test_reservation_is_crash_safe_and_idempotent(tmp_path):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)

    first = adapter.reserve_request(request, current_daily_loss_cents=0)
    assert first.allow is True
    assert first.reservation_id

    reloaded_journal = AppendOnlyOperationalJournal(
        journal.path,
        now_fn=lambda: NOW,
    )
    reloaded = CapitalEnvelopeAdapter(
        journal=reloaded_journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    second = reloaded.reserve_request(request, current_daily_loss_cents=0)

    assert second.allow is True
    assert second.reservation_id == first.reservation_id
    assert (
        len(reloaded_journal.events(kind="capital.reservation.created")) == 1
    )
    conflict = reloaded.reserve_request(
        _request(wrapper, size=2),
        current_daily_loss_cents=0,
    )
    assert conflict.allow is False
    assert conflict.rejected_by == "capital_idempotency"


def test_two_adapters_cannot_overreserve_same_capital_ceiling(tmp_path):
    first_adapter, first_journal = _adapter(tmp_path)
    wrapper = _signed_envelope(
        max_order_risk_cents=617,
        max_open_risk_cents=1_000,
        max_correlated_risk_cents=1_000,
        max_daily_loss_cents=2_000,
        max_open_orders=5,
    )
    first_adapter.accept_signed_envelope(wrapper)
    _record_flat(first_adapter)
    second_adapter = CapitalEnvelopeAdapter(
        journal=AppendOnlyOperationalJournal(
            first_journal.path,
            now_fn=lambda: NOW,
        ),
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    first_request = _request(
        wrapper,
        proposal_id="concurrent-proposal-a",
        price_cents=60,
        size=10,
    )
    second_request = _request(
        wrapper,
        proposal_id="concurrent-proposal-b",
        price_cents=60,
        size=10,
    )
    barrier = threading.Barrier(2)
    first_verdict = first_adapter._verdict
    second_verdict = second_adapter._verdict

    def gated_first(*args, **kwargs):
        result = first_verdict(*args, **kwargs)
        barrier.wait(timeout=5)
        return result

    def gated_second(*args, **kwargs):
        result = second_verdict(*args, **kwargs)
        barrier.wait(timeout=5)
        return result

    first_adapter._verdict = gated_first
    second_adapter._verdict = gated_second
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                first_adapter.reserve_request,
                first_request,
                current_daily_loss_cents=0,
            ),
            executor.submit(
                second_adapter.reserve_request,
                second_request,
                current_daily_loss_cents=0,
            ),
        ]
        verdicts = [future.result() for future in futures]

    assert sorted(verdict.allow for verdict in verdicts) == [False, True]
    restarted = AppendOnlyOperationalJournal(
        first_journal.path,
        now_fn=lambda: NOW,
    )
    reservations = restarted.events(kind="capital.reservation.created")
    assert restarted.healthy is True
    assert len(reservations) == 1
    assert sum(int(row["payload"]["risk_cents"]) for row in reservations) == 617


def test_cross_process_dispatch_claim_is_one_shot(tmp_path):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    reservation = adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reservation.reservation_id
    order = {
        "ticker": request.contract_ticker,
        "client_order_id": request.proposal_id,
        "side": "bid",
        "count": "1.00",
        "price": "0.5000",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "taker_at_cross",
        "post_only": True,
        "cancel_order_on_pause": True,
        "reduce_only": False,
        "subaccount": 0,
        "exchange_index": 0,
        "expiration_time": request.expiration_ts,
    }
    second_journal = AppendOnlyOperationalJournal(
        journal.path,
        now_fn=lambda: NOW,
    )
    second_adapter = CapitalEnvelopeAdapter(
        journal=second_journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    barrier = threading.Barrier(2)

    def claim(
        candidate: CapitalEnvelopeAdapter,
        nonce: str,
    ):
        barrier.wait(timeout=5)
        try:
            return candidate.claim_broker_dispatch(
                request,
                reservation_id=reservation.reservation_id,
                order=order,
                claimant_nonce=nonce,
            )
        except (ValueError, OperationalJournalError) as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            future.result()
            for future in (
                executor.submit(claim, adapter, "1" * 64),
                executor.submit(claim, second_adapter, "2" * 64),
            )
        ]

    successes = [
        result
        for result in results
        if isinstance(result, dict)
    ]
    failures = [
        result
        for result in results
        if isinstance(result, (ValueError, OperationalJournalError))
    ]
    assert len(successes) == 1
    assert successes[0]["kind"] == "capital.dispatch.claimed"
    assert len(failures) == 1
    assert "already" in str(failures[0]) or "claimed" in str(failures[0])
    assert len(
        second_journal.events(kind="capital.dispatch.claimed")
    ) == 1
    assert len(journal.events(kind="capital.dispatch.claimed")) == 1
    with pytest.raises(ValueError, match="disabled pending sealed CAS proof"):
        adapter.release_after_local_reservation_failure(
            request,
            reservation_id=reservation.reservation_id,
            reason="caller claims transport did not occur",
        )
    assert not journal.events(kind="capital.reservation.released")


def test_dispatch_claim_rejects_payload_drift_and_cancel_only(tmp_path):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    reservation = adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reservation.reservation_id
    order = {
        "ticker": request.contract_ticker,
        "client_order_id": request.proposal_id,
        "side": "bid",
        "count": "1.00",
        "price": "0.5100",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "taker_at_cross",
        "post_only": True,
        "cancel_order_on_pause": True,
        "reduce_only": False,
        "subaccount": 0,
        "exchange_index": 0,
        "expiration_time": request.expiration_ts,
    }
    with pytest.raises(ValueError, match="exact authorized wire payload"):
        adapter.claim_broker_dispatch(
            request,
            reservation_id=reservation.reservation_id,
            order=order,
            claimant_nonce="3" * 64,
        )

    order["price"] = "0.5000"
    adapter.enter_cancel_only(
        reason="operator kill",
        kill_asserted_at=_z(NOW),
    )
    with pytest.raises(ValueError, match="cancel-only"):
        adapter.claim_broker_dispatch(
            request,
            reservation_id=reservation.reservation_id,
            order=order,
            claimant_nonce="4" * 64,
        )
    assert len(journal.events(kind="capital.dispatch.claimed")) == 0


def test_existing_reservation_rechecks_new_broker_exposure(tmp_path):
    adapter, _journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    reservation = adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reservation.allow is True
    adapter.record_broker_bootstrap(
        inherited_exposure_receipt(
            receipt_id=_hash("new-inherited-receipt"),
            venue="dummy_kalshi",
            account_hash=ACCOUNT_HASH,
            observed_at=_z(NOW + timedelta(seconds=1)),
            broker_snapshot_sha256=_hash("new-inherited-snapshot"),
            total_exposure_cents=980,
            open_order_count=1,
            market_exposure_cents={request.market_ticker: 980},
            correlated_exposure_cents={"KXTEST": 980},
        )
    )

    verdict = adapter.evaluate_request(
        request,
        current_daily_loss_cents=0,
        current_local_total_exposure_cents=52,
        current_local_correlated_exposure_cents=52,
        current_local_open_orders=1,
        current_request_locally_reserved=True,
    )

    assert verdict.allow is False
    assert verdict.rejected_by == "capital_limits"
    assert verdict.reason == "DumbMoney maximum open risk exceeded"


@pytest.mark.asyncio
async def test_local_exposure_failure_retains_capital_without_broker_contact(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    tracker = ExposureTracker()
    tracker.reserve_order_submission = Mock(return_value=False)
    client = SimpleNamespace(create_order=AsyncMock())
    firewall = LiveBrokerFirewall(
        client,
        tracker,
        capital_envelope_adapter=adapter,
    )
    allow = FirewallVerdict(allow=True, reason="fixture")
    firewall.evaluate = AsyncMock(return_value=allow)
    firewall._mandatory_submit_authority = Mock(return_value=allow)
    firewall._verified_live_compliance_verdict = AsyncMock(return_value=allow)
    firewall._trusted_sink_orderbook = AsyncMock(
        return_value=(SimpleNamespace(), allow)
    )

    result = await firewall.submit(request, SimpleNamespace(), None)

    assert result.success is False
    assert result.error == "EXPOSURE_RESERVATION_FAILED"
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()
    releases = journal.events(kind="capital.reservation.released")
    assert len(journal.events(kind="capital.reservation.created")) == 1
    assert not journal.events(kind="capital.local_reservation.failed")
    assert releases == ()
    reused = adapter.evaluate_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reused.allow is True
    assert reused.reservation_id is not None


@pytest.mark.asyncio
async def test_authority_loss_after_reservation_never_contacts_broker(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    tracker = ExposureTracker()
    client = SimpleNamespace(create_order=AsyncMock())
    firewall = LiveBrokerFirewall(
        client,
        tracker,
        capital_envelope_adapter=adapter,
    )
    allow = FirewallVerdict(allow=True, reason="fixture")
    revoked = FirewallVerdict(
        allow=False,
        reason="Kill switch active",
        rejected_by="kill_switch",
    )
    firewall.evaluate = AsyncMock(return_value=allow)
    firewall._mandatory_submit_authority = Mock(
        side_effect=[allow, allow, revoked]
    )
    firewall._verified_live_compliance_verdict = AsyncMock(
        return_value=allow
    )
    firewall._trusted_sink_orderbook = AsyncMock(
        return_value=(SimpleNamespace(), allow)
    )

    result = await firewall.submit(request, SimpleNamespace(), None)

    assert result.success is False
    assert result.error == "Kill switch active"
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()
    assert len(journal.events(kind="capital.reservation.created")) == 1
    assert journal.events(kind="capital.reservation.released") == ()
    assert tracker.open_order_count() == 1


@pytest.mark.asyncio
async def test_authority_loss_after_dispatch_claim_never_contacts_broker(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    tracker = ExposureTracker()
    client = SimpleNamespace(create_order=AsyncMock())
    firewall = LiveBrokerFirewall(
        client,
        tracker,
        capital_envelope_adapter=adapter,
    )
    allow = FirewallVerdict(allow=True, reason="fixture")
    revoked = FirewallVerdict(
        allow=False,
        reason="Core command authority expired",
        rejected_by="core_command_authority",
    )
    firewall.evaluate = AsyncMock(return_value=allow)
    firewall._mandatory_submit_authority = Mock(
        side_effect=[allow, allow, allow, revoked]
    )
    firewall._verified_live_compliance_verdict = AsyncMock(
        return_value=allow
    )
    firewall._trusted_sink_orderbook = AsyncMock(
        return_value=(SimpleNamespace(), allow)
    )

    result = await firewall.submit(request, SimpleNamespace(), None)

    assert result.success is False
    assert result.error == "Core command authority expired"
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()
    assert len(journal.events(kind="capital.dispatch.claimed")) == 1
    assert len(journal.events(kind="capital.reservation.created")) == 1
    assert journal.events(kind="capital.reservation.released") == ()
    assert tracker.open_order_count() == 1


@pytest.mark.asyncio
async def test_existing_ambiguous_submission_is_reconciliation_only(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    capital = adapter.reserve_request(request, current_daily_loss_cents=0)
    assert capital.allow is True
    tracker = ExposureTracker()
    assert tracker.reserve_order_submission(
        request.proposal_id,
        request.market_ticker,
        request.size,
        request.price_cents,
        contract_ticker=request.contract_ticker,
        side=request.side,
    )
    client = SimpleNamespace(create_order=AsyncMock())
    firewall = LiveBrokerFirewall(
        client,
        tracker,
        capital_envelope_adapter=adapter,
    )
    allow = FirewallVerdict(allow=True, reason="fixture")
    firewall.evaluate = AsyncMock(return_value=allow)
    firewall._mandatory_submit_authority = Mock(return_value=allow)
    firewall._verified_live_compliance_verdict = AsyncMock(
        return_value=allow
    )
    firewall._trusted_sink_orderbook = AsyncMock(
        return_value=(SimpleNamespace(), allow)
    )

    result = await firewall.submit(request, SimpleNamespace(), None)

    assert result.success is False
    assert (
        result.error
        == "EXISTING_SUBMISSION_REQUIRES_BROKER_RECONCILIATION"
    )
    assert result.broker_contacted is False
    client.create_order.assert_not_awaited()
    assert journal.events(kind="capital.reservation.released") == ()
    assert tracker.submission_record(request.proposal_id) is not None
    assert tracker.state_healthy is True


def test_fee_inclusive_reservation_records_notional_and_worst_case_fee(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)

    verdict = adapter.reserve_request(
        _request(wrapper, price_cents=50, size=2),
        current_daily_loss_cents=0,
    )

    assert verdict.allow is True
    payload = journal.events(
        kind="capital.reservation.created"
    )[0]["payload"]
    assert payload["notional_cents"] == 100
    assert payload["fee_reserve_cents"] == 4
    assert payload["risk_cents"] == 104


def test_signed_terminal_and_settlement_witnesses_release_in_order(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope(
        max_order_risk_cents=100,
        max_open_risk_cents=100,
        max_correlated_risk_cents=100,
    )
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    reservation = adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reservation.reservation_id is not None
    adapter.claim_broker_dispatch(
        request,
        reservation_id=reservation.reservation_id,
        order=adapter._expected_broker_order(request),
        claimant_nonce="9" * 64,
    )
    pending = adapter.pending_reconciliation_reservations()
    assert len(pending) == 1
    terminal_wrapper = _terminal_witness(pending[0])
    tracker = ExposureTracker(
        persist=True,
        state_path=tmp_path / "live-exposure.json",
    )
    assert tracker.reserve_order_submission(
        request.proposal_id,
        request.market_ticker,
        request.size,
        request.price_cents,
        contract_ticker=request.contract_ticker,
        side=request.side,
    )
    assert tracker.confirm_open_order(
        request.proposal_id,
        "broker-order-1",
    )

    class Reader:
        settlement: dict | None = None

        def terminal_reconciliation_witness(self, _reservation):
            return terminal_wrapper

        def settlement_reconciliation_witness(self, _position):
            return self.settlement

    reader = Reader()
    sweeper = DumbMoneyKalshiReconciliationSweeper(
        capital_adapter=adapter,
        broker_reader=reader,
        exposure_tracker=tracker,
    )

    first = sweeper.run_once()

    assert first["status"] == "BLOCKED"
    assert first["terminal_witnesses_recorded"] == 1
    assert first["unresolved_positions"] == 1
    assert adapter.pending_reconciliation_reservations() == ()
    positions = adapter.active_position_exposures()
    assert len(positions) == 1
    assert positions[0]["risk_cents"] == 52
    assert tracker.open_order_count() == 0
    assert tracker.positions[
        (request.contract_ticker, request.side)
    ].quantity == 1
    blocked = adapter.evaluate_request(
        _request(wrapper, proposal_id="proposal-after-fill"),
        current_daily_loss_cents=0,
    )
    assert blocked.allow is False
    assert blocked.reason == "DumbMoney maximum open risk exceeded"

    reader.settlement = _settlement_witness(positions[0])
    second = sweeper.run_once()

    assert second["status"] == "COMPLETE"
    assert second["settlement_witnesses_recorded"] == 1
    assert adapter.active_position_exposures() == ()
    assert tracker.positions == {}
    allowed = adapter.evaluate_request(
        _request(wrapper, proposal_id="proposal-after-settlement"),
        current_daily_loss_cents=0,
    )
    assert allowed.allow is True
    assert len(
        journal.events(
            kind="capital.terminal_reconciliation.witnessed"
        )
    ) == 1
    assert len(
        journal.events(
            kind="capital.settlement_reconciliation.witnessed"
        )
    ) == 1

    # A restart sees no pending authority and does not duplicate releases.
    restarted_journal = AppendOnlyOperationalJournal(
        journal.path,
        now_fn=lambda: NOW,
    )
    restarted = CapitalEnvelopeAdapter(
        journal=restarted_journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        trusted_broker_witness_public_keys={
            WITNESS_KEY_ID: WITNESS_PUBLIC_KEY
        },
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    assert restarted.pending_reconciliation_reservations() == ()
    assert restarted.active_position_exposures() == ()


def test_terminal_witness_tamper_or_wrong_signer_never_releases(
    tmp_path,
):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    reservation = adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reservation.reservation_id is not None
    adapter.claim_broker_dispatch(
        request,
        reservation_id=reservation.reservation_id,
        order=adapter._expected_broker_order(request),
        claimant_nonce="8" * 64,
    )
    terminal = _terminal_witness(
        adapter.pending_reconciliation_reservations()[0]
    )
    tampered = copy.deepcopy(terminal)
    tampered["body"]["fill_cost_cents"] += 1

    with pytest.raises(ValueError, match="digest"):
        adapter.record_signed_terminal_reconciliation(tampered)

    wrong_key = Ed25519PrivateKey.from_private_bytes(bytes([7]) * 32)
    wrong = sign_broker_witness(
        terminal["body"],
        private_key=wrong_key,
        observed_at=NOW,
        correlation_id=request.proposal_id,
    )
    with pytest.raises(ValueError, match="trusted"):
        adapter.record_signed_terminal_reconciliation(wrong)

    assert journal.events(kind="capital.reservation.released") == ()
    assert adapter.pending_reconciliation_reservations()


def test_caller_authored_terminal_receipts_never_release_capital(tmp_path):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope(
        max_order_risk_cents=100,
        max_open_risk_cents=100,
        max_correlated_risk_cents=100,
    )
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper, price_cents=80)
    reservation = adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert reservation.reservation_id

    with pytest.raises(ValueError, match="sealed broker witness"):
        adapter.release_from_terminal_reconciliation(
            proposal_id=request.proposal_id,
            terminal_status="ambiguous",
            reconciliation_receipt={
                "schema": "dummy.terminal-order-reconciliation.v1",
                "terminal_status": "ambiguous",
                "proposal_id": request.proposal_id,
                "order_id": "broker-order-1",
                "broker_contacted": True,
                "local_exposure_projection_persisted": True,
            },
        )
    with pytest.raises(ValueError, match="sealed broker witness"):
        adapter.release_from_terminal_reconciliation(
            proposal_id=request.proposal_id,
            terminal_status="filled",
            reconciliation_receipt={
                "schema": "dummy.terminal-order-reconciliation.v1",
                "terminal_status": "filled",
                "proposal_id": request.proposal_id,
                "order_id": "broker-order-1",
                "broker_contacted": False,
                "local_exposure_projection_persisted": True,
            },
        )
    assert not journal.events(kind="capital.reservation.released")

    receipt = {
        "schema": "dummy.terminal-order-reconciliation.v1",
        "terminal_status": "filled",
        "proposal_id": request.proposal_id,
        "broker_contacted": True,
        "order_id": "broker-order-1",
        "fill_count": 1,
        "fill_price_cents": request.price_cents,
        "local_exposure_projection_persisted": True,
    }
    with pytest.raises(ValueError, match="sealed broker witness"):
        adapter.release_from_terminal_reconciliation(
            proposal_id=request.proposal_id,
            terminal_status="filled",
            reconciliation_receipt=receipt,
        )

    reloaded_journal = AppendOnlyOperationalJournal(
        journal.path,
        now_fn=lambda: NOW,
    )
    reloaded = CapitalEnvelopeAdapter(
        journal=reloaded_journal,
        trusted_public_keys={SIGNER_KEY_ID: PUBLIC_KEY},
        expected_venue="dummy_kalshi",
        expected_account_hash=ACCOUNT_HASH,
        lineage_resolver=LINEAGE_RESOLVER,
        now_fn=lambda: NOW,
    )
    with pytest.raises(ValueError, match="sealed broker witness"):
        reloaded.release_from_terminal_reconciliation(
            proposal_id=request.proposal_id,
            terminal_status="filled",
            reconciliation_receipt=receipt,
        )
    assert not reloaded_journal.events(
        kind="capital.terminal_reconciliation.witnessed"
    )
    assert not reloaded_journal.events(kind="capital.reservation.released")
    assert not reloaded_journal.events(kind="capital.position.exposure.recorded")
    replay = reloaded.reserve_request(
        request,
        current_daily_loss_cents=0,
    )
    assert replay.allow is True
    assert replay.reservation_id == reservation.reservation_id

    # Filled risk remains charged in the independent capital journal even if a
    # different process has an empty or stale local position book.
    next_request = _request(
        wrapper,
        proposal_id="proposal-2",
        price_cents=30,
    )
    blocked = reloaded.evaluate_request(
        next_request,
        current_daily_loss_cents=0,
    )
    assert blocked.allow is False
    assert "open risk" in blocked.reason


def test_brain_releases_only_after_persisted_terminal_broker_witness(
    tmp_path,
    monkeypatch,
):
    import live_firewall.exposure_tracker as tracker_module

    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    assert adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    ).allow
    tracker = ExposureTracker()
    assert tracker.reserve_order_submission(
        request.proposal_id,
        request.market_ticker,
        request.size,
        request.price_cents,
        contract_ticker=request.contract_ticker,
        side=request.side,
    )
    assert tracker.confirm_open_order(request.proposal_id, "broker-order-1")
    monkeypatch.setattr(
        tracker_module,
        "get_persistent_exposure_tracker",
        lambda: tracker,
    )
    brain = SimpleNamespace(
        mode=SessionMode.LIVE,
        executor=SimpleNamespace(capital_envelope_adapter=adapter),
    )
    outcome = TradeOutcome(
        decision_id="test-decision",
        market_ticker=request.market_ticker,
        kind=OutcomeKind.FILLED,
        order_id="broker-order-1",
        fill_count=1,
        fill_price_cents=request.price_cents,
        pnl_cents=None,
        broker_contacted=True,
        detail={"state": "filled"},
        created_at=_z(NOW),
    )

    PredatorBrain._sync_live_exposure(brain, [outcome])

    assert not journal.events(kind="capital.reservation.released")
    assert not journal.events(kind="capital.position.exposure.recorded")
    assert tracker.open_order_count() == 0
    assert tracker.total_exposure_cents() == request.price_cents


def test_brain_retains_capital_without_terminal_status_witness(
    tmp_path,
    monkeypatch,
):
    import live_firewall.exposure_tracker as tracker_module

    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    assert adapter.reserve_request(
        request,
        current_daily_loss_cents=0,
    ).allow
    tracker = ExposureTracker()
    assert tracker.reserve_order_submission(
        request.proposal_id,
        request.market_ticker,
        request.size,
        request.price_cents,
        contract_ticker=request.contract_ticker,
        side=request.side,
    )
    assert tracker.confirm_open_order(request.proposal_id, "broker-order-1")
    monkeypatch.setattr(
        tracker_module,
        "get_persistent_exposure_tracker",
        lambda: tracker,
    )
    brain = SimpleNamespace(
        mode=SessionMode.LIVE,
        executor=SimpleNamespace(capital_envelope_adapter=adapter),
    )
    ambiguous_cancel = TradeOutcome(
        decision_id="test-decision",
        market_ticker=request.market_ticker,
        kind=OutcomeKind.CANCELED,
        order_id="broker-order-1",
        fill_count=0,
        fill_price_cents=request.price_cents,
        pnl_cents=None,
        broker_contacted=True,
        detail={"reason": "cancel_requested_without_terminal_status"},
        created_at=_z(NOW),
    )

    PredatorBrain._sync_live_exposure(brain, [ambiguous_cancel])

    assert not journal.events(kind="capital.reservation.released")


def test_cancel_only_degraded_mode_never_invents_cancel_authority(tmp_path):
    adapter, journal = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    assert adapter.evaluate_request(request, current_daily_loss_cents=0).allow

    receipt = adapter.enter_cancel_only(
        reason="kill switch asserted",
        kill_asserted_at=_z(NOW),
    )

    assert receipt["payload"]["submission_authority"] is False
    assert receipt["payload"]["cancel_authority"] is False
    assert receipt["payload"]["broker_contacted"] is False
    assert not journal.events(kind="cancel.reconciliation.requested")
    blocked = adapter.evaluate_request(request, current_daily_loss_cents=0)
    assert blocked.allow is False
    assert blocked.rejected_by == "capital_cancel_only"

    with pytest.raises(ValueError, match="opaque receipt"):
        adapter.enter_cancel_only(
            reason="unverified cancel authority supplied",
            kill_asserted_at=_z(NOW),
            cancel_authorized=True,
            cancel_authority_receipt="opaque-authority-claim",
        )
    assert not journal.events(kind="cancel.reconciliation.requested")


def test_kill_queue_mirrors_cancel_only_without_cancel_command(tmp_path):
    adapter, journal = _adapter(tmp_path)

    receipt = queue_kill_reconciliation(
        kill_asserted_at=_z(NOW),
        receipt_path=tmp_path / "kill-reconciliation.json",
        capital_envelope_adapter=adapter,
    )

    assert receipt["submission_authority"] is False
    assert receipt["cancel_authority"] is False
    assert receipt["broker_contacted"] is False
    assert receipt["dumbmoney_operational_status"] == "CANCEL_AUTHORITY_REQUIRED"
    assert len(journal.events(kind="authority.cancel_only")) == 1
    assert not journal.events(kind="cancel.reconciliation.requested")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("local_order_cap", "grant_order_cap", "expected_rejected_by"),
    [
        (100, 500, "single_order_cap"),
        (500, 100, "capital_limits"),
    ],
)
async def test_firewall_intersects_local_and_signed_caps(
    tmp_path,
    monkeypatch,
    local_order_cap,
    grant_order_cap,
    expected_rejected_by,
):
    import live_firewall.firewall as firewall_module

    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope(
        max_order_risk_cents=grant_order_cap,
        max_open_risk_cents=1_000,
        max_correlated_risk_cents=1_000,
    )
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper, price_cents=50, size=3)
    caps = CapConfig(
        max_single_order_cents=local_order_cap,
        max_market_exposure_cents=2_000,
        max_correlated_exposure_cents=2_000,
        max_total_live_exposure_cents=2_000,
        max_daily_loss_cents=1_000,
        max_open_markets=10,
        max_orders_per_hour=10,
        allowed_markets=[request.market_ticker],
        max_spread_cents=5,
        min_liquidity=10,
        min_edge_bps=50,
    )
    monkeypatch.setattr(firewall_module, "load_caps", lambda: caps)
    monkeypatch.setattr(
        firewall_module,
        "get_allowed_adapter_names",
        lambda: {"kalshi_live_firewall_adapter"},
    )
    monkeypatch.setenv("KALSHI_API_KEY_ID", "fixture-key-id")
    state = DummyState()
    state.set_mode(AccountMode.AUTONOMOUS_LIVE_CAPPED)
    monkeypatch.setattr(firewall_module, "STATE", state)
    firewall = LiveBrokerFirewall(
        None,
        ExposureTracker(),
        capital_envelope_adapter=adapter,
    )
    book = OrderBook(
        market_ticker=request.market_ticker,
        contract_ticker=request.contract_ticker,
        bids=[OrderBookLevel(price=48, size=20)],
        asks=[OrderBookLevel(price=52, size=20)],
        timestamp=datetime.now(timezone.utc),
    )
    forecast = Forecast(
        market_ticker=request.market_ticker,
        contract_ticker=request.contract_ticker,
        event_title="Fixture",
        contract_title="Fixture yes",
        market_implied_probability=Decimal("0.50"),
        dummy_probability=Decimal("0.80"),
        probability_delta=Decimal("0.30"),
        confidence_score=Decimal("0.80"),
        uncertainty_band=(Decimal("0.75"), Decimal("0.85")),
        expected_edge=Decimal("0.25"),
        edge_after_fees=Decimal("0.20"),
        freshness_score=Decimal("1"),
        liquidity_score=Decimal("1"),
        spread_score=Decimal("1"),
        orderbook_depth_score=Decimal("1"),
        settlement_risk_score=Decimal("0.1"),
        source_summary="fixture",
        model_summary="fixture",
        calibration_notes="fixture",
        timestamp=datetime.now(timezone.utc),
        expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        strategy_references=[STRATEGY_REFERENCE],
        proof_reference=PASSPORT_REFERENCE,
    )

    verdict = await firewall.evaluate(request, book, forecast)

    assert verdict.allow is False
    assert verdict.rejected_by == expected_rejected_by


def test_final_firewall_authority_requires_current_core_command_state(
    tmp_path,
):
    adapter, _ = _adapter(tmp_path)
    wrapper = _signed_envelope()
    adapter.accept_signed_envelope(wrapper)
    _record_flat(adapter)
    request = _request(wrapper)
    firewall = LiveBrokerFirewall(
        None,
        ExposureTracker(),
        capital_envelope_adapter=adapter,
        core_submission_authority=lambda: False,
    )

    verdict = firewall._mandatory_submit_authority(request)

    assert verdict.allow is False
    assert verdict.rejected_by == "core_command_authority"


def test_operational_journal_outbox_is_append_only_and_replayable(tmp_path):
    path = tmp_path / "journal.jsonl"
    journal = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    first = journal.append(
        "fixture.event",
        {"value": 1},
        outbox_id="fixture-outbox",
    )
    repeated = journal.append(
        "fixture.event",
        {"value": 1},
        outbox_id="fixture-outbox",
    )
    assert repeated["event_sha256"] == first["event_sha256"]
    assert len(journal.pending_outbox()) == 1

    journal.acknowledge_outbox(
        "fixture-outbox",
        acknowledgement={"receiver": "dumbmoney-core"},
    )
    assert journal.pending_outbox() == ()

    reloaded = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    assert reloaded.healthy is True
    assert len(reloaded.events()) == 2


def test_operational_journal_serializes_two_preloaded_instances(tmp_path):
    path = tmp_path / "shared-journal.jsonl"
    first_writer = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    second_writer = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)

    first = first_writer.append("writer.a", {"value": 1})
    second = second_writer.append("writer.b", {"value": 2})
    third = first_writer.append("writer.a", {"value": 3})

    assert [first["sequence"], second["sequence"], third["sequence"]] == [1, 2, 3]
    assert second["previous_sha256"] == first["event_sha256"]
    assert third["previous_sha256"] == second["event_sha256"]
    assert [row["kind"] for row in second_writer.events()] == [
        "writer.a",
        "writer.b",
        "writer.a",
    ]

    restarted = AppendOnlyOperationalJournal(path, now_fn=lambda: NOW)
    assert restarted.healthy is True
    assert [row["sequence"] for row in restarted.events()] == [1, 2, 3]
