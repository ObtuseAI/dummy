from __future__ import annotations

import pytest

from archive.report_scripts.generate_v8_2_reports import generate_provider_alias_probe_report_v1


@pytest.mark.asyncio
async def test_alias_probe_lists_configured_and_default_aliases():
    report = await generate_provider_alias_probe_report_v1()
    assert report["verdict"] == "PASS"
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        entry = report[provider]
        assert entry["configured_model"]
        assert len(entry["aliases_attempted"]) >= 1
        assert "config" in entry["alias_sources"] or "default" in entry["alias_sources"]
