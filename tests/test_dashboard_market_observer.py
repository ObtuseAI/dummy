from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from autonomy.dashboard import build_app
from autonomy.dashboard_market_observer import (
    ChartArtifactError,
    LIGHTWEIGHT_CHARTS_ASSET,
    read_market_chart,
)
from autonomy.market_observer.artifacts import ContentAddressedArtifactStore
from autonomy.market_observer.contracts import (
    CandleBar,
    ChartBundle,
    ObservationEnvelope,
    ObservationStatus,
    SourceProvenance,
    sha256_json,
)

_NOW = 2_000_000_000.0


def _chart_envelope(status: ObservationStatus) -> ObservationEnvelope:
    interval_s = 3600
    bars = []
    first_open = int(_NOW) - 40 * interval_s - 60
    for index in range(40):
        open_time_s = first_open + index * interval_s
        close = 100.0 + index
        bars.append(
            CandleBar(
                asset="BTC",
                venue="fixture",
                timeframe="1h",
                interval_s=interval_s,
                open_time_s=open_time_s,
                close_time_s=open_time_s + interval_s,
                received_at_s=_NOW,
                open=close - 1,
                high=close + 2,
                low=close - 2,
                close=close,
                volume=10,
                source="fixture-v1",
                raw_sha256=sha256_json([index, close]),
            )
        )
    bundle = ChartBundle(
        asset="BTC",
        timeframe="1h",
        generated_at_s=_NOW,
        candles=tuple(bars),
        indicators={"rsi_wilder_14": 52.5, "atr_14": 4.0},
        patterns=(
            {
                "name": "hammer",
                "direction": "up",
                "strength": 0.8,
                "bar_open_time_s": bars[-1].open_time_s,
                "bar_close_time_s": bars[-1].close_time_s,
            },
        ),
        observation_id="a" * 64,
    )
    return ObservationEnvelope(
        kind="chart_bundle",
        status=status,
        requested_at_s=_NOW - 1,
        received_at_s=_NOW,
        requested={"asset": "BTC", "timeframe": "1h", "limit": 40},
        resolved={
            "asset": "BTC",
            "timeframe": "1h",
            "venue": "fixture",
            "bar_count": 40,
            "latest_close_time_s": bars[-1].close_time_s,
        },
        source=SourceProvenance(
            provider="fixture",
            venue="fixture",
            endpoint="https://example.invalid/public",
            documentation_url="https://example.invalid/docs",
            adapter_version="fixture-v1",
            rights_identifier="fixture-rights-v1",
            terms_review_identifier="fixture-terms-review-v1",
            terms_url="https://example.invalid/terms",
            automated_use_permitted=True,
        ),
        payload={"chart_bundle": bundle.to_dict()},
        warnings=("fixture_warning",) if status is not ObservationStatus.COMPLETE else (),
    )


def test_artifact_reader_validates_complete_chart_and_false_authority(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    store.write_observation(_chart_envelope(ObservationStatus.COMPLETE))

    payload = read_market_chart(tmp_path, "BTC", "1h", now_s=_NOW)

    assert payload["available"] is True
    assert payload["artifact_status"] == "COMPLETE"
    assert payload["time_status"] == "FRESH"
    assert payload["chart_bundle"]["patterns"][0]["name"] == "hammer"
    assert payload["chart_bundle"]["indicators"]["rsi_wilder_14"] == 52.5
    assert all(value is False for value in payload["authority"].values())
    assert payload["rendering"] == {
        "library": "lightweight-charts",
        "version": "5.2.0",
        "data_provider": False,
    }


def test_partial_refresh_is_labelled_without_replacing_complete(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    complete = _chart_envelope(ObservationStatus.COMPLETE)
    store.write_observation(complete)
    partial = ObservationEnvelope(
        kind=complete.kind,
        status=ObservationStatus.PARTIAL,
        requested_at_s=_NOW + 9,
        received_at_s=_NOW + 10,
        requested=complete.to_dict()["requested"],
        resolved=complete.to_dict()["resolved"],
        source=complete.source,
        payload=complete.to_dict()["payload"],
        raw_sha256=complete.raw_sha256,
        raw_ref=complete.raw_ref,
        warnings=("limited_chart_analysis_history",),
    )
    store.write_observation(partial)

    payload = read_market_chart(tmp_path, "BTC", "1h", now_s=_NOW + 10)

    assert payload["observation_id"] == complete.observation_id
    assert payload["serving_last_complete"] is True
    assert payload["latest_refresh"]["status"] == "PARTIAL"
    assert payload["latest_refresh"]["observation_id"] == partial.observation_id


def test_reader_rejects_content_hash_tampering(tmp_path):
    store = ContentAddressedArtifactStore(tmp_path)
    path = store.write_observation(_chart_envelope(ObservationStatus.COMPLETE))
    value = json.loads(path.read_text(encoding="utf-8"))
    value["payload"]["chart_bundle"]["candles"][-1]["close"] = 999
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ChartArtifactError, match="content hash"):
        read_market_chart(tmp_path, "BTC", "1h", now_s=_NOW)


def test_dashboard_chart_endpoint_is_artifact_only_get_and_local_asset(
    tmp_path,
    monkeypatch,
):
    store = ContentAddressedArtifactStore(tmp_path)
    store.write_observation(_chart_envelope(ObservationStatus.COMPLETE))
    monkeypatch.setenv("DUMMY_MARKET_OBSERVER_ROOT", str(tmp_path))

    def _network_forbidden(*_args, **_kwargs):
        raise AssertionError("dashboard chart request attempted provider access")

    monkeypatch.setattr(
        "autonomy.market_observer.providers.CoinbasePublicCandleProvider.fetch_candles",
        _network_forbidden,
    )
    before = {
        path: path.stat().st_mtime_ns
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    client = TestClient(build_app())
    response = client.get("/api/market-observer/chart/BTC/1h")
    assert response.status_code == 200
    assert response.json()["source"]["provider"] == "fixture"
    assert client.post("/api/market-observer/chart/BTC/1h").status_code == 405
    assert {
        path: path.stat().st_mtime_ns
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == before

    asset = client.get(
        "/assets/vendor/lightweight-charts/5.2.0/"
        "lightweight-charts.standalone.production.js"
    )
    assert asset.status_code == 200
    assert hashlib.sha256(asset.content).hexdigest() == (
        "c0992580867c4912cc9385b3c2728315bcc1a76c7f1087dca908430fccdf31d7"
    )
    assert "script-src 'self' 'unsafe-inline'" in asset.headers[
        "content-security-policy"
    ]


def test_dashboard_ui_names_local_renderer_and_false_authority():
    response = TestClient(build_app()).get("/")
    assert response.status_code == 200
    assert "Crypto Research Charts" in response.text
    assert "NO PRODUCTION AUTHORITY" in response.text
    assert "no TradingView data" in response.text
    assert "lightweight-charts.standalone.production.js" in response.text
    assert LIGHTWEIGHT_CHARTS_ASSET.is_file()


def test_vendored_renderer_manifest_hashes_license_and_notice():
    vendor_root = LIGHTWEIGHT_CHARTS_ASSET.parent
    manifest = json.loads((vendor_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "lightweight-charts"
    assert manifest["version"] == "5.2.0"
    assert manifest["license"] == "Apache-2.0"
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((vendor_root / name).read_bytes()).hexdigest() == expected
    assert "Apache License" in (vendor_root / "LICENSE").read_text(encoding="utf-8")
    assert "TradingView Lightweight Charts" in (
        vendor_root / "NOTICE"
    ).read_text(encoding="utf-8")
