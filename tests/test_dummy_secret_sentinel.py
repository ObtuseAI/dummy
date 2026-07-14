from __future__ import annotations

from pathlib import Path

import pytest

from live_firewall.firewall import _check_secret_redaction
from live_firewall.secret_sentinel import scan_path_for_risk, scan_text_for_risk


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("api_key='123456789abcdef'", "API_KEY_ASSIGNMENT"),
        ("-----BEGIN PRIVATE KEY-----", "PRIVATE_KEY_BLOCK"),
        ("set-cookie: session", "BROWSER_COOKIE"),
        ("weaponized exploit", "EXPLOIT_CHAIN_MARKER"),
    ],
)
def test_dummy_secret_sentinel_detects_risk(text: str, expected: str) -> None:
    assert expected in scan_text_for_risk(text)
    assert _check_secret_redaction(text) is False


def test_dummy_secret_sentinel_accepts_clean_order_text() -> None:
    assert scan_text_for_risk("market=KXBTC price=42 size=1") == ()
    assert _check_secret_redaction("market=KXBTC price=42 size=1") is True


def test_dummy_secret_sentinel_blocks_secret_file_names() -> None:
    assert scan_path_for_risk(Path(".env")) == ("ENV_FILE_BLOCKED",)
    assert scan_path_for_risk(Path("browser-cookies.json")) == (
        "COOKIE_FILE_BLOCKED",
    )


def test_live_firewall_has_no_legacy_runtime_dependency() -> None:
    source = Path("live_firewall/firewall.py").read_text(encoding="utf-8")
    assert "inherited_blunder" not in source
    assert "importlib.util" not in source
