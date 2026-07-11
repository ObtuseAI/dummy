from __future__ import annotations

import json

from archive.report_scripts.generate_v8_2_reports import (
    generate_no_provider_credential_leak_report_v1,
    generate_provider_credential_source_resolution_report_v1,
    generate_provider_route_mode_report_v1,
)


def test_no_provider_credential_leak_in_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-leak-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-leak-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret-leak-test")

    # Generate some V8.2 reports into tmp_path by patching ARTIFACTS.
    import archive.report_scripts.generate_v8_2_reports as gen
    original_artifacts = gen.ARTIFACTS
    gen.ARTIFACTS = tmp_path
    try:
        generate_provider_credential_source_resolution_report_v1()
        generate_provider_route_mode_report_v1()
        report = generate_no_provider_credential_leak_report_v1()
    finally:
        gen.ARTIFACTS = original_artifacts

    assert report["verdict"] == "PASS"
    assert report["leaked_files"] == []

    # Ensure the actual files on disk also contain no raw secrets.
    for name in report["checked_files"]:
        path = tmp_path / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "sk-deepseek-secret-leak-test" not in text
        assert "sk-minimax-secret-leak-test" not in text
        assert "sk-openrouter-secret-leak-test" not in text
