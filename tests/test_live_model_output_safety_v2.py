from __future__ import annotations

import pytest

from model_router.smoke import LiveModelSmokeV3


@pytest.mark.asyncio
async def test_output_safety_v2_all_safe():
    runner = LiveModelSmokeV3()
    report = await runner.generate_output_safety_report_v2()
    assert report["verdict"] == "PASS"
    for sample in report["samples"]:
        assert sample["output_firewall_safe"] is True
