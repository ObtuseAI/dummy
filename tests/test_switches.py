"""Wave-35: operator control switches -- main / crypto / sports-by-league /
LLM-backend, with env overrides and fail-safe-on defaults."""
from __future__ import annotations

import json

from autonomy.ontology import MarketView, Vertical
from autonomy.switches import Switches


def _write(tmp_path, data):
    p = tmp_path / "switches.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _market(ticker, vertical):
    return MarketView(ticker=ticker, title=ticker, vertical=vertical, status="active",
                      close_time="2026-07-20T00:00:00Z", yes_bid=50, yes_ask=52,
                      no_bid=48, no_ask=50, volume=1, liquidity=10)


def test_defaults_are_all_on_except_cli_llm(tmp_path):
    s = Switches.load(tmp_path / "absent.json")   # missing -> fail-safe defaults
    assert s.main_enabled() and s.crypto_enabled() and s.sports_enabled()
    assert s.league_enabled("mlb") is True
    assert s.llm_enabled("openrouter") is True
    assert s.llm_enabled("claude") is False and s.llm_enabled("codex") is False


def test_file_values_read_through(tmp_path):
    p = _write(tmp_path, {"main": True, "crypto": False, "sports": True,
                          "leagues": {"mlb": False, "nfl": True},
                          "llm": {"openrouter": False, "claude": True}})
    s = Switches.load(p)
    assert s.crypto_enabled() is False
    assert s.league_enabled("mlb") is False and s.league_enabled("nfl") is True
    assert s.llm_enabled("openrouter") is False and s.llm_enabled("claude") is True


def test_env_overrides_file(tmp_path, monkeypatch):
    p = _write(tmp_path, {"crypto": True, "sports": True, "leagues": {"nfl": True}})
    monkeypatch.setenv("DUMMY_CRYPTO_ENABLED", "0")
    monkeypatch.setenv("DUMMY_SPORTS_NFL_ENABLED", "0")
    s = Switches.load(p)
    assert s.crypto_enabled() is False           # env beats the file
    assert s.league_enabled("nfl") is False


def test_broken_file_is_fail_safe_on(tmp_path):
    p = tmp_path / "switches.json"
    p.write_text("{ not json", encoding="utf-8")
    s = Switches.load(p)
    assert s.main_enabled() and s.crypto_enabled() and s.league_enabled("mlb")


def test_sports_off_disables_every_league(tmp_path):
    p = _write(tmp_path, {"sports": False, "leagues": {"mlb": True}})
    s = Switches.load(p)
    assert s.sports_enabled() is False and s.league_enabled("mlb") is False


def test_market_allowed_by_vertical_and_league(tmp_path):
    s = Switches.load(_write(tmp_path, {"main": True, "crypto": False, "sports": True,
                                        "leagues": {"mlb": False, "nfl": True}}))
    assert s.market_allowed(_market("KXBTC15M-26JUL18-15", Vertical.CRYPTO)) is False   # crypto off
    assert s.market_allowed(_market("KXMLBGAME-26JUL18NYYBOS-NYY", Vertical.SPORTS)) is False  # mlb off
    assert s.market_allowed(_market("KXNFLGAME-26SEP18DALNYG-DAL", Vertical.SPORTS)) is True   # nfl on


def test_main_off_blocks_everything(tmp_path):
    s = Switches.load(_write(tmp_path, {"main": False, "crypto": True, "sports": True}))
    assert s.market_allowed(_market("KXBTC15M-26JUL18-15", Vertical.CRYPTO)) is False
    assert s.main_enabled() is False


def test_llm_switch_gates_router_providers(tmp_path, monkeypatch):
    import model_router.llm_switches as ls
    monkeypatch.setattr(ls, "SWITCHES_PATH", _write(
        tmp_path, {"llm": {"openrouter": False, "claude": True, "codex": False}}))
    assert ls.llm_backend_enabled("openrouter") is False
    assert ls.llm_backend_enabled("claude") is True
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")   # env re-enables
    assert ls.llm_backend_enabled("openrouter") is True


def test_cli_provider_available_follows_backend_switch(tmp_path, monkeypatch):
    import model_router.cli_providers as cli
    import model_router.llm_switches as ls
    from model_router.config import ProviderConfig

    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/claude")  # exe present
    monkeypatch.setattr(ls, "SWITCHES_PATH", _write(tmp_path, {"llm": {"claude": False}}))
    monkeypatch.delenv("DUMMY_CLI_PROVIDERS", raising=False)
    p = cli.ClaudeCliProvider(ProviderConfig(api_base="", api_key_env="", model_name="claude-sonnet-5"))
    assert p.available is False                    # backend off
    monkeypatch.setenv("DUMMY_LLM_CLAUDE_ENABLED", "1")
    assert p.available is True                      # backend on
