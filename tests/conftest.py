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
#
# This probe used to be ``(artifacts/dummy).exists()``, which made the whole
# suite ORDER-DEPENDENT (2026-07-24 audit, HIGH): the directory was created as
# an import side effect of the report generators, so a fresh worktree passed on
# run 1 (everything skipped) and reported 281 failures on run 2 (everything
# un-skipped against an empty directory). The import-time creation is fixed at
# the source, but the probe itself must also be unfalsifiable: it now looks for
# the historical *milestone* reports (323 of them on the workstation), which no
# test writes -- a full traced suite run writes 24 distinct files under
# artifacts/dummy and not one of them matches final_report_v*.json.
_EVIDENCE_DIR = _PROJECT_ROOT / "artifacts" / "dummy"
_WORKSTATION_EVIDENCE = (
    _EVIDENCE_DIR.is_dir()
    and any(_EVIDENCE_DIR.glob("final_report_v*.json"))
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


@pytest.fixture
def isolated_report_artifacts(monkeypatch, tmp_path):
    """Point every loaded report generator's ``ARTIFACTS`` at a tmp directory.

    Opt-in, deliberately NOT autouse.  The workstation-only governance tests
    legitimately *read* historical milestone evidence out of the real
    artifacts/dummy tree (250 reads from these very modules in one subset run),
    so a blanket redirect would break them.  This fixture exists for the tests
    that *write*: an orchestrator test would patch only the top module's
    ``ARTIFACTS`` while the sub-generators it calls kept their own module-level
    constant and wrote live governance evidence anyway.

    Returns the tmp directory so a test can assert on what was written.
    """
    real = _PROJECT_ROOT / "artifacts" / "dummy"
    target = tmp_path / "artifacts" / "dummy"
    target.mkdir(parents=True, exist_ok=True)
    # The V8 orchestrator imports its sub-generators lazily, inside main(), so
    # they are not necessarily in sys.modules yet when this fixture runs.
    # Import them up front; they are exactly the modules that used to escape a
    # test's isolation and write live evidence.
    import importlib

    for name in (
        "generate_v8_reports",
        "generate_v8_firewall_reports",
        "generate_v8_identity_reports",
        "generate_v8_kalshi_reports",
        "generate_v8_model_provider_reports",
        "generate_v8_rehearsal_reports",
    ):
        importlib.import_module(f"archive.report_scripts.{name}")
    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            artifacts = getattr(module, "ARTIFACTS")
        except (AttributeError, RuntimeError):
            continue
        if isinstance(artifacts, Path) and Path(artifacts) == real:
            monkeypatch.setattr(module, "ARTIFACTS", type(artifacts)(target))
    return target


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
    # The watchdog's scheduler inventory shells out to schtasks; unit tests
    # must stay hermetic (and deterministic off the canonical workstation).
    monkeypatch.setenv("DUMMY_WATCHDOG_INVENTORY", "0")
    # The cycle's watchdog-staleness alert reads the real runtime status file;
    # unit tests run from the repo root and must not see live fleet state.
    monkeypatch.setenv("DUMMY_WATCHDOG_STALE_ALERT", "0")
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
    # core.logger's JsonlHandler appends to the REAL logs/dummy.jsonl -- the
    # live 16 MB telemetry tape that DummyLogRotation bounds -- for every log
    # line any test triggers.  The handler resolves LOG_FILE at emit time, so
    # redirecting the module attribute is enough.
    from core import logger as _logger
    from core.evidence_dir import EvidencePath

    monkeypatch.setattr(
        _logger, "LOG_FILE", EvidencePath(tmp_path / "logs" / "dummy.jsonl"))
    # The enforced daily LLM spend ledger.  Parts of the suite open the live
    # model gate against a mocked transport and a reservation is never refunded
    # when the call "fails", so a plain pytest run charged the operator's real
    # budget -- and a polluted ledger later refuses real calls (fail-closed).
    monkeypatch.setenv(
        "DUMMY_LLM_SPEND_STATE_PATH",
        str(tmp_path / "runtime" / "autonomy" / "llm_spend_budget.json"),
    )
    # SeasonMonitor -- and every sports signal that default-constructs one
    # instead of injecting a stub -- persists to the RELATIVE path
    # runtime/autonomy/season_state.json, i.e. the live file, because pytest
    # runs from the repo root.
    _season_state = tmp_path / "runtime" / "autonomy" / "season_state.json"

    from autonomy import scope_analytics as _scope_analytics
    from autonomy.specialists import seasons as _seasons

    monkeypatch.setattr(_seasons, "STATE_PATH", _season_state)
    monkeypatch.setattr(_scope_analytics, "_SEASON_STATE_PATH", _season_state)
    # Same story for the remaining relative runtime/autonomy artifacts a test
    # can rewrite in place (the audit's "artifacts/dummy" leak had siblings).
    from autonomy import backtest as _backtest
    from autonomy import exit_advisor as _exit_advisor
    from autonomy import matchup_lens as _matchup_lens
    from autonomy import top_threat as _top_threat
    from autonomy.market_pressure.splits import service as _splits

    _runtime_autonomy = tmp_path / "runtime" / "autonomy"
    for _module, _attr, _leaf in (
        (_backtest, "RECAL_OOS_DELTA_PATH", "recal_oos_delta.json"),
        (_exit_advisor, "EXIT_ARTIFACT_PATH", "exit_advisories.json"),
        (_matchup_lens, "REPORT_PATH", "matchup_report.json"),
        (_matchup_lens, "RECAL_PATH", "last_recalibration.json"),
        (_matchup_lens, "BOARD_PATH", "bet_board.json"),
        (_top_threat, "REPORT_PATH", "top_threat.json"),
        (_splits, "CACHE_DIR", "splits_cache"),
        (_splits, "ARCHIVE_DIR", "splits_archive"),
    ):
        monkeypatch.setattr(_module, _attr, _runtime_autonomy / _leaf)
    # A public-data Fetcher built without an explicit cache_dir filled the LIVE
    # ingest cache (and created it) straight from unit tests.
    from autonomy.ingest import fetcher as _fetcher

    monkeypatch.setattr(
        _fetcher, "DEFAULT_CACHE_DIR", _runtime_autonomy / "ingest_cache")
    # Sports signals resolve their model/warm-state directory from this module
    # constant when no model_dir is injected; PowerRatingsSignal persists a
    # degraded-streak counter there, i.e. into the LIVE runtime/autonomy.
    from autonomy.signals import sports_intelligence as _sports_intelligence

    monkeypatch.setattr(_sports_intelligence, "MODEL_DIR", _runtime_autonomy)
    # The operator activation tool writes a REAL operator approval file from a
    # repo-root-relative path, and three test modules drive that command.
    # Patched here rather than imported: the tool is heavy and only those
    # modules load it (they do so at collection, so it is in sys.modules by
    # the time any test body runs).
    _ofc = sys.modules.get(
        "tools.operator_authority_appliance.operator_full_completion")
    if _ofc is not None:
        monkeypatch.setattr(
            _ofc,
            "SECOND_PROOF_APPROVAL_PATH",
            tmp_path / "runtime" / "approvals"
            / "dummy_second_controlled_real_broker_proof_approval.json",
        )


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
