"""Wave-34: Claude / Codex local-CLI router providers -- argv construction,
output extraction, and the arm gate. Subprocess is injected; nothing spawns."""
from __future__ import annotations

import asyncio
import json

from model_router.cli_providers import ClaudeCliProvider, CodexCliProvider
from model_router.config import ProviderConfig
from model_router.providers import ProviderError
from model_router.tasks import ModelTask

FORECAST = ModelTask.FORECAST_OPINION


def _cfg(model="claude-sonnet-5"):
    return ProviderConfig(api_base="", api_key_env="", model_name=model, timeout_seconds=30.0)


def _capturing_runner(canned, sink):
    async def run(argv, stdin_text, timeout):
        sink["argv"] = argv
        sink["stdin"] = stdin_text
        return canned
    return run


def test_claude_argv_pipes_prompt_on_stdin_with_model():
    sink = {}
    reply = json.dumps({"result": '{"dummy_probability": 0.61, "confidence_score": 0.7, "reasoning": "x"}'})
    p = ClaudeCliProvider(_cfg("claude-sonnet-5"), runner=_capturing_runner(reply, sink))
    p.exe_env = ""  # force which(); we only exercise _call_api's runner path below
    # Call _call_api directly with a stubbed exe path via monkeypatched _exe_path.
    p._exe_path = lambda: "claude"
    out = asyncio.run(p._call_api("Estimate this.", FORECAST, 512, 0.2))
    assert sink["argv"] == ["claude", "-p", "--output-format", "json", "--model", "claude-sonnet-5"]
    assert sink["stdin"] == "Estimate this."           # prompt on stdin, not argv
    # _extract unwrapped {"result": "<forecast json>"} -> the inner forecast JSON.
    assert json.loads(out)["dummy_probability"] == 0.61


def test_claude_extract_passes_through_plain_text():
    p = ClaudeCliProvider(_cfg())
    assert p._extract('{"dummy_probability": 0.5}') == '{"dummy_probability": 0.5}'  # not wrapped
    assert p._extract('{"result": "hello"}') == "hello"


def test_codex_argv_and_jsonl_extract():
    sink = {}
    stream = "\n".join([
        json.dumps({"type": "session", "id": "abc"}),
        json.dumps({"type": "item", "message": '{"dummy_probability": 0.4, "confidence_score": 0.6, "reasoning": "y"}'}),
    ])
    p = CodexCliProvider(_cfg("gpt-5-codex"), runner=_capturing_runner(stream, sink))
    p._exe_path = lambda: "codex"
    out = asyncio.run(p._call_api("Estimate.", FORECAST, 512, 0.2))
    assert sink["argv"] == ["codex", "exec", "--json", "-m", "gpt-5-codex", "Estimate."]
    assert sink["stdin"] is None                       # codex takes the prompt as an arg
    assert json.loads(out)["dummy_probability"] == 0.4


def test_available_is_gated_by_env_and_executable(tmp_path, monkeypatch):
    import model_router.cli_providers as cli
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)  # nothing on PATH
    exe = tmp_path / "claude.exe"
    exe.write_text("")
    monkeypatch.setenv("DUMMY_CLAUDE_CLI_PATH", str(exe))
    p = ClaudeCliProvider(_cfg())
    monkeypatch.delenv("DUMMY_CLI_PROVIDERS", raising=False)
    assert p.available is False                         # executable present but not armed
    monkeypatch.setenv("DUMMY_CLI_PROVIDERS", "1")
    assert p.available is True                          # armed + present
    monkeypatch.setenv("DUMMY_CLAUDE_CLI_PATH", str(tmp_path / "gone.exe"))
    assert p.available is False                         # armed but executable missing


def test_call_raises_when_executable_missing(monkeypatch):
    p = ClaudeCliProvider(_cfg())
    p._exe_path = lambda: None
    try:
        asyncio.run(p._call_api("x", FORECAST, 512, 0.2))
        raised = False
    except ProviderError:
        raised = True
    assert raised


def test_router_registers_cli_providers():
    from model_router.router import _PROVIDER_CLASSES
    assert _PROVIDER_CLASSES["claude_cli"] is ClaudeCliProvider
    assert _PROVIDER_CLASSES["codex_cli"] is CodexCliProvider
