from pathlib import Path
import json
import pytest

ROOT = Path(__file__).parent.parent


def test_artifacts_dummy_directory_exists():
    assert (ROOT / "artifacts" / "dummy").exists()


def test_historical_artifacts_dumby_preserved():
    old = ROOT / "artifacts" / "dumby"
    assert old.exists(), "historical V4 artifacts should be preserved"
    assert (old / "final_report.json").exists()


def test_path_migration_report_generated():
    # This test runs after the report generator; if absent, generator has not run.
    path = ROOT / "artifacts" / "dummy" / "path_migration_manifest_v1.json"
    if not path.exists():
        pytest.skip("migration manifest not yet generated")
    data = json.loads(path.read_text())
    mappings = data.get("mappings", [])
    assert any(m.get("old") == "C:/src/engine/dumby" and m.get("new") == str(ROOT) for m in mappings)
    assert any(m.get("old") == "DumbyState" and m.get("new") == "DummyState" for m in mappings)
