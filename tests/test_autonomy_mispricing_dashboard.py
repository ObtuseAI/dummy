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


def test_dashboard_renders_the_lattice_conviction_counts():
    # WS-5: renderMispricing gets two small counts (structural, cross_confirmed)
    # alongside the existing scanned/shortlist/opportunist-strikes meta line.
    from autonomy.dashboard import _HTML

    assert "structural_count" in _HTML
    assert "cross_confirmed_count" in _HTML


# -- WS-8: CLV per specialist surfaces in the mispricing panel -----------------

def test_dashboard_exposes_clv_report(tmp_path):
    (tmp_path / "clv_report.json").write_text(
        json.dumps({
            "report_name": "AUTONOMY_CLV",
            "graded_entries": 3,
            "scopes": {
                "mlb|winner": {
                    "specialist": "mlb", "market_type": "winner",
                    "n_entries": 3, "n_event_clusters": 2,
                    "clv_bps_mean": 1200.0,
                    "clv_bps_ci95_lower": 400.0, "clv_bps_ci95_upper": 2000.0,
                },
            },
        }),
        encoding="utf-8",
    )
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    clv = state["clv_report"]
    assert clv["graded_entries"] == 3
    assert clv["scopes"]["mlb|winner"]["clv_bps_mean"] == 1200.0


def test_missing_clv_report_yields_empty_block(tmp_path):
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["clv_report"] == {}


def test_dashboard_renders_the_clv_panel():
    # WS-8: renderMispricing gains the CLV-per-specialist table.
    from autonomy.dashboard import _HTML

    assert "renderMispricing(d.mispricing_monitor" in _HTML
    assert "clv_report" in _HTML
    assert "clv_bps_mean" in _HTML
