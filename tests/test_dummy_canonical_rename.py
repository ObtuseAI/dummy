from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent


def test_active_root_is_dummy():
    assert ROOT.name == "dummy"
    old_root = Path("C:/src/engine/dumby")
    assert not old_root.exists(), f"old Dumby root still exists: {old_root}"


def test_no_dumby_in_active_source():
    source_dirs = ["core", "kalshi", "live_firewall", "execution", "dashboard/backend",
                   "strategies", "forecasting", "adapters", "services"]
    alias_patterns = ("DumbyState = DummyState", "DumbyAdapter = DummyAdapter")
    # Identity/migration files are allowed to mention the previous name.
    allowed_files = {
        ROOT / "dashboard" / "backend" / "v5_routes.py",
        ROOT / "dashboard" / "backend" / "v6_routes.py",
    }
    for d in source_dirs:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p in allowed_files:
                continue
            if p.is_file() and p.suffix in {".py", ".toml", ".md"}:
                text = p.read_text(encoding="utf-8")
                # Remove compatibility alias lines before checking for stray Dumby strings.
                cleaned = "\n".join(
                    line for line in text.splitlines()
                    if not any(a in line for a in alias_patterns)
                )
                assert "Dumby" not in cleaned, f"{p} still contains Dumby"


def test_dummy_identifiers_exist():
    from core.state import DummyState
    from adapters.base import DummyAdapter
    assert DummyState.__name__ == "DummyState"
    assert DummyAdapter.__name__ == "DummyAdapter"


def test_compatibility_aliases_exist():
    from core.state import DummyState, DumbyState
    from adapters.base import DummyAdapter, DumbyAdapter
    assert DumbyState is DummyState
    assert DumbyAdapter is DummyAdapter


def test_pyproject_name_is_dummy():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "dummy"' in text


def test_dashboard_title_is_dummy():
    html = (ROOT / "dashboard" / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Dummy Dashboard" in html
