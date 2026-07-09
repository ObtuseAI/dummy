from predator_mesh.v30.adapters import AdapterRequestV1, FixtureMode, KalshiReadonlyRuleAdapterV1
from tests.v30_test_helpers import assert_v30_report_named


def test_kalshi_readonly_rule_adapter_v1_preserves_ambiguous_rule_blocker() -> None:
    adapter = KalshiReadonlyRuleAdapterV1()
    response = adapter.fetch(
        AdapterRequestV1(
            adapter_id=adapter.adapter_id,
            market_class="KALSHI_MAPPED_MARKET",
            metric="settlement_rule_text",
            target={"ticker": "KXDEMO-RULE"},
            fixture_id="kalshi_ambiguous_rule_fixture",
            mode=FixtureMode.REPLAY_FIXTURE,
        )
    )

    packet = response.to_evidence_packet()
    assert response.blocker == "SETTLEMENT_AMBIGUOUS"
    assert response.settlement_compatible is False
    assert packet.live_score_eligible is False
    assert packet.ambiguous_settlement_scored is False
    assert response.private_endpoint_used is False


def test_kalshi_readonly_rule_adapter_v1_report_contract() -> None:
    report = assert_v30_report_named("kalshi_readonly_rule_adapter_v1_report.json", "kalshi_rule_adapter_status")
    assert report["kalshi_rule_adapter_status"] == "PASS_WITH_AMBIGUITY_BLOCKER"
    assert report["read_only_only"] is True
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
