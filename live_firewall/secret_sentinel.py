"""DUMMY-owned fail-closed secret and unsafe-content sentinel.

This module is intentionally dependency-free so the live firewall never has
to import research code or a legacy external namespace to inspect an order.
"""

from __future__ import annotations

import re
from pathlib import Path


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OPENROUTER_API_KEY_VALUE", re.compile(r"sk-or-[A-Za-z0-9_-]{20,}")),
    ("OPENAI_API_KEY_VALUE", re.compile(r"sk-(?!or\b)[A-Za-z0-9]{20,}")),
    (
        "API_KEY_ASSIGNMENT",
        re.compile(
            r"(?i)(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]{8,}['\"]"
        ),
    ),
    (
        "PRIVATE_KEY_BLOCK",
        re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA |PRIVATE )?KEY-----"),
    ),
    ("BROWSER_COOKIE", re.compile(r"(?i)(sessionid|cookie|set-cookie)\s*[:=]")),
)

BLOCKED_MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "PRIVATE_REPO_MARKER",
        re.compile(r"(?i)private[_ -]?repo|unauthorized repository"),
    ),
    ("LEAKED_CODE_MARKER", re.compile(r"(?i)leaked[_ -]?code|stolen source")),
    ("MALWARE_MARKER", re.compile(r"(?i)malware|ransomware|keylogger")),
    (
        "EXPLOIT_CHAIN_MARKER",
        re.compile(r"(?i)exploit chain|weaponized exploit"),
    ),
)


def scan_text_for_risk(text: str) -> tuple[str, ...]:
    """Return every deterministic risk flag found in text."""

    return tuple(
        name
        for name, pattern in (*SECRET_PATTERNS, *BLOCKED_MARKERS)
        if pattern.search(text)
    )


def scan_path_for_risk(path: Path) -> tuple[str, ...]:
    """Reject common secret-bearing artifact names before content handling."""

    lower = path.name.lower()
    flags: list[str] = []
    if lower == ".env" or lower.endswith(".env"):
        flags.append("ENV_FILE_BLOCKED")
    if "cookie" in lower:
        flags.append("COOKIE_FILE_BLOCKED")
    return tuple(flags)


def is_clean_risk(flags: tuple[str, ...]) -> bool:
    return not flags
