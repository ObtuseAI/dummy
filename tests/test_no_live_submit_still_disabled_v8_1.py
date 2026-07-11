from __future__ import annotations

import json
from pathlib import Path

import pytest

from archive.report_scripts.generate_v8_1_reports import generate_no_live_submit_still_disabled_report_v8_1


def test_live_submit_report_passes_when_disabled(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir(parents=True)
    live_submit = configs / "live_submit.json"
    live_submit.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(
        "archive.report_scripts.generate_v8_1_reports.ROOT", tmp_path
    )

    report = generate_no_live_submit_still_disabled_report_v8_1()
    assert report["verdict"] == "PASS"
    assert report["enabled"] is False


def test_live_submit_report_fails_when_enabled(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir(parents=True)
    live_submit = configs / "live_submit.json"
    live_submit.write_text(json.dumps({"enabled": True}))
    monkeypatch.setattr(
        "archive.report_scripts.generate_v8_1_reports.ROOT", tmp_path
    )

    report = generate_no_live_submit_still_disabled_report_v8_1()
    assert report["verdict"] == "FAIL"
    assert report["enabled"] is True


def test_actual_live_submit_config_is_still_disabled():
    path = Path("C:/src/engine/dummy/configs/live_submit.json")
    if not path.exists():
        return
    data = json.loads(path.read_text())
    assert data.get("enabled") is not True, "live_submit.json must remain disabled"
