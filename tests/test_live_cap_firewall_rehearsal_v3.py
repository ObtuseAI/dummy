import pytest


@pytest.mark.asyncio
async def test_live_cap_firewall_rehearsal_report_v3():
    from archive.report_scripts.generate_v6_reports import generate_live_cap_firewall_rehearsal_report_v3
    report = await generate_live_cap_firewall_rehearsal_report_v3()
    assert report["verdict"] == "PASS"
    assert report["verdict_scope"] == "LOCAL_SAFETY_REHEARSAL_ONLY"
    assert report["execution_ready"] is False
    assert report["live_submitted"] is False
    assert report["live_submit_enabled"] is False
    assert report["mandatory_submit_gate_blocked"] is True
    assert report["mandatory_submit_rejected_by"] == "autonomy_risk_state"
    assert report["model_influence_attestation_verified"] is True
    assert (
        report["model_influence_attestation_reason"]
        == "quant_only_probability_attested"
    )
    block_tests = report.get("block_tests", {})
    assert block_tests["missing_model_influence_attestation"] is True
    assert (
        report["block_reasons"]["missing_model_influence_attestation"]
        == "model_influence_attestation_missing"
    )
    assert report["broker_contacted"] is False
    assert report["client_methods_called"] == []
    assert report["no_adapter_or_broker_call"] is True
    assert report["fresh_sink_checks_required"] is True
    assert all(block_tests.values())
