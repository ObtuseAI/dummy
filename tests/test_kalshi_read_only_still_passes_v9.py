from __future__ import annotations

import pytest

from scripts.generate_v9_reports import generate_kalshi_read_only_still_passes_report_v9


@pytest.mark.asyncio
async def test_kalshi_read_only_still_passes_v9() -> None:
    report = await generate_kalshi_read_only_still_passes_report_v9()
    assert report["verdict"] in ("PASS", "SKIP")
    assert report["order_creating_endpoints_called"] == []
    assert report["write_http_methods_used"] == []
