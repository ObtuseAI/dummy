from __future__ import annotations

import os
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("PYTHONPATH", str(_PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _isolated_evidence_root(monkeypatch, tmp_path):
    """Route second-proof evidence dirs to tmp so tests never write into the
    real artifacts/dummy tree (which preserves real proof evidence)."""
    monkeypatch.setenv("DUMMY_EVIDENCE_ROOT", str(tmp_path / "evidence"))
    # Keep the daemon's alert path (which opens the real ledger) out of unit
    # tests; alert logic is covered directly in test_autonomy_alerts.
    monkeypatch.setenv("DUMMY_DAEMON_ALERTS", "0")


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
