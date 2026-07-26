from __future__ import annotations

from autonomy.dashboard_market_observer import read_market_chart
from autonomy.market_observer.artifacts import ContentAddressedArtifactStore
from scripts.generate_dummy_crypto_chart_demo import build_demo_observation


def test_synthetic_chart_demo_is_valid_artifact_only_and_authority_free(tmp_path):
    now_s = 2_000_000_000.0
    envelope = build_demo_observation("BTC", "1h", now_s=now_s, bar_count=64)
    ContentAddressedArtifactStore(tmp_path).write_observation(envelope)

    payload = read_market_chart(tmp_path, "BTC", "1h", now_s=now_s)

    assert payload["available"] is True
    assert payload["time_status"] == "FRESH"
    assert payload["source"]["provider"] == "dummy-synthetic-release-demo"
    assert len(payload["chart_bundle"]["candles"]) == 64
    assert payload["warnings"][0].startswith("SYNTHETIC DEMO")
    assert all(value is False for value in payload["authority"].values())
