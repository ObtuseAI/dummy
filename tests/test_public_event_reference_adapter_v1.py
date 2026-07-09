from predator_mesh.v30.adapters import AdapterRequestV1, FixtureMode, PublicEventReferenceAdapterV1
from tests.v30_test_helpers import assert_v30_report_named


def test_public_event_reference_adapter_v1_normalizes_open_reference_fixture() -> None:
    adapter = PublicEventReferenceAdapterV1()
    response = adapter.fetch(
        AdapterRequestV1(
            adapter_id=adapter.adapter_id,
            market_class="FINANCE_MACRO_RELEASE",
            metric="cpi_yoy",
            target={"release": "CPI", "period": "2026-06"},
            fixture_id="macro_cpi_reference_fixture",
            mode=FixtureMode.CACHED_PUBLIC_RESPONSE,
        )
    )

    packet = response.to_evidence_packet()
    assert response.value == 3.1
    assert response.settlement_role == "PUBLIC_EVENT_REFERENCE_SETTLEMENT"
    assert packet.evidence_class == "CACHED_PUBLIC_ELIGIBLE"
    assert packet.live_observation_eligible is False
    assert packet.context_only_claimed_edge is False


def test_public_event_reference_adapter_v1_report_contract() -> None:
    report = assert_v30_report_named("public_event_reference_adapter_v1_report.json", "public_event_adapter_status")
    assert report["public_event_adapter_status"] == "PASS"
    assert report["private_or_paywalled_source_used"] is False
