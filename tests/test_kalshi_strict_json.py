from __future__ import annotations

import httpx
import pytest

from kalshi.strict_json import (
    StrictJSONResponseError,
    load_strict_json_response,
)


def _response(body: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=body,
        request=httpx.Request("GET", "https://kalshi.invalid/test"),
    )


def test_accepts_nested_strict_utf8_json() -> None:
    payload = load_strict_json_response(
        _response('{"market":{"ticker":"KX-✓"},"prices":[1,2]}'.encode())
    )

    assert payload == {
        "market": {"ticker": "KX-✓"},
        "prices": [1, 2],
    }


@pytest.mark.parametrize(
    "body",
    [
        b'{"ticker":"A","ticker":"B"}',
        b'{"market":{"ticker":"A","ticker":"B"}}',
        b'[{"ticker":"A","ticker":"B"}]',
    ],
)
def test_rejects_duplicate_keys_at_every_object_depth(body: bytes) -> None:
    with pytest.raises(StrictJSONResponseError, match="duplicate JSON key"):
        load_strict_json_response(_response(body))


@pytest.mark.parametrize(
    "token",
    ["NaN", "Infinity", "-Infinity", "1e999999"],
)
def test_rejects_non_finite_numeric_extensions(token: str) -> None:
    with pytest.raises(StrictJSONResponseError, match="non-finite"):
        load_strict_json_response(_response(f'{{"price":{token}}}'.encode()))


def test_rejects_invalid_utf8() -> None:
    with pytest.raises(StrictJSONResponseError, match="strict UTF-8 JSON"):
        load_strict_json_response(_response(b'{"ticker":"\xff"}'))


def test_rejects_response_over_explicit_byte_limit_before_decoding() -> None:
    with pytest.raises(StrictJSONResponseError, match="exceeds 7 byte limit"):
        load_strict_json_response(_response(b'{"a":1} '), maximum_bytes=7)


@pytest.mark.asyncio
async def test_kalshi_client_rejects_duplicate_response_keys(monkeypatch) -> None:
    from kalshi.client import KalshiClient

    client = KalshiClient()

    async def fake_request(*_args, **_kwargs):
        return _response(b'{"markets":[],"markets":[{"ticker":"forged"}]}')

    monkeypatch.setattr(client.client, "request", fake_request)
    monkeypatch.setattr(
        "kalshi.client.sign_request",
        lambda *_args, **_kwargs: {},
    )

    with pytest.raises(StrictJSONResponseError, match="duplicate JSON key"):
        await client.get_markets()


def test_public_reconciler_rejects_non_finite_response(monkeypatch) -> None:
    from autonomy import reconciler

    monkeypatch.setattr(
        reconciler,
        "_public_get",
        lambda *_args, **_kwargs: _response(
            b'{"market":{"ticker":"KX","last_price":NaN}}'
        ),
    )

    with pytest.raises(StrictJSONResponseError, match="non-finite"):
        reconciler.default_fetch_market_result("KX")
