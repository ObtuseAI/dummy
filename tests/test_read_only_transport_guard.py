import pytest

from core.read_only_transport_guard import ReadOnlyTransportGuard


class FakeAsyncClient:
    async def request(self, method: str, path: str, **kwargs):
        return {"method": method, "path": path, "kwargs": kwargs}


@pytest.mark.asyncio
async def test_get_allowed():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    result = await guard.request("GET", "/markets")
    assert result["method"] == "GET"
    assert result["path"] == "/markets"
    assert guard.blocked_attempts == []


@pytest.mark.asyncio
async def test_head_allowed():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    result = await guard.request("HEAD", "/markets/FOO")
    assert result["method"] == "HEAD"
    assert guard.blocked_attempts == []


@pytest.mark.asyncio
async def test_post_blocked():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    with pytest.raises(RuntimeError, match="POST"):
        await guard.request("POST", "/portfolio/orders")
    assert len(guard.blocked_attempts) == 1
    assert guard.blocked_attempts[0]["method"] == "POST"


@pytest.mark.asyncio
async def test_put_blocked():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    with pytest.raises(RuntimeError, match="PUT"):
        await guard.request("PUT", "/portfolio/orders/123")
    assert guard.blocked_attempts[0]["method"] == "PUT"


@pytest.mark.asyncio
async def test_patch_blocked():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    with pytest.raises(RuntimeError, match="PATCH"):
        await guard.request("PATCH", "/portfolio/orders/123")
    assert guard.blocked_attempts[0]["method"] == "PATCH"


@pytest.mark.asyncio
async def test_delete_blocked():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    with pytest.raises(RuntimeError, match="DELETE"):
        await guard.request("DELETE", "/portfolio/orders/123")
    assert guard.blocked_attempts[0]["method"] == "DELETE"


@pytest.mark.asyncio
async def test_order_submit_endpoint_blocked():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    with pytest.raises(RuntimeError, match="POST"):
        await guard.request("POST", "/portfolio/orders")
    assert guard.blocked_attempts[0]["path"] == "/portfolio/orders"


@pytest.mark.asyncio
async def test_cancel_endpoint_blocked():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    with pytest.raises(RuntimeError, match="DELETE"):
        await guard.request("DELETE", "/portfolio/orders/abc-123")
    assert guard.blocked_attempts[0]["path"] == "/portfolio/orders/abc-123"


@pytest.mark.asyncio
async def test_blocked_attempts_recorded_across_calls():
    guard = ReadOnlyTransportGuard(client=FakeAsyncClient())
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(RuntimeError):
            await guard.request(method, "/portfolio/orders")
    assert len(guard.blocked_attempts) == 4
    assert {a["method"] for a in guard.blocked_attempts} == {"POST", "PUT", "PATCH", "DELETE"}
