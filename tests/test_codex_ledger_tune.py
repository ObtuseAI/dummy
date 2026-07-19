"""Wave-37: codex forward-compat (account default model, no -m) + env-tunable
ledger busy_timeout."""
from __future__ import annotations

from autonomy.ledger import _ledger_busy_timeout_s
from model_router.cli_providers import CodexCliProvider
from model_router.config import ProviderConfig


def test_ledger_busy_timeout_defaults_to_60_and_is_env_tunable(monkeypatch):
    monkeypatch.delenv("DUMMY_LEDGER_BUSY_TIMEOUT_S", raising=False)
    assert _ledger_busy_timeout_s() == 60.0
    monkeypatch.setenv("DUMMY_LEDGER_BUSY_TIMEOUT_S", "90")
    assert _ledger_busy_timeout_s() == 90.0
    monkeypatch.setenv("DUMMY_LEDGER_BUSY_TIMEOUT_S", "junk")   # bad -> default
    assert _ledger_busy_timeout_s() == 60.0
    monkeypatch.setenv("DUMMY_LEDGER_BUSY_TIMEOUT_S", "-5")     # non-positive -> default
    assert _ledger_busy_timeout_s() == 60.0


def test_codex_empty_model_omits_dash_m():
    # A ChatGPT-account codex rejects every -m override, so an empty model_name
    # means "let the account/CLI pick its default".
    p = CodexCliProvider(ProviderConfig(api_base="", api_key_env="", model_name=""))
    argv, stdin = p._argv("Estimate.", "codex")
    assert argv == ["codex", "exec", "--json", "Estimate."]   # no -m
    assert "-m" not in argv and stdin is None
