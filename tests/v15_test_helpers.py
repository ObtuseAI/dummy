from __future__ import annotations

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v14.credential_forensics import KalshiCredentialForensics


def bridge_with_env(env: dict[str, str]) -> KalshiReadOnlyCredentialBridge:
    return KalshiReadOnlyCredentialBridge(env=env, dummy_env_path="__nonexistent_dummy__.env", project_env_path="__nonexistent_project__.env")


def forensics_with_env(env: dict[str, str]) -> KalshiCredentialForensics:
    return KalshiCredentialForensics(credential_bridge=bridge_with_env(env))


VALID_ENV = {
    "KALSHI_API_KEY_ID": "real-looking-key-id-1234",
    "KALSHI_API_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
}

MALFORMED_BACKSLASH_ENV = {
    "KALSHI_API_KEY_ID": "real-looking-key-id-1234",
    "KALSHI_API_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
}

MISSING_ENV: dict[str, str] = {}

PLACEHOLDER_KEY_ENV = {
    "KALSHI_API_KEY_ID": "<placeholder>",
    "KALSHI_API_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
}
