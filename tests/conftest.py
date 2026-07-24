from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("PYTHONPATH", str(_PROJECT_ROOT))
# Historical dashboard endpoint tests exercise the explicit archive surface.
# Production imports omit all V3-V304 routers unless this exact test/dev mode
# is selected before dashboard.backend.main is imported.
os.environ.setdefault("DUMMY_DASHBOARD_ARCHIVE_SURFACE", "test-only")

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
def _paid_model_provider_network_interlock(monkeypatch):
    """Block real paid-provider HTTP transports throughout ordinary pytest.

    Tests may still use ``httpx.MockTransport`` or replace ``AsyncClient`` with
    a local double.  A missed mock cannot reach OpenRouter or either official
    legacy provider host, even when the real project ``.env`` contains a key.
    """

    import httpx

    from model_router.network_capability import APPROVED_MODEL_PROVIDER_HTTPS_HOSTS

    original_send = httpx.AsyncClient.send

    async def guarded_send(client, request, *args, **kwargs):
        host = (request.url.host or "").lower().rstrip(".")
        if host in APPROVED_MODEL_PROVIDER_HTTPS_HOSTS:
            transport = getattr(client, "_transport", None)
            if not isinstance(transport, httpx.MockTransport):
                raise RuntimeError(
                    "pytest paid-model-provider network interlock blocked real transport"
                )
        return await original_send(client, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)


@pytest.fixture
def model_network_capability():
    """Explicit capability for tests that already install a local HTTP double.

    The autouse transport interlock remains active, so requesting this fixture
    without a mock transport still cannot contact a paid provider.
    """

    from model_router.network_capability import issue_model_network_capability

    return issue_model_network_capability(
        allow_live=True,
        source="pytest.mocked_model_provider",
    )


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
    # A PredatorBrain created without an explicit board_path otherwise writes
    # its fixture cycle into runtime/autonomy/bet_board.json.  That production
    # artifact feeds the desktop daily guide, so one integration test could
    # replace thousands of fresh markets with a one-row synthetic board.
    from autonomy import bet_board as bet_board_module

    monkeypatch.setattr(
        bet_board_module,
        "BOARD_PATH",
        tmp_path / "runtime" / "autonomy" / "bet_board.json",
    )
    # The sports history lake defaults to runtime/autonomy/sports_history.db.
    # Any component that opens it WITHOUT an injected store (the sports signals'
    # lazy ``SportsHistoryStore()`` default, adapter warmups) would otherwise
    # read/write the LIVE ~95 MB lake. A concurrent lake writer (the DummyTune
    # scheduled task) can then hold its write lock long enough to hang a test to
    # timeout (observed in history_store.upsert_games). Point the default at an
    # isolated tmp DB so no test ever touches -- or is blocked by -- the
    # production lake. Tests that need real fixtures still inject their own store.
    from autonomy.sports import history_store as _history_store

    monkeypatch.setattr(
        _history_store, "DEFAULT_PATH", tmp_path / "sports_history.db")


@pytest.fixture(autouse=True)
def _isolated_runtime_risk_state(monkeypatch, tmp_path):
    """Never let tests mutate the production risk/safety state singleton.

    Some legacy modules import ``STATE`` directly instead of resolving it
    through ``core.state`` at call time. Patch both the canonical module and
    every already-imported alias that still points at the production object.
    Modules imported later receive the already-patched canonical singleton.
    The isolated state still uses real atomic persistence so restart behavior
    remains exercised rather than being mocked away.
    """
    monkeypatch.setenv(
        "DUMMY_RISK_STATE_PATH",
        str(tmp_path / "runtime" / "risk_state.json"),
    )
    monkeypatch.setenv(
        "DUMMY_EXPOSURE_STATE_PATH",
        str(tmp_path / "runtime" / "live_exposure_state.json"),
    )
    monkeypatch.setenv(
        "DUMMY_AUTONOMY_RISK_STATE_PATH",
        str(tmp_path / "runtime" / "autonomy_risk_state.json"),
    )
    monkeypatch.setenv(
        "DUMMY_AUTONOMY_LIVE_RISK_STATE_PATH",
        str(tmp_path / "runtime" / "autonomy_risk_state_live.json"),
    )

    from core import state as state_module

    production_state = state_module.STATE
    isolated_state = state_module.DummyState(
        persist=True,
        state_path=tmp_path / "runtime" / "risk_state.json",
    )
    monkeypatch.setattr(state_module, "STATE", isolated_state)

    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            imported_state = getattr(module, "STATE")
        except (AttributeError, RuntimeError):
            continue
        if imported_state is production_state:
            monkeypatch.setattr(module, "STATE", isolated_state)

    yield isolated_state


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

    fake = tmp_path / "no_env_here"
    monkeypatch.setattr(cred, "PROJECT_ENV_PATH", fake)
    # Reset module-level caches if any resolver instances reuse them.
    monkeypatch.setattr(cred, "PROJECT_ROOT", tmp_path)
    yield fake
