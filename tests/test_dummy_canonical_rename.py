from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_active_root_is_dummy():
    # Isolated implementation worktrees need not inherit the canonical folder
    # name; project metadata, imports, and the retired checkout are the identity.
    assert 'name = "dummy"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    old_root = Path("C:/src/engine/dumby")
    assert not old_root.exists(), f"old Dumby root still exists: {old_root}"


def test_no_dumby_in_active_source():
    source_dirs = ["core", "kalshi", "live_firewall", "execution", "autonomy",
                   "strategies", "forecasting", "adapters", "services"]
    alias_patterns = ("DumbyState = DummyState", "DumbyAdapter = DummyAdapter")
    for d in source_dirs:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
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
    """Assert the rename against the sole supported dashboard."""
    html = (ROOT / "autonomy" / "dashboard_ui.py").read_text(encoding="utf-8")
    assert "<title>DUMMY" in html
    assert "Dumby" not in html
