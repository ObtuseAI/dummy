from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_oil_source_blocker_names_energy_exchange_blockers() -> None:
    report = assert_v20_report("oil_source_blocker_report_v1.json", "blocked_sources")
    assert {"CL futures orderbook/trades", "Brent/ICE context"} <= set(report["blocked_sources"])
