from __future__ import annotations

from typing import Any

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v38.reports import V38ReportFactory


class RepresentativeReadOnlyTransport:
    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any]:
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 21.1}, "timestamp": "2026-07-04T12:00:00Z"}}
        if task.source_family == "crypto":
            return {"data": {"amount": "61234.12"}, "timestamp": "2026-07-04T12:00:00Z"}
        if task.source_family == "public_event":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.2, "date": "2025"}]
        raise AssertionError(f"unexpected task: {task.source_family}")


def test_v38_enabled_fake_transport_produces_real_live_public_score_chain() -> None:
    reports = V38ReportFactory(
        env=EXACT_GATE_ENV,
        enable_real_probe=True,
        real_transport=RepresentativeReadOnlyTransport(),
    ).build()
    chain = reports["v38_real_probe_evidence_score_chain_v1_report.json"]
    assert chain["probe_run_path"] == "REAL_PROBE_RUN"
    assert chain["real_probe_run_count"] > 0
    assert chain["real_evidence_count"] > 0
    assert chain["settlement_compatible_evidence_count"] > 0
    assert chain["observed_real_live_public_count"] > 0
    assert chain["real_scored_count"] > 0
    assert chain["score_mode_required"] == "OBSERVED_REAL_LIVE_PUBLIC"
    assert chain["kalshi_readonly_status"] == "READONLY_ACCESS_UNAVAILABLE"
    assert chain["kalshi_blocks_other_public_families"] is False
    assert chain["calibration_low_sample_warning"] is True
