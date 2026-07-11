from __future__ import annotations

import os
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("PYTHONPATH", str(_PROJECT_ROOT))

# The staged-gate governance tests validate this workstation, not just the
# codebase: they assert historical report evidence under artifacts/dummy
# (gitignored) and the sibling C:\src\engine\obtuse\blunder mirror. On a
# fresh clone (CI) that evidence cannot exist, so those tests skip with an
# explicit reason instead of failing. The full suite still runs unreduced on
# the workstation.
_WORKSTATION_EVIDENCE = (
    (_PROJECT_ROOT / "artifacts" / "dummy").exists()
    and Path("C:/src/engine/obtuse/blunder").exists()
)
_WORKSTATION_ONLY = set(
    (Path(__file__).parent / "workstation_only_tests.txt")
    .read_text(encoding="utf-8")
    .split()
)


def pytest_collection_modifyitems(config, items):
    if _WORKSTATION_EVIDENCE:
        return
    marker = pytest.mark.skip(
        reason=(
            "workstation-only: requires local governance evidence "
            "(artifacts/dummy, sibling repos) absent in a fresh clone"
        )
    )
    for item in items:
        if Path(str(item.fspath)).name in _WORKSTATION_ONLY:
            item.add_marker(marker)


@pytest.fixture(autouse=True)
def _isolated_evidence_root(monkeypatch, tmp_path):
    """Route second-proof evidence dirs to tmp so tests never write into the
    real artifacts/dummy tree (which preserves real proof evidence)."""
    monkeypatch.setenv("DUMMY_EVIDENCE_ROOT", str(tmp_path / "evidence"))
    # Keep the daemon's alert path (which opens the real ledger) out of unit
    # tests; alert logic is covered directly in test_autonomy_alerts.
    monkeypatch.setenv("DUMMY_DAEMON_ALERTS", "0")
    # Same for the daemon's periodic self-recalibration (real ledger + curve).
    monkeypatch.setenv("DUMMY_DAEMON_RECAL", "0")
    # Route repo_harvester artifacts (incorporation registry, adapter plans)
    # to tmp so tests never dirty the real artifacts/repo_harvester tree.
    monkeypatch.setenv("DUMMY_HARVESTER_ROOT", str(tmp_path / "harvester"))


@pytest.fixture(autouse=True)
def _restore_whitelisted_env():
    """Undo whitelisted env refs that production helpers (e.g.
    _load_dotenv_for_one_shot) apply to os.environ mid-test, so credential
    presence in one test cannot leak into later tests."""
    from core.env_loader import ALLOWED_ENV_REFS

    before = {name: os.environ.get(name) for name in ALLOWED_ENV_REFS}
    yield
    for name, value in before.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture
def clean_env(monkeypatch):
    """Remove provider API keys from the environment for isolated tests."""
    for name in (
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def no_project_env(monkeypatch, tmp_path):
    """Point the credential resolver at a directory with no .env file."""
    import model_router.credential_source as cred

    original = cred.PROJECT_ENV_PATH
    fake = tmp_path / "no_env_here"
    monkeypatch.setattr(cred, "PROJECT_ENV_PATH", fake)
    # Reset module-level caches if any resolver instances reuse them.
    monkeypatch.setattr(cred, "PROJECT_ROOT", tmp_path)
    yield fake
