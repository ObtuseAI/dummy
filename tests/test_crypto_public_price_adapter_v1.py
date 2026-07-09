from predator_mesh.v30.adapters import AdapterRequestV1, CryptoPublicPriceAdapterV1, FixtureMode
from tests.v30_test_helpers import assert_v30_report_named


def test_crypto_public_price_adapter_v1_normalizes_price_and_single_source_consensus() -> None:
    adapter = CryptoPublicPriceAdapterV1()
    response = adapter.fetch(
        AdapterRequestV1(
            adapter_id=adapter.adapter_id,
            market_class="CRYPTO_PRICE_THRESHOLD",
            metric="btc_usd",
            target={"symbol": "BTC/USD", "threshold": 60000},
            fixture_id="crypto_btc_usd_fixture",
            mode=FixtureMode.PUBLIC_SAMPLE_RESPONSE,
        )
    )

    assert response.value == 67250.25
    assert response.consensus_status == "SINGLE_SOURCE_REFERENCE"
    assert response.source_ref.venue == "fixture-spot-reference"
    assert response.to_evidence_packet().evidence_class == "PUBLIC_SAMPLE_NOT_LIVE"
    assert response.to_evidence_packet().live_score_eligible is False


def test_crypto_public_price_adapter_v1_report_contract() -> None:
    report = assert_v30_report_named("crypto_public_price_adapter_v1_report.json", "crypto_adapter_status")
    assert report["crypto_adapter_status"] == "PASS"
    assert report["perps_enabled"] is False
    assert report["live_crypto_execution_enabled"] is False
    assert "SINGLE_SOURCE_REFERENCE" in report["consensus_statuses_supported"]
