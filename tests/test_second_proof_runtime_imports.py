"""Regression tests proving the second-proof one-shot-live import graph resolves.

The original BLOCKED_BEFORE_BROKER incident was a ``ModuleNotFoundError`` for the
``calibration`` package when ``tools/operator_authority_appliance/operator_full_completion.py``
was executed via ``python tools/.../operator_full_completion.py one-shot-live``.  That invocation
puts the script's own directory on ``sys.path[0]`` instead of the repo root, so the package must
be discoverable through the installed editable distribution, not just the current-working-dir
fallback used by ``python -c`` or pytest.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path



REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = REPO_ROOT / "tools" / "operator_authority_appliance" / "operator_full_completion.py"


def _minimal_env() -> dict[str, str]:
    """Return the current environment with PYTHONPATH cleared.

    Clearing PYTHONPATH forces the package to be resolved through the installed
    editable distribution (or the current-working-directory fallback), which is
    exactly the condition that exposed the missing ``calibration`` package.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def test_calibration_package_importable_outside_repo_root():
    """``calibration`` must resolve when cwd is not the repo root."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, "-c", "import calibration.schema; print('OK')"],
            cwd=tmp,
            env=_minimal_env(),
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "OK" in result.stdout


def test_second_proof_runner_importable_from_script_directory():
    """``core.second_proof_runner`` must import when the CLI script is invoked by path.

    The preflight command is the simplest production path that imports the full
    second-proof runner graph.  After a real attempt the lock may be consumed, so
    we accept either PASS or BLOCKED_PROOF_LOCK as proof the import resolved.
    """
    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "second-proof-runtime-preflight"],
        cwd=str(REPO_ROOT),
        env=_minimal_env(),
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in output
    assert "SECOND_PROOF_RUNTIME_PREFLIGHT_PASS" in output or "BLOCKED_PROOF_LOCK" in output


def test_preflight_does_not_contact_broker_or_enable_live_submit():
    """The runtime preflight must be read-only with respect to broker state and live-submit."""
    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "second-proof-runtime-preflight"],
        cwd=str(REPO_ROOT),
        env=_minimal_env(),
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert "ModuleNotFoundError" not in output
    assert "broker_contacted=true" not in output.lower()
    assert "live_submit_enabled" not in output.lower() or "live_submit_enabled=false" in output.lower()


def test_command_seal_still_blocks_without_env_gate():
    """Even after repair, one-shot-live must refuse to run without the exact env gate."""
    result = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "one-shot-live"],
        cwd=str(REPO_ROOT),
        env=_minimal_env(),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "BLOCKED_ENV_GATE_ABSENT" in (result.stdout + result.stderr)
