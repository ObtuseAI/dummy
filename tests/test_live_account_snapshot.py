from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import httpx

from autonomy.live_account_snapshot import (
    AccountSnapshotGetOnlyTransport,
    collect_live_account_snapshot,
    load_live_account_env,
    read_live_account_snapshot,
    refresh_live_account_snapshot,
    write_live_account_snapshot,
)
from kalshi.client import KalshiClient


NOW = datetime(2026, 7, 22, 18, 0, tzinfo=timezone.utc)


class FakeKalshiClient:
    def __init__(
        self,
        *,
        include_available_balance: bool = True,
        fills_error: Exception | None = None,
        injected_audit: dict[str, Any] | None = None,
    ) -> None:
        self.include_available_balance = include_available_balance
        self.fills_error = fills_error
        self.injected_audit = injected_audit
        self.request_audit_log: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, path, kwargs))
        self.request_audit_log.append(
            {
                "method": method,
                "path": path,
                "path_family": path,
                "status_code": 200,
                "status_class": "2xx",
                "redacted_summary": {"keys": ["do_not_copy_raw_summaries"]},
            }
        )
        if path == "/portfolio/balance":
            response: dict[str, Any] = {
                "balance": 13_579,
                "portfolio_value": 2_468,
                "updated_ts": 1_753_207_200,
                "user_id": "secret-user-id",
            }
            if self.include_available_balance:
                response["available_balance"] = 12_345
            return response
        if path == "/portfolio/positions":
            return {
                "market_positions": [
                    {"ticker": "SECRET-TICKER-ONE", "position_fp": "3.00"},
                    {"ticker": "SECRET-TICKER-ZERO", "position_fp": "0.00"},
                ],
                "cursor": "",
            }
        if path == "/portfolio/orders":
            if self.injected_audit is not None:
                self.request_audit_log.append(self.injected_audit)
            return {
                "orders": [
                    {
                        "order_id": "secret-order-resting",
                        "ticker": "SECRET-TICKER-ONE",
                        "status": "resting",
                    },
                    {"order_id": "secret-order-executed", "status": "executed"},
                    {"order_id": "secret-order-canceled", "status": "canceled"},
                    {"order_id": "secret-order-weird", "status": "secret-status"},
                ],
                "cursor": "",
            }
        if path == "/portfolio/fills":
            if self.fills_error is not None:
                raise self.fills_error
            return {
                "fills": [
                    {
                        "fill_id": "secret-fill-id",
                        "order_id": "secret-order-executed",
                        "ticker": "SECRET-TICKER-ONE",
                    }
                ],
                "cursor": "",
            }
        raise AssertionError(f"unexpected path in hermetic fake: {path}")


@pytest.mark.asyncio
async def test_snapshot_is_sanitized_and_proves_get_only_collection() -> None:
    client = FakeKalshiClient()

    snapshot = await collect_live_account_snapshot(client=client, now=NOW)

    assert snapshot["schema"] == "dummy.live_account_snapshot"
    assert snapshot["version"] == 1
    assert snapshot["generated_at"] == NOW.isoformat()
    assert snapshot["status"] == "FRESH"
    assert snapshot["stale"] is False
    assert snapshot["reason"] is None
    assert snapshot["execution_authority"] is False
    assert snapshot["balance_cents"] == 13_579
    assert snapshot["available_balance_cents"] == 12_345
    assert snapshot["open_positions_count"] == 1
    assert snapshot["open_orders_count"] == 1
    assert snapshot["historical_orders_count"] == 3
    assert snapshot["historical_fills_count"] == 1
    assert snapshot["order_status_counts"] == {
        "canceled": 1,
        "executed": 1,
        "other": 1,
        "resting": 1,
    }
    assert snapshot["source"]["provider"] == "kalshi"
    assert snapshot["source"]["authenticated"] is True
    assert snapshot["source"]["history_scope"] == "live_portfolio_retention_window"
    assert snapshot["http_proof"]["get_only"] is True
    assert snapshot["http_proof"]["methods"] == ["GET"]
    assert snapshot["http_proof"]["path_families"] == [
        "/portfolio/balance",
        "/portfolio/fills",
        "/portfolio/orders",
        "/portfolio/positions",
    ]
    assert snapshot["http_proof"]["mutation_count"] == 0
    assert [call[:2] for call in client.calls] == [
        ("GET", "/portfolio/balance"),
        ("GET", "/portfolio/positions"),
        ("GET", "/portfolio/orders"),
        ("GET", "/portfolio/fills"),
    ]

    serialized = json.dumps(snapshot, sort_keys=True)
    for forbidden in (
        "SECRET-TICKER",
        "secret-order",
        "secret-fill",
        "secret-user-id",
        "do_not_copy_raw_summaries",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_optional_available_balance_is_omitted_when_source_does_not_supply_it() -> None:
    snapshot = await collect_live_account_snapshot(
        client=FakeKalshiClient(include_available_balance=False),
        now=NOW,
    )

    assert snapshot["status"] == "FRESH"
    assert "available_balance_cents" not in snapshot


@pytest.mark.asyncio
async def test_any_mutation_in_client_audit_fails_closed_and_discards_account_data() -> None:
    snapshot = await collect_live_account_snapshot(
        client=FakeKalshiClient(
            injected_audit={
                "method": "POST",
                "path": "/portfolio/orders/secret-order-id",
                "path_family": "/portfolio/orders/{order_id}",
                "status_class": "2xx",
            }
        ),
        now=NOW,
    )

    assert snapshot["status"] == "ERROR"
    assert snapshot["stale"] is True
    assert snapshot["reason"] == "client_audit_violation"
    assert snapshot["balance_cents"] is None
    assert snapshot["open_positions_count"] is None
    assert snapshot["open_orders_count"] is None
    assert snapshot["historical_orders_count"] is None
    assert snapshot["http_proof"]["get_only"] is False
    assert snapshot["http_proof"]["mutation_count"] == 1
    assert "secret-order-id" not in json.dumps(snapshot)


@pytest.mark.asyncio
async def test_malformed_client_audit_entry_also_fails_closed() -> None:
    client = FakeKalshiClient()
    client.request_audit_log.append("not-a-structured-audit-entry")

    snapshot = await collect_live_account_snapshot(client=client, now=NOW)

    assert snapshot["status"] == "ERROR"
    assert snapshot["reason"] == "client_audit_violation"
    assert snapshot["http_proof"]["unexpected_path_count"] == 1
    assert snapshot["balance_cents"] is None


@pytest.mark.asyncio
async def test_optional_fill_error_never_persists_secret_bearing_exception_text() -> None:
    secret = "super-secret-api-key-value"
    snapshot = await collect_live_account_snapshot(
        client=FakeKalshiClient(fills_error=RuntimeError(f"upstream exposed {secret}")),
        now=NOW,
    )

    assert snapshot["status"] == "FRESH"
    assert snapshot["stale"] is False
    assert snapshot["reason"] == "optional_fills_unavailable"
    assert snapshot["optional_fills_status"] == "ERROR"
    assert "historical_fills_count" not in snapshot
    assert snapshot["errors"] == [
        {"stage": "fills", "code": "RUNTIME_ERROR", "retryable": False}
    ]
    assert secret not in json.dumps(snapshot)


@pytest.mark.asyncio
async def test_exact_get_transport_blocks_non_get_and_non_whitelisted_paths() -> None:
    raw = AsyncMock()
    raw.request.return_value = object()
    guard = AccountSnapshotGetOnlyTransport(raw)

    await guard.request("GET", "/portfolio/balance")
    with pytest.raises(PermissionError, match="GET_ONLY_TRANSPORT_BLOCKED_METHOD"):
        await guard.request("POST", "/portfolio/orders", json={"secret": "value"})
    with pytest.raises(PermissionError, match="GET_ONLY_TRANSPORT_BLOCKED_PATH"):
        await guard.request("GET", "/markets")
    with pytest.raises(PermissionError, match="GET_ONLY_TRANSPORT_BLOCKED_PATH"):
        await guard.request("GET", "https://evil.invalid/portfolio/balance")

    raw.request.assert_awaited_once()
    assert guard.blocked_attempts == [
        {"kind": "method", "method": "POST"},
        {"kind": "path", "method": "GET"},
        {"kind": "path", "method": "GET"},
    ]


@pytest.mark.asyncio
async def test_invalid_api_host_writes_safe_error_without_contacting_network(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "live_account_snapshot.json"
    monkeypatch.setenv("KALSHI_API_KEY_ID", "configured-id")
    monkeypatch.setenv("KALSHI_API_PRIVATE_KEY_PEM", "configured-key")
    monkeypatch.setenv("KALSHI_API_BASE", "https://evil.invalid")
    monkeypatch.setenv("KALSHI_API_VERSION", "trade-api/v2")

    snapshot = await refresh_live_account_snapshot(target, now=NOW)

    assert snapshot["status"] == "ERROR"
    assert snapshot["reason"] == "invalid_endpoint_configuration"
    assert snapshot["http_proof"]["total_requests"] == 0
    assert snapshot["errors"] == [
        {
            "stage": "credentials",
            "code": "INVALID_KALSHI_ENDPOINT",
            "retryable": False,
        }
    ]
    assert "evil.invalid" not in target.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_real_kalshi_client_is_wrapped_before_any_hermetic_transport_call(
    monkeypatch,
) -> None:
    client = KalshiClient()
    original_httpx_client = client.client
    raw = AsyncMock()

    def response_for(method, path, **kwargs):
        del kwargs
        payloads = {
            "/portfolio/balance": {"balance": 500},
            "/portfolio/positions": {"market_positions": [], "cursor": ""},
            "/portfolio/orders": {"orders": [], "cursor": ""},
            "/portfolio/fills": {"fills": [], "cursor": ""},
        }
        return httpx.Response(
            200,
            json=payloads[path],
            request=httpx.Request(method, f"https://example.invalid{path}"),
        )

    raw.request.side_effect = response_for
    raw.aclose = AsyncMock()
    client.client = raw
    monkeypatch.setattr(
        "kalshi.client.sign_request",
        lambda method, path, body="": {
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-SIGNATURE": "test",
            "KALSHI-ACCESS-TIMESTAMP": "1",
        },
    )
    try:
        snapshot = await collect_live_account_snapshot(client=client, now=NOW)
    finally:
        await original_httpx_client.aclose()

    assert snapshot["status"] == "FRESH"
    assert snapshot["http_proof"]["get_only"] is True
    assert snapshot["http_proof"]["total_requests"] == 4
    assert raw.request.await_count == 4
    assert {call.args[0] for call in raw.request.await_args_list} == {"GET"}


def test_load_live_account_env_applies_only_kalshi_whitelist(tmp_path, monkeypatch) -> None:
    for key in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "OPENROUTER_API_KEY",
        "DUMMY_LIVE_PROOF_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "KALSHI_API_KEY_ID=test-id\n"
        "KALSHI_API_PRIVATE_KEY_PEM_PATH=secrets/key.pem\n"
        "OPENROUTER_API_KEY=must-not-load\n"
        "DUMMY_LIVE_PROOF_MODE=1\n",
        encoding="utf-8",
    )

    loaded = load_live_account_env(dotenv)

    assert loaded == {
        "KALSHI_API_KEY_ID": "SET_FROM_DOTENV",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH": "SET_FROM_DOTENV",
    }
    assert "OPENROUTER_API_KEY" not in loaded
    assert "DUMMY_LIVE_PROOF_MODE" not in loaded


def test_atomic_write_and_reader_staleness_contract(tmp_path) -> None:
    target = tmp_path / "live_account_snapshot.json"
    snapshot = {
        "schema": "dummy.live_account_snapshot",
        "version": 1,
        "generated_at": NOW.isoformat(),
        "status": "FRESH",
        "stale": False,
        "reason": None,
        "execution_authority": False,
        "balance_cents": 100,
        "open_positions_count": 0,
        "open_orders_count": 0,
        "historical_orders_count": 0,
        "order_status_counts": {},
        "source": {"provider": "kalshi", "authenticated": True},
        "http_proof": {"get_only": True},
        "errors": [],
    }

    write_live_account_snapshot(snapshot, target)

    assert not list(tmp_path.glob("*.tmp"))
    loaded = read_live_account_snapshot(
        target,
        now=NOW + timedelta(minutes=1),
        max_age_seconds=300,
    )
    assert loaded is not None
    assert loaded["status"] == "FRESH"
    stale = read_live_account_snapshot(
        target,
        now=NOW + timedelta(minutes=10),
        max_age_seconds=300,
    )
    assert stale is not None
    assert stale["status"] == "STALE"
    assert stale["stale"] is True
    assert stale["reason"] == "artifact_age_exceeded"


@pytest.mark.parametrize(
    "patch",
    [
        {"schema": "wrong"},
        {"version": 2},
        {"execution_authority": True},
        {"generated_at": (NOW + timedelta(minutes=6)).isoformat()},
    ],
)
def test_reader_rejects_invalid_or_future_contract(tmp_path, patch) -> None:
    target = tmp_path / "live_account_snapshot.json"
    payload = {
        "schema": "dummy.live_account_snapshot",
        "version": 1,
        "generated_at": NOW.isoformat(),
        "status": "FRESH",
        "stale": False,
        "reason": None,
        "execution_authority": False,
        "balance_cents": 100,
        "open_positions_count": 0,
        "open_orders_count": 0,
        "historical_orders_count": 0,
        "order_status_counts": {},
        "source": {"provider": "kalshi", "authenticated": True},
        "http_proof": {"get_only": True},
        "errors": [],
        **patch,
    }
    target.write_text(json.dumps(payload), encoding="utf-8")

    assert read_live_account_snapshot(target, now=NOW) is None


def test_reader_rejects_nested_raw_or_unhashable_proof_values_without_raising(
    tmp_path,
) -> None:
    target = tmp_path / "live_account_snapshot.json"
    payload = {
        "schema": "dummy.live_account_snapshot",
        "version": 1,
        "generated_at": NOW.isoformat(),
        "status": "FRESH",
        "stale": False,
        "reason": None,
        "execution_authority": False,
        "balance_cents": 100,
        "open_positions_count": 0,
        "open_orders_count": 0,
        "historical_orders_count": 0,
        "order_status_counts": {},
        "source": {
            "provider": "kalshi",
            "authenticated": True,
            "raw_response": {"ticker": "must-not-pass"},
        },
        "http_proof": {"get_only": True, "methods": [["GET"]]},
        "errors": [],
    }
    target.write_text(json.dumps(payload), encoding="utf-8")

    assert read_live_account_snapshot(target, now=NOW) is None


def test_snapshot_source_contains_no_execution_calls() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "autonomy" / "live_account_snapshot.py"
    ).read_text(encoding="utf-8")
    assert ".create_order(" not in source
    assert ".cancel_order(" not in source
    assert "DUMMY_LIVE_PROOF" not in source
    assert "configs/caps.json" not in source
    assert "configs/live_submit.json" not in source
