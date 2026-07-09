"""Safe environment-variable loader for operator-controlled one-shot processes.

Loads only whitelisted Kalshi credential reference names and Dummy live-proof env
gates from the current shell environment or from a .env file. Never prints secret
values; only reports SET/UNSET/file_exists.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Credential reference names that may be loaded from .env. Values are never logged.
KALSHI_ENV_REFS = {
    "KALSHI_API_KEY_ID",
    "KALSHI_API_PRIVATE_KEY_PEM",
    "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    "KALSHI_PRIVATE_KEY",
    "KALSHI_PRIVATE_KEY_PATH",
    "KALSHI_API_BASE",
    "KALSHI_API_VERSION",
}

# Dummy live-proof env gates.
LIVE_PROOF_ENV_REFS = {
    "DUMMY_LIVE_PROOF_MODE",
    "DUMMY_LIVE_PROOF_ACK",
}

ALLOWED_ENV_REFS = KALSHI_ENV_REFS | LIVE_PROOF_ENV_REFS


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file, skipping comments and blank lines."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip optional surrounding quotes.
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def read_whitelisted_env(dotenv_path: Path | str | None = None) -> dict[str, str]:
    """Read whitelisted env refs from .env without mutating os.environ.

    Returns a mapping of ref name -> value for keys present in the .env file.
    Values are not logged by this module.
    """
    if dotenv_path is None:
        dotenv_path = Path(".env")
    else:
        dotenv_path = Path(dotenv_path)

    dotenv_values = _parse_dotenv(dotenv_path)
    return {key: value for key, value in dotenv_values.items() if key in ALLOWED_ENV_REFS}


def apply_whitelisted_env(values: dict[str, str], *, overwrite: bool = False) -> dict[str, str]:
    """Apply a whitelist of env values to os.environ.

    Returns a dict of the keys that were set. Existing shell env values are
    preserved unless overwrite=True.
    """
    loaded: dict[str, str] = {}
    for key, value in values.items():
        if key not in ALLOWED_ENV_REFS:
            continue
        if key in os.environ and not overwrite:
            continue
        if value:
            os.environ[key] = value
            loaded[key] = "SET_FROM_DOTENV"
    return loaded


def load_whitelisted_env(*, dotenv_path: Path | str | None = None, overwrite: bool = False) -> dict[str, str]:
    """Read .env and apply whitelisted refs to os.environ.

    Convenience for production one-shot commands. Tests should prefer
    read_whitelisted_env + apply_whitelisted_env (or neither) to avoid leaking
    state between tests.
    """
    return apply_whitelisted_env(read_whitelisted_env(dotenv_path=dotenv_path), overwrite=overwrite)


def credential_ref_status(refs: set[str] | None = None, env_values: dict[str, str] | None = None) -> dict[str, Any]:
    """Report SET/UNSET for credential refs without exposing values.

    For private-key path refs, reports file_exists=true/false without reading
    the file contents.
    """
    if refs is None:
        refs = KALSHI_ENV_REFS
    source = env_values if env_values is not None else os.environ
    status: dict[str, Any] = {}
    for key in sorted(refs):
        value = source.get(key)
        present = bool(value)
        entry: dict[str, Any] = {"present": present}
        if "PATH" in key and present:
            path = Path(value)
            if not path.is_absolute():
                path = Path.cwd() / path
            entry["file_exists"] = path.exists()
        status[key] = entry
    return status


def kalshi_credential_status(env_values: dict[str, str] | None = None) -> dict[str, Any]:
    """Convenience wrapper for Kalshi credential refs only."""
    return credential_ref_status(KALSHI_ENV_REFS, env_values=env_values)
