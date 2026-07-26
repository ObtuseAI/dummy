from __future__ import annotations

import io
import json
from dataclasses import FrozenInstanceError

import pytest

from autonomy.market_observer.artifacts import ContentAddressedArtifactStore
from autonomy.market_observer.contracts import (
    CandleBar,
    ChartBundle,
    ObservationEnvelope,
    ObservationStatus,
    SourceProvenance,
    canonical_json,
    sha256_json,
)
from autonomy.market_observer.providers import (
    CoinbasePublicCandleProvider,
    ProviderBatch,
    ProviderConfigurationError,
    ProviderSchemaDrift,
    ProviderUnavailable,
)
from autonomy.market_observer.runtime import (
    CircuitBreaker,
    ObserverAlreadyRunning,
    RequestRateBudget,
    SingleRunLock,
)
from autonomy.market_observer.server import (
    TOOLS,
    ObserverToolRouter,
    handle_message,
    run_stdio,
)
from autonomy.market_observer.service import MarketObserver


def _bar(
    *,
    index: int = 0,
    timeframe: str = "1h",
    interval_s: int = 3600,
    received_at_s: float = 2_000_000_000.0,
) -> CandleBar:
    open_time_s = 1_999_850_000 + index * interval_s
    close = 100.0 + index
    row = [open_time_s, close - 2, close + 2, close - 1, close, 10.0]
    return CandleBar(
        asset="BTC",
        venue="fixture",
        timeframe=timeframe,
        interval_s=interval_s,
        open_time_s=open_time_s,
        close_time_s=open_time_s + interval_s,
        received_at_s=received_at_s,
        open=close - 1,
        high=close + 2,
        low=close - 2,
        close=close,
        volume=10.0,
        source="fixture-v1",
        raw_sha256=sha256_json(row),
        provider_observed_at_s=open_time_s + interval_s,
    )


def _source() -> SourceProvenance:
    return SourceProvenance(
        provider="fixture",
        venue="fixture",
        endpoint="https://example.invalid/public",
        documentation_url="https://example.invalid/docs",
        adapter_version="fixture-v1",
        rights_identifier="fixture-rights-v1",
        terms_review_identifier="fixture-terms-review-v1",
        terms_url="https://example.invalid/terms",
        automated_use_permitted=True,
    )


def _envelope(
    status: ObservationStatus,
    *,
    received_at_s: float,
) -> ObservationEnvelope:
    return ObservationEnvelope(
        kind="candles",
        status=status,
        requested_at_s=received_at_s - 1,
        received_at_s=received_at_s,
        requested={"asset": "BTC", "timeframe": "1h", "limit": 1},
        resolved={"asset": "BTC", "timeframe": "1h"},
        source=_source(),
        payload={"candles": [_bar().to_dict()]},
    )


def test_candle_bar_is_closed_validated_and_frozen():
    bar = _bar()
    assert bar.close_time_s <= bar.received_at_s
    assert bar.closed is True
    with pytest.raises(FrozenInstanceError):
        bar.close = 999.0
    with pytest.raises(ValueError, match="not closed"):
        CandleBar(
            **{
                **bar.to_dict(),
                "open_time_s": int(bar.received_at_s) + 1 - bar.interval_s,
                "close_time_s": int(bar.received_at_s) + 1,
            }
        )
    with pytest.raises(ValueError, match="high"):
        CandleBar(**{**bar.to_dict(), "high": bar.low})


def test_observation_and_chart_contracts_are_deeply_immutable():
    envelope = ObservationEnvelope(
        kind="candles",
        status=ObservationStatus.COMPLETE,
        requested_at_s=10,
        received_at_s=11,
        requested={"asset": "BTC", "timeframe": "1h"},
        resolved={"nested": {"value": 1}},
        source=_source(),
        payload={"rows": [{"values": [1, 2]}]},
    )
    with pytest.raises(TypeError):
        envelope.payload["rows"][0]["values"][0] = 9
    assert envelope.to_dict()["authority"] == {
        "execution": False,
        "order": False,
        "cancel": False,
        "amend": False,
        "allocation": False,
        "promotion": False,
    }
    bundle = ChartBundle(
        asset="BTC",
        timeframe="1h",
        generated_at_s=2_000_000_000,
        candles=(_bar(),),
        indicators={"rsi": 50.0},
        patterns=({"name": "doji"},),
    )
    assert "probability" not in canonical_json(bundle.to_dict()).lower()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://tradingview.com/data",
        "https://data.tradingview.com/feed",
        "https://tradingview-widget.com/chart",
        "https://api.tradingview.example/feed",
    ],
)
def test_source_provenance_hard_denies_every_tradingview_domain(endpoint):
    with pytest.raises(ValueError, match="TradingView"):
        SourceProvenance(
            provider="forbidden",
            venue="forbidden",
            endpoint=endpoint,
            documentation_url="https://example.invalid/docs",
            adapter_version="forbidden-v1",
            rights_identifier="forbidden-rights",
            terms_review_identifier="forbidden-review",
            terms_url="https://example.invalid/terms",
            automated_use_permitted=True,
        )


def test_source_provenance_requires_explicit_automated_use_permission():
    with pytest.raises(ValueError, match="automated API use"):
        SourceProvenance(
            provider="fixture",
            venue="fixture",
            endpoint="https://example.invalid/public",
            documentation_url="https://example.invalid/docs",
            adapter_version="fixture-v1",
            rights_identifier="fixture-rights",
            terms_review_identifier="fixture-review",
            terms_url="https://example.invalid/terms",
            automated_use_permitted=False,
        )
    value = _source().to_dict()
    assert value["rights_identifier"] == "fixture-rights-v1"
    assert value["terms_review_identifier"] == "fixture-terms-review-v1"
    assert value["automated_use_permitted"] is True


def test_partial_failure_never_replaces_latest_complete(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    complete = _envelope(ObservationStatus.COMPLETE, received_at_s=20)
    partial = _envelope(ObservationStatus.PARTIAL, received_at_s=30)
    store.write_observation(complete)
    store.write_observation(partial)
    latest = store.read_latest("candles", "BTC", "1h")
    failure = store.read_latest("candles", "BTC", "1h", include_failure=True)
    assert latest["observation_id"] == complete.observation_id
    assert latest["status"] == "COMPLETE"
    assert failure["observation_id"] == partial.observation_id
    assert failure["status"] == "PARTIAL"


def test_read_latest_rehashes_immutable_observation_content(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    envelope = _envelope(ObservationStatus.COMPLETE, received_at_s=20)
    artifact = store.write_observation(envelope)
    tampered = json.loads(artifact.read_text(encoding="utf-8"))
    tampered["payload"]["candles"][0]["close"] += 1
    artifact.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="content hash mismatch"):
        store.read_latest("candles", "BTC", "1h")


def test_read_latest_rejects_pointer_to_other_valid_request(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    btc = _envelope(ObservationStatus.COMPLETE, received_at_s=20)
    eth = ObservationEnvelope(
        kind=btc.kind,
        status=btc.status,
        requested_at_s=btc.requested_at_s,
        received_at_s=btc.received_at_s,
        requested={"asset": "ETH", "timeframe": "1h", "limit": 1},
        resolved={"asset": "ETH", "timeframe": "1h"},
        source=btc.source,
        payload=btc.to_dict()["payload"],
        raw_sha256=btc.raw_sha256,
        raw_ref=btc.raw_ref,
        warnings=btc.warnings,
    )
    # ObservationEnvelope computes identity; it does not accept a stored ID.
    store.write_observation(btc)
    store.write_observation(eth)
    btc_pointer = tmp_path / "by_request/candles/BTC/1h/LATEST.json"
    eth_pointer = tmp_path / "by_request/candles/ETH/1h/LATEST.json"
    btc_pointer.write_text(eth_pointer.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="request identity mismatch"):
        store.read_latest("candles", "BTC", "1h")


def test_read_latest_enforces_pointer_disposition(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    envelope = _envelope(ObservationStatus.COMPLETE, received_at_s=20)
    store.write_observation(envelope)
    pointer = tmp_path / "by_request/candles/BTC/1h/LATEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value["status"] = "PARTIAL"
    pointer.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="pointer disposition"):
        store.read_latest("candles", "BTC", "1h")


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.closed = False

    def get(self, url, params=None):
        self.calls.append((url, params))
        return _Response(self.payload)

    def close(self):
        self.closed = True


def _coinbase_rows(now_s: int, hours: int = 40):
    rows = []
    for offset in range(hours, -1, -1):
        open_time_s = now_s - offset * 3600
        close = 100.0 + hours - offset
        rows.append(
            [open_time_s, close - 2, close + 2, close - 1, close, 10.0]
        )
    return list(reversed(rows))


def test_coinbase_provider_excludes_open_bar_and_aggregates_closed_history():
    now_s = 2_000_001_600  # divisible by four hours
    client = _Client(_coinbase_rows(now_s))
    provider = CoinbasePublicCandleProvider(
        client_factory=lambda: client,
        clock=lambda: now_s,
    )
    batch = provider.fetch_candles("BTC", "4h", limit=5)
    assert len(batch.candles) == 5
    assert all(bar.closed and bar.close_time_s <= now_s for bar in batch.candles)
    assert all(bar.interval_s == 4 * 3600 for bar in batch.candles)
    assert "excluded_1_open_rows" in batch.warnings
    assert all("tradingview" not in url.lower() for url, _params in client.calls)
    assert client.closed is True


def test_coinbase_provider_quarantines_conflicting_duplicate_timestamp():
    now_s = 2_000_001_600
    rows = _coinbase_rows(now_s)
    duplicate = list(rows[-1])
    duplicate[4] += 10
    duplicate[2] += 10
    client = _Client([*rows, duplicate])
    provider = CoinbasePublicCandleProvider(
        client_factory=lambda: client,
        clock=lambda: now_s,
    )
    with pytest.raises(ProviderSchemaDrift, match="conflicting duplicate"):
        provider.fetch_candles("BTC", "1h", limit=5)


@pytest.mark.parametrize(
    "base_url",
    [
        "https://tradingview.com",
        "https://data.tradingview.com",
        "https://tradingview-widget.com",
        "https://example.invalid",
        "http://api.exchange.coinbase.com",
    ],
)
def test_coinbase_provider_configuration_is_https_allowlisted(base_url):
    error = "TradingView" if "tradingview" in base_url else "allowlisted"
    with pytest.raises(ProviderConfigurationError, match=error):
        CoinbasePublicCandleProvider(base_url=base_url)


class _FixtureProvider:
    def __init__(self, bars: tuple[CandleBar, ...]):
        self.bars = bars

    def fetch_candles(self, asset, timeframe, *, limit):
        selected = self.bars[-limit:]
        return ProviderBatch(
            candles=selected,
            provenance=_source(),
            requested_at_s=2_000_000_000,
            received_at_s=2_000_000_001,
            raw_payload={"rows": [bar.to_dict() for bar in selected]},
            status=ObservationStatus.COMPLETE,
        )


class _OutcomeProvider(_FixtureProvider):
    def __init__(self, bars, outcomes):
        super().__init__(bars)
        self.outcomes = list(outcomes)
        self.calls = 0

    def fetch_candles(self, asset, timeframe, *, limit):
        self.calls += 1
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
        return super().fetch_candles(asset, timeframe, limit=limit)


def test_service_persists_facts_only_chart_bundle_and_health(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    observer = MarketObserver(
        provider=_FixtureProvider(bars),
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
    )
    envelope = observer.get_chart_bundle("BTC", "1h", limit=40)
    assert envelope.status is ObservationStatus.COMPLETE
    serialized = canonical_json(envelope.to_dict()).lower()
    assert "probability_yes" not in serialized
    assert '"execution":false' in serialized
    assert envelope.payload["chart_bundle"]["observation_id"]
    assert (tmp_path / envelope.raw_ref).exists()

    candles = observer.get_candles("BTC", "1h", limit=40)
    health = observer.source_health("BTC", "1h")
    assert health.status is ObservationStatus.COMPLETE
    assert health.payload["latest_complete"]["observation_id"] == candles.observation_id
    assert health.payload["latest_complete_fresh"] is True


def test_source_health_marks_old_complete_observation_stale(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    observer = MarketObserver(
        provider=_FixtureProvider(bars),
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
    )
    observer.get_candles("BTC", "1h", limit=40)
    observer.clock = lambda: 2_000_010_000

    health = observer.source_health("BTC", "1h")

    assert health.status is ObservationStatus.STALE
    assert health.payload["latest_complete_fresh"] is False
    assert health.payload["latest_complete_age_s"] > health.payload["stale_after_s"]
    assert "latest_complete_is_stale" in health.warnings


def test_source_health_surfaces_newer_partial_observation(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    observer = MarketObserver(
        provider=_FixtureProvider(bars),
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
    )
    observer.get_candles("BTC", "1h", limit=40)
    observer.store.write_observation(
        _envelope(ObservationStatus.PARTIAL, received_at_s=2_000_000_005)
    )
    observer.clock = lambda: 2_000_000_006

    health = observer.source_health("BTC", "1h")

    assert health.status is ObservationStatus.PARTIAL
    assert health.payload["latest_complete_fresh"] is False
    assert "newer_candle_failure_observation" in health.warnings


def test_mcp_surface_is_allowlisted_read_only_and_fail_closed(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    observer = MarketObserver(
        provider=_FixtureProvider(bars),
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
    )
    router = ObserverToolRouter(observer)
    names = {tool["name"] for tool in TOOLS}
    assert names == {
        "get_candles",
        "get_market_snapshot",
        "compute_indicators",
        "detect_candlestick_patterns",
        "get_chart_bundle",
        "get_network_metrics",
        "source_health",
    }
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in TOOLS)
    assert not any(
        forbidden in name
        for name in names
        for forbidden in ("order", "trade", "alert", "webhook", "account")
    )

    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_candles",
                "arguments": {"asset": "BTC", "timeframe": "1h", "limit": 5},
            },
        },
        router,
    )
    assert response["result"]["isError"] is False
    assert response["result"]["structuredContent"]["authority"]["order"] is False

    failed = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_candles",
                "arguments": {
                    "asset": "BTC",
                    "timeframe": "1h",
                    "private_key": "never-accepted",
                },
            },
        },
        router,
    )
    assert failed["result"]["isError"] is True
    assert failed["result"]["structuredContent"]["status"] == "UNAVAILABLE"
    assert "never-accepted" not in canonical_json(failed)


def test_mcp_router_exercises_every_facts_only_tool(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    observer = MarketObserver(
        provider=_FixtureProvider(bars),
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
    )
    router = ObserverToolRouter(observer)
    common = {"asset": "BTC", "timeframe": "1h", "limit": 40}

    snapshot, snapshot_error = router.call("get_market_snapshot", common)
    indicators, indicators_error = router.call("compute_indicators", common)
    patterns, patterns_error = router.call(
        "detect_candlestick_patterns",
        common,
    )
    bundle, bundle_error = router.call("get_chart_bundle", common)
    network, network_error = router.call(
        "get_network_metrics",
        {"asset": "BTC"},
    )
    health, health_error = router.call(
        "source_health",
        {"asset": "BTC", "timeframe": "1h"},
    )

    assert not any(
        (
            snapshot_error,
            indicators_error,
            patterns_error,
            bundle_error,
            network_error,
            health_error,
        )
    )
    assert snapshot.payload["facts_only"] is True
    assert indicators.payload["indicators"]["facts_only"] is True
    assert patterns.payload["facts_only"] is True
    assert bundle.payload["chart_bundle"]["observation_id"]
    assert network.status is ObservationStatus.UNAVAILABLE
    assert network.payload["reason"] == (
        "no_contract_reviewed_network_provider_configured"
    )
    assert health.payload["latest_complete"]["status"] == "COMPLETE"
    assert all(
        envelope.authority.execution is False
        for envelope in (snapshot, indicators, patterns, bundle, network, health)
    )


def test_mcp_protocol_rejects_invalid_messages_without_disclosure(tmp_path):
    observer = MarketObserver(
        provider=_FixtureProvider(tuple(_bar(index=index) for index in range(40))),
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
    )
    router = ObserverToolRouter(observer)

    assert handle_message("not-an-object", router)["error"]["code"] == -32600
    assert (
        handle_message(
            {"jsonrpc": "1.0", "id": 1, "method": "ping"},
            router,
        )["error"]["code"]
        == -32600
    )
    assert (
        handle_message(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            router,
        )
        is None
    )
    assert handle_message(
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        router,
    )["result"] == {}
    assert (
        handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": "not-an-object",
            },
            router,
        )["error"]["code"]
        == -32602
    )
    assert (
        handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {},
            },
            router,
        )["error"]["code"]
        == -32602
    )
    assert (
        handle_message(
            {"jsonrpc": "2.0", "id": 5, "method": "unknown"},
            router,
        )["error"]["code"]
        == -32601
    )

    output = io.StringIO()
    payload = "\n".join(
        (
            "",
            "{malformed-json",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/cancelled",
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "unknown",
                }
            ),
        )
    )
    assert (
        run_stdio(
            input_stream=io.StringIO(payload),
            output_stream=output,
            observer=observer,
        )
        == 0
    )
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [response["error"]["code"] for response in responses] == [
        -32700,
        -32601,
    ]
    assert "traceback" not in output.getvalue().lower()


def test_request_rate_budget_fails_closed_and_recovers_by_window(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    provider = _OutcomeProvider(bars, [None, None, None])
    monotonic = [100.0]
    budget = RequestRateBudget(
        max_requests=2,
        window_s=10,
        clock=lambda: monotonic[0],
    )
    observer = MarketObserver(
        provider=provider,
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
        request_budget=budget,
        circuit_breaker=CircuitBreaker(failure_threshold=5),
    )
    router = ObserverToolRouter(observer)
    arguments = {"asset": "BTC", "timeframe": "1h", "limit": 5}
    assert router.call("get_candles", arguments)[1] is False
    assert router.call("get_candles", arguments)[1] is False
    failure, is_error = router.call("get_candles", arguments)
    assert is_error is True
    assert failure.payload["error_type"] == "RequestBudgetExceeded"
    assert provider.calls == 2

    monotonic[0] += 11
    assert router.call("get_candles", arguments)[1] is False
    assert provider.calls == 3


def test_circuit_breaker_blocks_then_allows_one_recovery_probe(tmp_path):
    bars = tuple(_bar(index=index) for index in range(40))
    provider = _OutcomeProvider(
        bars,
        [
            ProviderUnavailable("down"),
            ProviderUnavailable("still down"),
            None,
        ],
    )
    monotonic = [100.0]
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_s=10,
        clock=lambda: monotonic[0],
    )
    observer = MarketObserver(
        provider=provider,
        artifact_root=tmp_path,
        clock=lambda: 2_000_000_001,
        request_budget=RequestRateBudget(max_requests=20),
        circuit_breaker=breaker,
    )
    router = ObserverToolRouter(observer)
    arguments = {"asset": "BTC", "timeframe": "1h", "limit": 5}
    assert router.call("get_candles", arguments)[1] is True
    assert router.call("get_candles", arguments)[1] is True
    blocked, is_error = router.call("get_candles", arguments)
    assert is_error is True
    assert blocked.payload["error_type"] == "CircuitBreakerOpen"
    assert provider.calls == 2
    assert breaker.snapshot()["state"] == "OPEN"

    monotonic[0] += 11
    assert router.call("get_candles", arguments)[1] is False
    assert provider.calls == 3
    assert breaker.snapshot()["state"] == "CLOSED"


def test_single_run_lock_has_exclusive_ownership_and_releases(tmp_path):
    path = tmp_path / "observer.lock"
    first = SingleRunLock(path)
    second = SingleRunLock(path)
    first.acquire()
    assert path.exists()
    with pytest.raises(ObserverAlreadyRunning, match="already running"):
        second.acquire()
    first.release()
    second.acquire()
    second.release()
    assert not path.exists()


def test_single_run_lock_reclaims_a_dead_owner_without_signalling_it(tmp_path):
    path = tmp_path / "observer.lock"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": 999_999_999,
                "token": "dead-owner",
                "created_at_s": 1,
            }
        ),
        encoding="utf-8",
    )
    lock = SingleRunLock(path)
    lock.acquire()
    lock.release()
    assert not path.exists()


def test_stdio_protocol_initializes_and_lists_tools_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_MARKET_OBSERVER_ROOT", str(tmp_path))
    requests = "\n".join(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {},
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
            ),
        ]
    )
    output = io.StringIO()
    assert run_stdio(input_stream=io.StringIO(requests), output_stream=output) == 0
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert responses[0]["result"]["serverInfo"]["name"] == "dummy-market-observer"
    assert len(responses[1]["result"]["tools"]) == 7
