"""The dashboard exposes the mispricing-monitor evidence + scheduler role."""
from __future__ import annotations

import json

from autonomy.dashboard import MISPRICING_TASK_NAME, assemble_dashboard_state


def test_dashboard_exposes_mispricing_monitor(tmp_path):
    (tmp_path / "mispricing_monitor_latest.json").write_text(
        json.dumps({
            "generated_at": "2026-07-12T00:00:00+00:00",
            "scanned": 5, "assessed": 4, "shortlist_count": 2, "opportunity_count": 1,
            "shortlist": [{"ticker": "KXX", "side": "YES", "edge": 0.10}],
            "opportunities": [{"ticker": "KXG", "side": "YES", "edge": 0.12}],
        }),
        encoding="utf-8",
    )
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    monitor = state["mispricing_monitor"]
    assert monitor["shortlist_count"] == 2
    assert monitor["opportunity_count"] == 1
    assert monitor["shortlist"][0]["ticker"] == "KXX"


def test_dashboard_fleet_includes_the_monitor_role(tmp_path):
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    roles = [row["role"] for row in state["scheduler_fleet"]]
    assert "mispricing monitor" in roles
    assert MISPRICING_TASK_NAME == "DummyMispricingMonitor"


def test_missing_monitor_file_yields_empty_block(tmp_path):
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["mispricing_monitor"] == {}
