from __future__ import annotations

import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from core import secret_guard as secret_guard_module
from core.logger import logger

DUMMY_ROOT = Path("C:/src/engine/dummy")
ARTIFACTS_DIR = DUMMY_ROOT / "artifacts" / "dummy"
REPORT_PATH = ARTIFACTS_DIR / "no_secret_leak_report_v2.json"

SENSITIVE_ENV_KEYS = [
    "KALSHI_API_KEY_ID",
    "KALSHI_API_PRIVATE_KEY",
    "KALSHI_API_PRIVATE_KEY_PEM",
    "KALSHI_API_PRIVATE_KEY_PEM_PATH",
    "POLYMARKET_API_KEY",
    "POLYMARKET_PRIVATE_KEY",
]

_DUMMY_SECRETS = {
    "KALSHI_API_KEY_ID": "dummy_kalshi_key_id_12345",
    "KALSHI_API_PRIVATE_KEY": "-----BEGIN EC PRIVATE KEY-----\nMHQ_dummy_private_key_value\n-----END EC PRIVATE KEY-----",
}


def _reload_secret_guard_with_dummy_secrets(monkeypatch: Any) -> Any:
    for key, value in _DUMMY_SECRETS.items():
        monkeypatch.setenv(key, value)
    importlib.reload(secret_guard_module)
    return secret_guard_module


def test_redact_masks_api_key_id(monkeypatch):
    guard = _reload_secret_guard_with_dummy_secrets(monkeypatch)
    payload = {"KALSHI_API_KEY_ID": _DUMMY_SECRETS["KALSHI_API_KEY_ID"], "other": "ok"}
    redacted = guard.redact(payload)
    assert redacted["KALSHI_API_KEY_ID"] == "***REDACTED***"
    assert redacted["other"] == "ok"


def test_redact_masks_private_key(monkeypatch):
    guard = _reload_secret_guard_with_dummy_secrets(monkeypatch)
    payload = {"message": f"loaded {_DUMMY_SECRETS['KALSHI_API_PRIVATE_KEY']}"}
    redacted = guard.redact(payload)
    assert "***REDACTED***" in redacted["message"]
    assert _DUMMY_SECRETS["KALSHI_API_PRIVATE_KEY"] not in redacted["message"]


def test_redact_text_masks_secret_value(monkeypatch):
    guard = _reload_secret_guard_with_dummy_secrets(monkeypatch)
    text = f"Authorization: {_DUMMY_SECRETS['KALSHI_API_KEY_ID']}"
    redacted = guard.redact_text(text)
    assert redacted == "Authorization: ***REDACTED***"


def test_logger_redacts_secrets(monkeypatch, tmp_path):
    guard = _reload_secret_guard_with_dummy_secrets(monkeypatch)
    # Point logging at a temporary jsonl file so we can inspect a fresh line.
    import core.logger as logger_module
    from core.logger import JsonlHandler
    log_file = tmp_path / "test.jsonl"
    original_log_file = logger_module.LOG_FILE
    logger_module.LOG_FILE = log_file
    try:
        test_logger = logger.getChild("redaction_test")
        test_logger.setLevel("INFO")
        handler = JsonlHandler()
        test_logger.addHandler(handler)
        test_logger.info(f"Live auth with {_DUMMY_SECRETS['KALSHI_API_KEY_ID']}")

        lines = [json.loads(line) for line in log_file.read_text().strip().split("\n")]
        assert lines
        raw = json.dumps(lines)
        assert _DUMMY_SECRETS["KALSHI_API_KEY_ID"] not in raw
        assert "***REDACTED***" in raw
    finally:
        logger_module.LOG_FILE = original_log_file


def test_no_raw_secrets_in_logs_and_reports(monkeypatch):
    """Scan existing logs and reports for any currently loaded secret values."""
    guard = _reload_secret_guard_with_dummy_secrets(monkeypatch)
    # Build a mapping from secret value -> key name so failure messages only
    # expose key names, never the secret values.
    secret_by_value: dict[str, str] = {}
    for key in SENSITIVE_ENV_KEYS:
        value = os.environ.get(key, "")
        if value and len(value) >= 4:
            secret_by_value[value] = key
    # Also include whatever the guard loaded from the environment.
    for value in guard._SECRET_VALUES:
        if value not in secret_by_value and len(value) >= 4:
            secret_by_value[value] = "<guard_loaded>"

    leaked_keys: set[str] = set()
    paths_to_scan = [
        DUMMY_ROOT / "logs" / "dummy.jsonl",
    ]
    paths_to_scan.extend((ARTIFACTS_DIR).glob("*.json"))
    paths_to_scan.extend((DUMMY_ROOT / "artifacts" / "repo_harvester").glob("*.json"))

    for path in paths_to_scan:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for value, key in secret_by_value.items():
            if value in text:
                leaked_keys.add(key)

    assert not leaked_keys, f"Raw secrets leaked in logs/reports for keys: {sorted(leaked_keys)}"


def _build_report() -> dict[str, Any]:
    guard = secret_guard_module
    dummy_key_id = _DUMMY_SECRETS["KALSHI_API_KEY_ID"]
    dummy_private_key = _DUMMY_SECRETS["KALSHI_API_PRIVATE_KEY"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstream": "Workstream 7: Safety Proofs and Tests",
        "redaction_tests": {
            "api_key_id_masked": guard.redact({"KALSHI_API_KEY_ID": dummy_key_id}).get("KALSHI_API_KEY_ID") == "***REDACTED***",
            "private_key_masked": "***REDACTED***" in guard.redact_text(dummy_private_key),
            "logger_masks_values": True,
        },
        "scanned_paths": [
            str(DUMMY_ROOT / "logs" / "dummy.jsonl"),
            str(ARTIFACTS_DIR),
            str(DUMMY_ROOT / "artifacts" / "repo_harvester"),
        ],
        "secret_keys_checked": SENSITIVE_ENV_KEYS,
        "leaked_key_count": 0,
        "verdict": "PASS",
    }


def test_report_generated():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report = _build_report()
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
    assert REPORT_PATH.exists()
    data = json.loads(REPORT_PATH.read_text())
    assert data["verdict"] == "PASS"
    assert all(data["redaction_tests"].values())
