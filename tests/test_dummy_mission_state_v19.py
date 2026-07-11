from __future__ import annotations

import json


def test_dummy_mission_state_v19_summarizes_activation_without_execution() -> None:
    from predator_mesh.v19.mission import DummyMissionStateV19

    report = DummyMissionStateV19().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["no_direct_order_cancel_bypass"] is True


def test_generate_v19_reports_promotes_final_report_json(tmp_path, monkeypatch) -> None:
    from archive.report_scripts import generate_v19_reports as generator

    monkeypatch.setattr(generator, "ARTIFACTS", tmp_path)
    (tmp_path / "final_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-03T00:00:00+00:00",
                "milestone": "OLDER_MILESTONE",
                "verdict": "PASS",
                "v18": {"verdict": "PARTIAL"},
            }
        ),
        encoding="utf-8",
    )

    final = generator.main()
    top_level = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))

    assert final["verdict"] == "PARTIAL"
    assert top_level["milestone"] == generator.MILESTONE
    assert top_level["v19"]["final_report_v19"].endswith("final_report_v19.json")
    assert top_level["previous_final_report_snapshot"]["milestone"] == "OLDER_MILESTONE"
    assert top_level["v18"]["verdict"] == "PARTIAL"
