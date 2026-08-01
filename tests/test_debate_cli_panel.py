"""Wave-36: plug the CLI voices into the debate -- guarantee them a panel slot
when allowed, exclude them (quota cap) otherwise; env-tunable debate breadth."""
from __future__ import annotations

from autonomy.brain import (
    DEBATE_HARD_MAX_MARKETS_PER_CYCLE,
    _debate_cli_top_k,
    _debate_top_k,
)
from autonomy.debate import _panel_configs

# Synthetic provider list (a fake router; never reads the real config) sized
# past the 5-slot panel so CLI prioritization is exercised. The extra HTTP
# names are arbitrary fillers, not live-configured providers.
_REALS = ["glm_5_2", "gpt_5_6_terra", "gpt_5_6_luna", "claude_sonnet_5",
          "extra_http_a", "extra_http_b", "claude_cli", "codex_cli"]


class _Router:
    def __init__(self, reals):
        self._reals = reals

    def available_real_providers(self):
        return list(self._reals)


def test_cli_voices_are_guaranteed_a_slot_when_allowed():
    configs = _panel_configs(_Router(_REALS), allow_cli=True)
    providers = [p for _label, p, _t in configs]
    assert len(configs) == 5
    # Without prioritization the CLIs (7th/8th) would never make the top 5.
    assert "claude_cli" in providers and "codex_cli" in providers


def test_cli_voices_excluded_when_not_allowed():
    configs = _panel_configs(_Router(_REALS), allow_cli=False)
    providers = [p for _label, p, _t in configs]
    assert "claude_cli" not in providers and "codex_cli" not in providers
    assert providers[0] == "glm_5_2"        # pure HTTP panel


def test_panel_empty_without_providers():
    assert _panel_configs(_Router([]), allow_cli=True) == []
    # Only CLI available + allowed -> the panel is CLI voices (padded across
    # temperatures when it's the only model; on the live box the OpenRouter
    # models fill the other slots, so no padding).
    only_cli = _panel_configs(_Router(["claude_cli"]), allow_cli=True)
    assert only_cli and all(p == "claude_cli" for _label, p, _t in only_cli)
    # Only CLI available but disallowed -> empty.
    assert _panel_configs(_Router(["claude_cli"]), allow_cli=False) == []


def test_debate_breadth_is_env_tunable(monkeypatch):
    monkeypatch.delenv("DUMMY_DEBATE_TOP_K", raising=False)
    monkeypatch.delenv("DUMMY_DEBATE_CLI_TOP_K", raising=False)
    assert _debate_top_k() == 1 and _debate_cli_top_k() == 1
    monkeypatch.setenv("DUMMY_DEBATE_TOP_K", "12")
    monkeypatch.setenv("DUMMY_DEBATE_CLI_TOP_K", "3")
    assert _debate_top_k() == DEBATE_HARD_MAX_MARKETS_PER_CYCLE
    assert _debate_cli_top_k() == 3
    monkeypatch.setenv("DUMMY_DEBATE_TOP_K", "junk")   # bad value -> default
    assert _debate_top_k() == 1
