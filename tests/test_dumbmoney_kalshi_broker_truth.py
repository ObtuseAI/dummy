from __future__ import annotations

import base64
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from live_firewall import dumbmoney_windows_service as windows_service
from live_firewall.dumbmoney_capital import verify_signed_envelope
from live_firewall.kalshi_broker_truth import (
    KALSHI_API_PREFIX,
    KALSHI_PRODUCTION_ORIGIN,
    KalshiBrokerTruthError,
    KalshiBrokerTruthProvider,
)
from live_firewall.kalshi_reconciliation import (
    KalshiReconciliationReader,
)


NOW = datetime(2026, 7, 26, 22, 0, tzinfo=timezone.utc)
KEY_ID = "test-key-id"
ACCOUNT_HASH = windows_service.kalshi_account_hash(KEY_ID, 0)


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65_537, key_size=2_048)


@pytest.fixture(scope="module")
def private_key_pem(private_key: rsa.RSAPrivateKey) -> bytes:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _client(
    handler: Any,
) -> httpx.Client:
    return httpx.Client(
        base_url=f"{KALSHI_PRODUCTION_ORIGIN}{KALSHI_API_PREFIX}/",
        transport=httpx.MockTransport(handler),
        trust_env=False,
        follow_redirects=False,
    )


def _provider(
    private_key_pem: bytes,
    handler: Any,
    **kwargs: Any,
) -> KalshiBrokerTruthProvider:
    return KalshiBrokerTruthProvider(
        api_key_id=KEY_ID,
        private_key_pem=private_key_pem,
        expected_account_hash=ACCOUNT_HASH,
        subaccount_number=0,
        client=_client(handler),
        clock=lambda: NOW,
        **kwargs,
    )


def _flat_handler(requests: list[httpx.Request]) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/portfolio/balance"):
            payload = {
                "balance": 123,
                "balance_dollars": "1.2300",
                "portfolio_value": 0,
                "updated_ts": 1_721_000_000,
                "balance_breakdown": [],
            }
        elif request.url.path.endswith("/portfolio/positions"):
            payload = {
                "market_positions": [],
                "event_positions": [],
                "cursor": "",
            }
        elif request.url.path.endswith("/portfolio/orders"):
            payload = {"orders": [], "cursor": ""}
        else:
            raise AssertionError(f"unexpected path: {request.url.path}")
        return httpx.Response(200, json=payload, request=request)

    return handler


def test_flat_snapshot_is_signed_scoped_stable_and_network_read_only(
    private_key: rsa.RSAPrivateKey,
    private_key_pem: bytes,
) -> None:
    requests: list[httpx.Request] = []
    provider = _provider(private_key_pem, _flat_handler(requests))
    try:
        snapshot = provider.snapshot()
    finally:
        provider.close()

    assert snapshot == {
        "schema": "dummy.kalshi-broker-truth.v1",
        "venue": "dummy_kalshi",
        "account_hash": ACCOUNT_HASH,
        "subaccount_number": 0,
        "observed_at": "2026-07-26T22:00:00Z",
        "broker_snapshot_sha256": snapshot["broker_snapshot_sha256"],
        "flat_book_observed": True,
        "total_exposure_cents": 0,
        "open_order_count": 0,
        "market_exposure_cents": {},
        "correlated_exposure_cents": {},
        "unresolved_open_orders": 0,
        "unresolved_positions": 0,
    }
    assert len(snapshot["broker_snapshot_sha256"]) == 64
    assert [request.method for request in requests] == ["GET"] * 5
    assert Counter(request.url.path for request in requests) == {
        f"{KALSHI_API_PREFIX}/portfolio/balance": 1,
        f"{KALSHI_API_PREFIX}/portfolio/positions": 2,
        f"{KALSHI_API_PREFIX}/portfolio/orders": 2,
    }
    for request in requests:
        assert request.url.host == "external-api.kalshi.com"
        assert request.url.scheme == "https"
        assert request.url.params["subaccount"] == "0"
        assert request.headers["KALSHI-ACCESS-KEY"] == KEY_ID
        timestamp = request.headers["KALSHI-ACCESS-TIMESTAMP"]
        signature = request.headers["KALSHI-ACCESS-SIGNATURE"]
        private_key.public_key().verify(
            base64.b64decode(signature),
            f"{timestamp}GET{request.url.path}".encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
    positions = [
        request
        for request in requests
        if request.url.path.endswith("/portfolio/positions")
    ]
    orders = [
        request
        for request in requests
        if request.url.path.endswith("/portfolio/orders")
    ]
    assert all(request.url.params["limit"] == "1000" for request in positions)
    assert all(
        request.url.params["count_filter"] == "position"
        for request in positions
    )
    assert all(request.url.params["status"] == "resting" for request in orders)


def test_paginated_exposure_is_complete_and_conservative(
    private_key_pem: bytes,
) -> None:
    calls: Counter[tuple[str, str]] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        cursor = request.url.params.get("cursor", "")
        calls[(path, cursor)] += 1
        if path.endswith("/portfolio/balance"):
            payload = {
                "balance": 500,
                "balance_dollars": "5.0000",
                "portfolio_value": 25,
                "updated_ts": 1_721_000_001,
            }
        elif path.endswith("/portfolio/positions") and not cursor:
            payload = {
                "market_positions": [
                    {
                        "ticker": "KXTEST-A",
                        "position_fp": "1.00",
                        "market_exposure_dollars": "0.1234",
                        "last_updated_ts": "2026-07-26T21:59:00Z",
                    }
                ],
                "event_positions": [
                    {
                        "event_ticker": "KXTEST",
                        "event_exposure_dollars": "0.2000",
                    }
                ],
                "cursor": "positions-next",
            }
        elif path.endswith("/portfolio/positions"):
            assert cursor == "positions-next"
            payload = {
                "market_positions": [
                    {
                        "ticker": "KXOTHER-B",
                        "position_fp": "-2.00",
                        "market_exposure_dollars": "-0.0001",
                        "last_updated_ts": "2026-07-26T21:59:30Z",
                    }
                ],
                "event_positions": [
                    {
                        "event_ticker": "KXOTHER",
                        "event_exposure_dollars": "0.0500",
                    }
                ],
                "cursor": "",
            }
        elif path.endswith("/portfolio/orders") and not cursor:
            payload = {
                "orders": [
                    {
                        "order_id": "order-a",
                        "ticker": "KXTEST-A",
                        "remaining_count_fp": "1.00",
                        "yes_price_dollars": "0.4000",
                        "no_price_dollars": "0.6000",
                        "subaccount_number": 0,
                    }
                ],
                "cursor": "orders-next",
            }
        elif path.endswith("/portfolio/orders"):
            assert cursor == "orders-next"
            payload = {
                "orders": [
                    {
                        "order_id": "order-b",
                        "ticker": "KXOTHER-B",
                        "remaining_count_fp": "2.00",
                        "yes_price_dollars": "0.7500",
                        "no_price_dollars": "0.2500",
                        "subaccount_number": 0,
                    }
                ],
                "cursor": "",
            }
        else:
            raise AssertionError(path)
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(private_key_pem, handler)
    try:
        snapshot = provider.snapshot()
    finally:
        provider.close()

    assert snapshot["flat_book_observed"] is False
    assert snapshot["total_exposure_cents"] == 25
    assert snapshot["market_exposure_cents"] == {
        "KXOTHER-B": 1,
        "KXTEST-A": 13,
    }
    assert snapshot["correlated_exposure_cents"] == {
        "KXOTHER": 5,
        "KXTEST": 20,
    }
    assert snapshot["open_order_count"] == 2
    assert snapshot["unresolved_open_orders"] == 2
    assert snapshot["unresolved_positions"] == 2
    assert calls[
        (f"{KALSHI_API_PREFIX}/portfolio/positions", "")
    ] == 2
    assert calls[
        (f"{KALSHI_API_PREFIX}/portfolio/positions", "positions-next")
    ] == 2
    assert calls[
        (f"{KALSHI_API_PREFIX}/portfolio/orders", "")
    ] == 2
    assert calls[
        (f"{KALSHI_API_PREFIX}/portfolio/orders", "orders-next")
    ] == 2


def test_snapshot_rejects_state_that_changes_between_double_reads(
    private_key_pem: bytes,
) -> None:
    position_reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal position_reads
        if request.url.path.endswith("/portfolio/balance"):
            payload = {
                "balance": 100,
                "balance_dollars": "1.0000",
                "portfolio_value": 0,
                "updated_ts": 1,
            }
        elif request.url.path.endswith("/portfolio/orders"):
            payload = {"orders": [], "cursor": ""}
        else:
            position_reads += 1
            markets = (
                []
                if position_reads == 1
                else [
                    {
                        "ticker": "KXCHANGED",
                        "position_fp": "1.00",
                        "market_exposure_dollars": "0.1000",
                        "last_updated_ts": "2026-07-26T21:59:00Z",
                    }
                ]
            )
            payload = {
                "market_positions": markets,
                "event_positions": [],
                "cursor": "",
            }
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(private_key_pem, handler)
    try:
        with pytest.raises(
            KalshiBrokerTruthError,
            match="changed during reconciliation",
        ):
            provider.snapshot()
    finally:
        provider.close()


@pytest.mark.parametrize(
    ("market_positions", "event_positions", "message"),
    [
        (
            [
                {
                    "ticker": "KXFUTURE",
                    "position_fp": "1.00",
                    "market_exposure_dollars": "0.1000",
                    "last_updated_ts": "2026-07-26T22:00:06Z",
                }
            ],
            [],
            "timestamp is in the future",
        ),
        (
            [],
            [
                {
                    "event_ticker": "KXORPHAN",
                    "event_exposure_dollars": "0.1000",
                }
            ],
            "event exposure exists without a market position",
        ),
    ],
)
def test_snapshot_rejects_internally_inconsistent_position_evidence(
    private_key_pem: bytes,
    market_positions: list[dict[str, Any]],
    event_positions: list[dict[str, Any]],
    message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/portfolio/balance"):
            payload = {
                "balance": 100,
                "balance_dollars": "1.0000",
                "portfolio_value": 0,
                "updated_ts": 1,
            }
        elif request.url.path.endswith("/portfolio/positions"):
            payload = {
                "market_positions": market_positions,
                "event_positions": event_positions,
                "cursor": "",
            }
        else:
            payload = {"orders": [], "cursor": ""}
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(private_key_pem, handler)
    try:
        with pytest.raises(KalshiBrokerTruthError, match=message):
            provider.snapshot()
    finally:
        provider.close()


def test_snapshot_rejects_incomplete_pagination(
    private_key_pem: bytes,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/portfolio/balance"):
            payload = {
                "balance": 100,
                "balance_dollars": "1.0000",
                "portfolio_value": 0,
                "updated_ts": 1,
            }
        else:
            payload = {
                "market_positions": [],
                "event_positions": [],
                "cursor": "still-more",
            }
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(
        private_key_pem,
        handler,
        maximum_pages=1,
    )
    try:
        with pytest.raises(
            KalshiBrokerTruthError,
            match="positions pagination is incomplete",
        ):
            provider.snapshot()
    finally:
        provider.close()


@pytest.mark.parametrize(
    "body",
    [
        b'{"balance":100,"balance":200,"balance_dollars":"1.0000",'
        b'"portfolio_value":0,"updated_ts":1}',
        b'{"balance":NaN,"balance_dollars":"1.0000",'
        b'"portfolio_value":0,"updated_ts":1}',
    ],
)
def test_snapshot_rejects_non_strict_broker_json(
    private_key_pem: bytes,
    body: bytes,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json"},
            request=request,
        )

    provider = _provider(private_key_pem, handler)
    try:
        with pytest.raises(
            KalshiBrokerTruthError,
            match="strict bounded JSON",
        ):
            provider.snapshot()
    finally:
        provider.close()


def test_snapshot_rejects_order_from_another_subaccount(
    private_key_pem: bytes,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/portfolio/balance"):
            payload = {
                "balance": 100,
                "balance_dollars": "1.0000",
                "portfolio_value": 0,
                "updated_ts": 1,
            }
        elif request.url.path.endswith("/portfolio/positions"):
            payload = {
                "market_positions": [],
                "event_positions": [],
                "cursor": "",
            }
        else:
            payload = {
                "orders": [
                    {
                        "order_id": "wrong-account",
                        "ticker": "KXTEST",
                        "remaining_count_fp": "1.00",
                        "yes_price_dollars": "0.5000",
                        "no_price_dollars": "0.5000",
                        "subaccount_number": 1,
                    }
                ],
                "cursor": "",
            }
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(private_key_pem, handler)
    try:
        with pytest.raises(
            KalshiBrokerTruthError,
            match="different subaccount",
        ):
            provider.snapshot()
    finally:
        provider.close()


def test_production_constructor_is_proxy_isolated_and_origin_pinned(
    monkeypatch: pytest.MonkeyPatch,
    private_key_pem: bytes,
) -> None:
    constructed = Mock()
    monkeypatch.setattr(
        "live_firewall.kalshi_broker_truth.httpx.Client",
        constructed,
    )
    KalshiBrokerTruthProvider(
        api_key_id=KEY_ID,
        private_key_pem=private_key_pem,
        expected_account_hash=ACCOUNT_HASH,
        subaccount_number=0,
        clock=lambda: NOW,
    )

    assert constructed.call_count == 1
    kwargs = constructed.call_args.kwargs
    assert kwargs["base_url"] == (
        "https://external-api.kalshi.com/trade-api/v2/"
    )
    assert kwargs["trust_env"] is False
    assert kwargs["follow_redirects"] is False
    assert kwargs["limits"].max_connections == 1


def test_service_main_wires_credential_owned_truth_without_contacting_broker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    private_key_pem: bytes,
) -> None:
    config = SimpleNamespace(
        data_root=tmp_path / "data",
        expected_account_hash=ACCOUNT_HASH,
        kalshi_subaccount_number=0,
    )
    secrets = SimpleNamespace(
        kalshi_key_id=KEY_ID,
        kalshi_private_key_pem=private_key_pem,
    )
    provider = object()
    captured: dict[str, Any] = {}

    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))
    monkeypatch.setattr(
        windows_service,
        "load_runner_config",
        lambda *_args: config,
    )
    monkeypatch.setattr(
        windows_service,
        "load_secrets",
        lambda *_args: secrets,
    )
    monkeypatch.setattr(
        windows_service,
        "WindowsCredentialManager",
        lambda: object(),
    )
    monkeypatch.setattr(
        windows_service,
        "LoopbackCoreTransport",
        lambda: object(),
    )

    def truth_factory(**kwargs: Any) -> object:
        captured["truth_kwargs"] = kwargs
        return provider

    class Service:
        def __init__(
            self,
            _config: Any,
            _secrets: Any,
            **kwargs: Any,
        ) -> None:
            captured["service_kwargs"] = kwargs

        def run_forever(self, _stop_event: Any) -> None:
            return

    monkeypatch.setattr(
        windows_service,
        "KalshiBrokerTruthProvider",
        truth_factory,
    )
    monkeypatch.setattr(
        windows_service,
        "DumbMoneyDummyKalshiService",
        Service,
    )
    monkeypatch.setattr(windows_service.signal, "signal", lambda *_args: None)

    result = windows_service.main(
        [
            "--core-endpoint-ref",
            windows_service.CORE_ENDPOINT_REF,
            "--core-cell-token-target",
            windows_service.CELL_TOKEN_TARGET_REF,
            "--kalshi-key-id-target",
            windows_service.KALSHI_KEY_ID_TARGET_REF,
            "--kalshi-private-key-target",
            windows_service.KALSHI_PRIVATE_KEY_TARGET_REF,
            "--readiness-signing-key-target",
            windows_service.READINESS_KEY_TARGET_REF,
            "--start-mode",
            windows_service.START_MODE,
            "--readiness-ref",
            windows_service.READINESS_REF,
            "--config-sha256",
            "b" * 64,
        ]
    )

    assert result == 0
    assert captured["truth_kwargs"] == {
        "api_key_id": KEY_ID,
        "private_key_pem": private_key_pem,
        "expected_account_hash": ACCOUNT_HASH,
        "subaccount_number": 0,
    }
    assert captured["service_kwargs"]["broker_truth"] is provider
    cycle = captured["service_kwargs"]["execution_cycle"]
    assert isinstance(cycle, windows_service.SealedDisabledExecutionCycle)
    assert cycle.submission_capable is False


def test_service_close_closes_broker_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        Path(windows_service.__file__)
        .read_text(encoding="utf-8")
        .replace("\r\n", "\n")
    )
    assert 'getattr(self.broker_truth, "close", None)' in source
    assert "broker_close()" in source


def test_terminal_reader_combines_live_and_historical_fills_and_signs(
    private_key_pem: bytes,
) -> None:
    signing_key = Ed25519PrivateKey.from_private_bytes(bytes([6]) * 32)
    public_key = signing_key.public_key().public_bytes_raw()
    signer_id = hashlib.sha256(public_key).hexdigest()
    requests: list[httpx.Request] = []

    order = {
        "order_id": "broker-order-1",
        "user_id": "fixture-user",
        "client_order_id": "proposal-1",
        "ticker": "KXTEST-26JUL",
        "side": "yes",
        "action": "buy",
        "outcome_side": "yes",
        "book_side": "bid",
        "type": "limit",
        "status": "executed",
        "yes_price_dollars": "0.500000",
        "no_price_dollars": "0.500000",
        "fill_count_fp": "1.00",
        "remaining_count_fp": "0.00",
        "initial_count_fp": "1.00",
        "taker_fill_cost_dollars": "0.500000",
        "maker_fill_cost_dollars": "0.000000",
        "taker_fees_dollars": "0.020000",
        "maker_fees_dollars": "0.000000",
        "expiration_time": "2026-07-26T22:30:00Z",
        "created_time": "2026-07-26T21:59:00Z",
        "last_update_time": "2026-07-26T21:59:30Z",
        "self_trade_prevention_type": "taker_at_cross",
        "order_group_id": "",
        "cancel_order_on_pause": True,
        "subaccount_number": 0,
    }
    fill = {
        "fill_id": "fill-1",
        "trade_id": "trade-1",
        "order_id": "broker-order-1",
        "ticker": "KXTEST-26JUL",
        "market_ticker": "KXTEST-26JUL",
        "side": "yes",
        "action": "buy",
        "outcome_side": "yes",
        "book_side": "bid",
        "count_fp": "1.00",
        "yes_price_dollars": "0.500000",
        "no_price_dollars": "0.500000",
        "is_taker": True,
        "fee_cost": "0.020000",
        "created_time": "2026-07-26T21:59:30Z",
        "subaccount_number": 0,
        "ts": 1_721_000_000,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/orders"):
            payload = {"orders": [order], "cursor": ""}
        elif request.url.path.endswith("/fills"):
            payload = {"fills": [fill], "cursor": ""}
        else:
            raise AssertionError(request.url.path)
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(private_key_pem, handler)
    reader = KalshiReconciliationReader(
        broker_truth=provider,
        witness_signing_private_key=signing_key,
    )
    reservation = {
        "reservation_id": hashlib.sha256(b"reservation").hexdigest(),
        "proposal_id": "proposal-1",
        "market_ticker": "KXTEST-26JUL",
        "contract_ticker": "KXTEST-26JUL",
        "side": "yes",
        "size": 1,
        "price_cents": 50,
    }
    try:
        with pytest.raises(
            KalshiBrokerTruthError,
            match="differs from the capital reservation",
        ):
            reader.terminal_reconciliation_witness(
                {**reservation, "price_cents": 49}
            )
        requests.clear()
        wrapper = reader.terminal_reconciliation_witness(reservation)
    finally:
        provider.close()

    assert wrapper is not None
    signed = verify_signed_envelope(
        wrapper,
        trusted_public_keys={signer_id: public_key},
        expected_body_schema=(
            "dummy.kalshi-order-terminal-witness.v1"
        ),
        require_active=False,
    )
    assert signed.body["terminal_status"] == "executed"
    assert signed.body["fill_count"] == 1
    assert signed.body["fill_cost_cents"] == 50
    assert signed.body["fee_cents"] == 2
    assert signed.body["average_fill_price_cents"] == 50
    assert signed.body["fill_ids"] == ["fill-1"]
    assert Counter(request.url.path for request in requests) == {
        f"{KALSHI_API_PREFIX}/portfolio/orders": 2,
        f"{KALSHI_API_PREFIX}/historical/orders": 2,
        f"{KALSHI_API_PREFIX}/portfolio/fills": 2,
        f"{KALSHI_API_PREFIX}/historical/fills": 2,
    }
    live_requests = [
        request for request in requests
        if "/portfolio/" in request.url.path
    ]
    assert all(
        request.url.params["subaccount"] == "0"
        for request in live_requests
    )


def test_settlement_reader_requires_stable_position_absence(
    private_key_pem: bytes,
) -> None:
    signing_key = Ed25519PrivateKey.from_private_bytes(bytes([5]) * 32)
    position_reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal position_reads
        if request.url.path.endswith("/positions"):
            position_reads += 1
            payload = {
                "market_positions": [],
                "event_positions": [],
                "cursor": "",
            }
        elif request.url.path.endswith("/settlements"):
            payload = {
                "settlements": [
                    {
                        "ticker": "KXTEST-26JUL",
                        "event_ticker": "KXTEST",
                        "market_result": "yes",
                        "yes_count_fp": "1.00",
                        "yes_total_cost_dollars": "0.500000",
                        "no_count_fp": "0.00",
                        "no_total_cost_dollars": "0.000000",
                        "revenue": 100,
                        "settled_time": "2026-07-26T21:59:59Z",
                        "fee_cost": "0.020000",
                        "value": 100,
                    }
                ],
                "cursor": "",
            }
        else:
            raise AssertionError(request.url.path)
        return httpx.Response(200, json=payload, request=request)

    provider = _provider(private_key_pem, handler)
    reader = KalshiReconciliationReader(
        broker_truth=provider,
        witness_signing_private_key=signing_key,
    )
    position = {
        "position_exposure_id": hashlib.sha256(b"position").hexdigest(),
        "reservation_id": hashlib.sha256(b"reservation").hexdigest(),
        "proposal_id": "proposal-1",
        "contract_ticker": "KXTEST-26JUL",
        "side": "yes",
        "fill_count": 1,
        "observed_at": "2026-07-26T21:59:30Z",
    }
    try:
        wrapper = reader.settlement_reconciliation_witness(position)
    finally:
        provider.close()

    assert wrapper is not None
    assert wrapper["body"]["position_absent"] is True
    assert wrapper["body"]["market_result"] == "yes"
    assert wrapper["body"]["settlement_fee_cents"] == 2
    assert position_reads == 2
