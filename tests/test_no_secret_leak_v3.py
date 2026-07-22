"""Scan logs and artifacts for leaked Kalshi secrets."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import core.secret_guard as secret_guard
from core.env_loader import read_whitelisted_env

SECRET_KEYS = [
    "KALSHI_API_KEY_ID",
    "KALSHI_API_PRIVATE_KEY_PEM",
    "KALSHI_API_PRIVATE_KEY_PEM_PATH",
]


def _real_secret_values():
    """Configured secrets from the shell env or the local .env (never logged)."""
    dotenv = read_whitelisted_env()
    values = []
    for key in SECRET_KEYS:
        value = os.environ.get(key) or dotenv.get(key)
        if value and len(value) >= 8:
            values.append((key, value))
    return values


_SCAN_CHUNK_BYTES = 1024 * 1024


def _file_matches(path: Path, needles: list[tuple[str, bytes]]) -> set[str]:
    """Search once in bounded chunks while preserving cross-chunk matches."""
    remaining = dict(needles)
    matches: set[str] = set()
    overlap = max((len(value) - 1 for value in remaining.values()), default=0)
    tail = b""
    with path.open("rb") as handle:
        while chunk := handle.read(_SCAN_CHUNK_BYTES):
            window = tail + chunk
            for key, value in tuple(remaining.items()):
                if value in window:
                    matches.add(key)
                    del remaining[key]
            if not remaining:
                break
            tail = window[-overlap:] if overlap else b""
    return matches


def _find_offenders(paths, secrets):
    """Scan the corpus concurrently without putting secrets in process args.

    The artifact store contains thousands of immutable snapshots.  One Python
    file-open loop eventually exceeds the repository's per-test timeout as the
    store grows.  Threads keep the same exhaustive byte scan while overlapping
    Windows file-open/Defender latency; secrets never leave this process.
    """

    encoded_secrets = [
        (key, value.encode("utf-8"))
        for key, value in secrets
    ]
    files = sorted(path for path in paths if path.is_file())

    def scan(path: Path) -> tuple[Path, set[str], str | None]:
        try:
            return path, _file_matches(path, encoded_secrets), None
        except FileNotFoundError:
            # Scheduled artifact rotation may remove a path after enumeration;
            # a file that no longer exists is no longer part of the corpus.
            return path, set(), None
        except OSError as exc:
            return path, set(), type(exc).__name__

    worker_count = min(32, max(4, (os.cpu_count() or 4) * 2), len(files) or 1)
    offenders: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        for path, matches, scan_error in pool.map(scan, files):
            if scan_error is not None:
                offenders.append(("SCAN_ERROR", f"{path}:{scan_error}"))
            offenders.extend(
                (key, str(path))
                for key, _value in encoded_secrets
                if key in matches
            )
    return offenders


def test_secret_leak_detector_catches_planted_value(tmp_path):
    """The detector itself is exercised hermetically on every run."""
    leaked = tmp_path / "leaky.log"
    leaked.write_text("Authorization: sentinel-key-value-123456", encoding="utf-8")
    (tmp_path / "clean.log").write_text("nothing to see", encoding="utf-8")
    offenders = _find_offenders(
        sorted(tmp_path.rglob("*")), [("KALSHI_API_KEY_ID", "sentinel-key-value-123456")]
    )
    assert offenders == [("KALSHI_API_KEY_ID", str(leaked))]


def test_secret_leak_detector_catches_cross_chunk_value(tmp_path, monkeypatch):
    """Chunk boundaries must not create a blind spot in the detector."""
    monkeypatch.setattr(sys.modules[__name__], "_SCAN_CHUNK_BYTES", 8)
    leaked = tmp_path / "boundary.bin"
    leaked.write_bytes(b"1234567sentinel-secret-value")
    offenders = _find_offenders(
        [leaked], [("KALSHI_API_KEY_ID", "sentinel-secret-value")]
    )
    assert offenders == [("KALSHI_API_KEY_ID", str(leaked))]


def test_secret_leak_detector_fails_closed_on_unreadable_file(tmp_path, monkeypatch):
    artifact = tmp_path / "unreadable.json"
    artifact.write_text("{}", encoding="utf-8")

    def unreadable(_path, _needles):
        raise PermissionError("fixture")

    monkeypatch.setattr(sys.modules[__name__], "_file_matches", unreadable)
    offenders = _find_offenders(
        [artifact],
        [("KALSHI_API_KEY_ID", "sentinel-secret-value")],
    )
    assert offenders == [("SCAN_ERROR", f"{artifact}:PermissionError")]


def test_no_real_secret_values_in_logs_and_artifacts():
    """Any real configured secret value must not appear in logs or artifacts."""
    secrets = _real_secret_values()
    if not secrets:
        pytest.skip("No Kalshi secrets in the shell environment or local .env")

    paths = []
    for root in ["logs", "artifacts"]:
        p = Path(root)
        if p.exists():
            paths.extend(p.rglob("*"))

    offenders = _find_offenders(paths, secrets)
    assert not offenders, f"Secrets found in: {offenders}"


def test_redact_text_masks_registered_secret():
    """redact_text masks a secret value once it is registered."""
    original = list(secret_guard._SECRET_VALUES)
    try:
        secret_guard._SECRET_VALUES.append("kalshi-test-key-id-12345")
        text = secret_guard.redact_text("Authorization: kalshi-test-key-id-12345")
        assert "kalshi-test-key-id-12345" not in text
        assert "***REDACTED***" in text
    finally:
        secret_guard._SECRET_VALUES[:] = original


def test_redact_masks_secret_keys():
    payload = {"api_key_id": "secret123", "private_key": "pem456", "safe": "visible"}
    redacted = secret_guard.redact(payload)
    assert redacted["api_key_id"] == "***REDACTED***"
    assert redacted["private_key"] == "***REDACTED***"
    assert redacted["safe"] == "visible"


def test_nested_redaction_snapshots_environment_once(monkeypatch):
    calls = []

    def secrets():
        calls.append(True)
        return ["dynamic-secret"]

    monkeypatch.setattr(secret_guard, "_current_env_secrets", secrets)
    redacted = secret_guard.redact(
        {"rows": [{"title": "dynamic-secret"}, {"title": "dynamic-secret"}]}
    )

    assert calls == [True]
    assert redacted["rows"][0]["title"] == "***REDACTED***"
    assert redacted["rows"][1]["title"] == "***REDACTED***"
