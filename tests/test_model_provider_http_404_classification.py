from __future__ import annotations

import httpx

from model_router.error_classifier import (
    classify_provider_error_v2,
)


def test_404_on_models_endpoint_is_endpoint_not_found():
    request = httpx.Request("GET", "https://api.example.com/v1/models")
    response = httpx.Response(404, request=request)
    exc = httpx.HTTPStatusError("not found", request=request, response=response)
    assert classify_provider_error_v2(exc, path="/v1/models") == "ENDPOINT_NOT_FOUND"


def test_404_on_chat_completions_is_model_not_found():
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(404, request=request)
    exc = httpx.HTTPStatusError("not found", request=request, response=response)
    assert classify_provider_error_v2(exc, path="/v1/chat/completions") == "MODEL_NOT_FOUND"


def test_404_on_unknown_path_is_provider_route_not_found():
    request = httpx.Request("GET", "https://api.example.com/v1/unknown")
    response = httpx.Response(404, request=request)
    exc = httpx.HTTPStatusError("not found", request=request, response=response)
    assert classify_provider_error_v2(exc, path="/v1/unknown") == "PROVIDER_ROUTE_NOT_FOUND"


def test_401_is_provider_auth_failed():
    request = httpx.Request("GET", "https://api.example.com/v1/models")
    response = httpx.Response(401, request=request)
    exc = httpx.HTTPStatusError("unauthorized", request=request, response=response)
    assert classify_provider_error_v2(exc, path="/v1/models") == "PROVIDER_AUTH_FAILED"


def test_403_is_provider_auth_failed():
    request = httpx.Request("GET", "https://api.example.com/v1/models")
    response = httpx.Response(403, request=request)
    exc = httpx.HTTPStatusError("forbidden", request=request, response=response)
    assert classify_provider_error_v2(exc, path="/v1/models") == "PROVIDER_AUTH_FAILED"


def test_429_is_provider_rate_limited():
    request = httpx.Request("GET", "https://api.example.com/v1/models")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    assert classify_provider_error_v2(exc, path="/v1/models") == "PROVIDER_RATE_LIMITED"


def test_timeout_is_provider_timeout():
    exc = httpx.TimeoutException("timed out")
    assert classify_provider_error_v2(exc, path="/v1/models") == "PROVIDER_TIMEOUT"


def test_network_error_is_provider_network_error():
    exc = httpx.ConnectError("connection failed")
    assert classify_provider_error_v2(exc, path="/v1/models") == "PROVIDER_NETWORK_ERROR"


def test_schema_error_is_provider_schema_error():
    from model_router.error_classifier import ProviderResponseSchemaError

    exc = ProviderResponseSchemaError("missing key")
    assert classify_provider_error_v2(exc, path="/v1/chat/completions") == "PROVIDER_SCHEMA_ERROR"
