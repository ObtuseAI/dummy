"""Local-CLI model providers: the Claude and Codex command-line tools as
router panelists.

The HTTP providers need an OpenRouter key; these two instead shell out to the
already-installed, already-authenticated `claude` and `codex` CLIs, so they
add frontier-model firepower to the debate WITHOUT any API key -- and keep the
LLM layer alive even when the HTTP key is absent.

Cost note: both CLIs bill the operator's PERSONAL Claude / OpenAI
subscriptions and compete with interactive use, so they are OFF by default and
gated behind DUMMY_CLI_PROVIDERS=1, throttled to a low per-process rate. Arm
them deliberately.

The subprocess call is injected (``_runner``) so argv construction and output
parsing are unit-tested without spawning anything; live invocation uses
asyncio. Any non-zero exit / timeout / unparseable output raises ProviderError
so the router falls back exactly like a failed HTTP call.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from typing import Any, Awaitable, Callable

from model_router.config import ProviderConfig
from model_router.providers import BaseModelProvider, ProviderError
from model_router.tasks import ModelTask

CLI_GATE_ENV = "DUMMY_CLI_PROVIDERS"
# A floor between calls per process, so an armed panel can't machine-gun the
# personal subscription. Tunable via DUMMY_CLI_MIN_INTERVAL (seconds).
DEFAULT_MIN_INTERVAL = 3.0
MIN_INTERVAL_ENV = "DUMMY_CLI_MIN_INTERVAL"

# (argv, stdin_text, timeout) -> stdout text. Injected for tests.
CliRunner = Callable[[list[str], str | None, float], Awaitable[str]]


async def _asyncio_runner(argv: list[str], stdin_text: str | None, timeout: float) -> str:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE if stdin_text is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    payload = stdin_text.encode("utf-8") if stdin_text is not None else None
    try:
        out, err = await asyncio.wait_for(proc.communicate(payload), timeout)
    except asyncio.TimeoutError as exc:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise ProviderError("cli timeout", {"timeout": timeout}) from exc
    if proc.returncode != 0:
        raise ProviderError(
            "cli non-zero exit",
            {"returncode": proc.returncode, "stderr": (err or b"").decode("utf-8", "replace")[:300]})
    return (out or b"").decode("utf-8", "replace")


class _CliProvider(BaseModelProvider):
    """Base for a provider backed by a local CLI executable."""

    exe_name: str = ""
    exe_env: str = ""              # optional env override for the executable path

    def __init__(self, config: ProviderConfig, runner: CliRunner | None = None):
        super().__init__(config)
        self._runner = runner or _asyncio_runner
        self._last_call = 0.0

    def _exe_path(self) -> str | None:
        override = os.environ.get(self.exe_env) if self.exe_env else None
        if override and os.path.exists(override):
            return override
        return shutil.which(self.exe_name)

    @property
    def available(self) -> bool:
        # Gated: present executable AND the per-backend LLM switch is on (the
        # legacy DUMMY_CLI_PROVIDERS master still arms both, for back-compat).
        from model_router.llm_switches import llm_backend_enabled

        armed = (llm_backend_enabled(self._backend or "")
                 or os.environ.get(CLI_GATE_ENV) == "1")
        return armed and self._exe_path() is not None

    def _argv(self, prompt: str, exe: str) -> tuple[list[str], str | None]:
        raise NotImplementedError

    def _extract(self, stdout: str) -> str:
        return stdout.strip()

    async def _throttle(self) -> None:
        try:
            interval = float(os.environ.get(MIN_INTERVAL_ENV, DEFAULT_MIN_INTERVAL))
        except (TypeError, ValueError):
            interval = DEFAULT_MIN_INTERVAL
        wait = interval - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()

    async def _call_api(
        self, prompt: str, task: ModelTask, max_tokens: int, temperature: float
    ) -> str:
        exe = self._exe_path()
        if exe is None:
            raise ProviderError("cli executable missing", {"exe": self.exe_name})
        await self._throttle()
        argv, stdin_text = self._argv(prompt, exe)
        stdout = await self._runner(argv, stdin_text, self.config.timeout_seconds)
        text = self._extract(stdout)
        if not text:
            raise ProviderError("empty cli output", {"exe": self.exe_name})
        return text

    def _estimate_cost(self, usage: dict[str, int] | None) -> float | None:
        # Billed to the personal subscription, not metered here.
        return None


class ClaudeCliProvider(_CliProvider):
    """The `claude` CLI in print mode. --output-format json wraps the reply in
    {"result": "<text>", ...}; we return that inner text for schema
    validation. The prompt is fed on stdin to avoid arg-length/quoting limits."""
    name = "claude_cli"
    exe_name = "claude"
    exe_env = "DUMMY_CLAUDE_CLI_PATH"
    _backend = "claude"

    def _argv(self, prompt: str, exe: str) -> tuple[list[str], str | None]:
        argv = [exe, "-p", "--output-format", "json"]
        if self.config.model_name and self.config.model_name != "mock":
            argv += ["--model", self.config.model_name]
        return argv, prompt

    def _extract(self, stdout: str) -> str:
        stdout = stdout.strip()
        try:
            wrapper = json.loads(stdout)
        except (ValueError, TypeError):
            return stdout                       # not JSON; use as-is
        # Only unwrap the CLI envelope ({"result": "..."}); a bare forecast
        # JSON (no result/text key) is already the payload -- pass it through.
        if isinstance(wrapper, dict) and ("result" in wrapper or "text" in wrapper):
            return str(wrapper.get("result") or wrapper.get("text") or "").strip()
        return stdout


class CodexCliProvider(_CliProvider):
    """The `codex exec` CLI. --json emits a JSONL event stream; the final
    assistant message is the reply. Falls back to raw stdout if the stream
    isn't JSONL (older/newer CLI). Model is configurable -- the CLI's own
    default may be too new for the installed binary, so set model_name to a
    version the installed codex supports before arming."""
    name = "codex_cli"
    exe_name = "codex"
    exe_env = "DUMMY_CODEX_CLI_PATH"
    _backend = "codex"

    def _argv(self, prompt: str, exe: str) -> tuple[list[str], str | None]:
        argv = [exe, "exec", "--json"]
        if self.config.model_name and self.config.model_name != "mock":
            argv += ["-m", self.config.model_name]
        argv.append(prompt)
        return argv, None

    def _extract(self, stdout: str) -> str:
        # Prefer the last assistant/message text from the JSONL event stream.
        last_text = ""
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            text = _codex_event_text(event)
            if text:
                last_text = text
        return last_text or stdout.strip()


def _codex_event_text(event: Any) -> str:
    """Pull assistant text out of a codex JSON event, tolerant of shape."""
    if not isinstance(event, dict):
        return ""
    for key in ("message", "text", "content", "delta"):
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            inner = val.get("text") or val.get("content")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""
