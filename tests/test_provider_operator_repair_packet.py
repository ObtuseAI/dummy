from __future__ import annotations

import json

import pytest

from archive.report_scripts.generate_v8_2_reports import (
    generate_model_id_validation_report_v1,
    generate_provider_operator_repair_packet_v1,
)


@pytest.mark.asyncio
async def test_repair_packet_contains_no_secret_values(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-secret")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-mm-secret")

    import archive.report_scripts.generate_v8_2_reports as gen
    original_artifacts = gen.ARTIFACTS
    gen.ARTIFACTS = tmp_path
    try:
        await generate_model_id_validation_report_v1()
        report = generate_provider_operator_repair_packet_v1()
    finally:
        gen.ARTIFACTS = original_artifacts

    text = json.dumps(report, default=str)
    assert "sk-ds-secret" not in text
    assert "sk-mm-secret" not in text
    assert report["verdict"] == "PASS"
    for entry in report["packet"]:
        assert "exact_fields_to_set" in entry
        assert "example_values" in entry
        assert entry["current_route_mode"]
