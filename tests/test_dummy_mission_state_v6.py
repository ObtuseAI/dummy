from __future__ import annotations

import json


def test_dummy_mission_state_v6_summarizes_v20_source_universe_without_execution() -> None:
    from predator_mesh.v20.mission import DummyMissionStateV6

    report = DummyMissionStateV6().to_report()

    assert report["verdict"] == "PARTIAL"
    assert report["v17_truth_loop_status"] == "PASS"
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["source_universe_status"] == "PASS"
    assert report["real_vs_fixture_split"]["real_read_only"] == 0


def test_generate_v20_reports_promotes_final_report_json(tmp_path, monkeypatch) -> None:
    from archive.report_scripts import generate_v20_reports as generator

    monkeypatch.setattr(generator, "ARTIFACTS", tmp_path)
    (tmp_path / "final_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-03T00:00:00+00:00",
                "milestone": "OLDER_MILESTONE",
                "verdict": "PASS",
                "v19": {"verdict": "PARTIAL"},
            }
        ),
        encoding="utf-8",
    )

    final = generator.main()
    top_level = json.loads((tmp_path / "final_report.json").read_text(encoding="utf-8"))

    assert final["verdict"] == "PARTIAL"
    assert top_level["milestone"] == generator.MILESTONE
    assert top_level["v20"]["final_report_v20"].endswith("final_report_v20.json")
    assert top_level["previous_final_report_snapshot"]["milestone"] == "OLDER_MILESTONE"
    assert top_level["v19"]["verdict"] == "PARTIAL"

