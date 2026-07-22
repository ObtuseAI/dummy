from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from autonomy import sports_model_seed as seed
from autonomy.sports_board_refresh import (
    AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
    validate_authoritative_model_seed_binding,
)
from autonomy.taxonomy import scope_weight_key


NOW = datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc)


class FakePromotionRegistry:
    def __init__(self, active: list[str] | None = None) -> None:
        self.active = list(active or [])

    def snapshot(self) -> dict[str, Any]:
        return {
            "promoted": list(self.active),
            "auto_demoted": [],
            "active": list(self.active),
            "stages": {scope: 2 for scope in self.active},
            "weight_fractions": {scope: 1.0 for scope in self.active},
        }

    def is_promoted_signal(
        self,
        source: str,
        ticker: str,
        features: dict[str, Any] | None,
    ) -> bool:
        return False

    def weight_multiplier_for_signal(
        self,
        source: str,
        ticker: str,
        features: dict[str, Any] | None,
    ) -> float:
        return 1.0


def _write_trust_ledger(
    path: Path,
    rows: list[tuple[str, float]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE source_trust (source TEXT PRIMARY KEY, weight REAL)"
        )
        connection.executemany(
            "INSERT INTO source_trust (source, weight) VALUES (?, ?)",
            rows or [],
        )


def _empty_page_fetch(series: str) -> dict[str, Any]:
    assert series in seed.TARGET_SERIES
    return {"markets": [], "cursor": ""}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_read_only_trust_weights_honor_precedence_without_db_mutation(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.db"
    ticker = "KXMLBGAME-26JUL22CHCSTL-CHC"
    features = {"vertical": "SPORTS", "is_live": False}
    exact_key = scope_weight_key("alpha", ticker, features)
    _write_trust_ledger(
        ledger,
        [
            ("alpha", 0.6),
            ("alpha@SPORTS", 0.8),
            (exact_key, 1.2),
            ("global_only", 0.7),
        ],
    )
    before_bytes = ledger.read_bytes()
    before_stat = ledger.stat()

    weights = seed.ReadOnlyTrustWeights.from_ledger(ledger)

    assert weights.get_weight_for_signal(
        "alpha", "SPORTS", ticker, features
    ) == pytest.approx(1.2)
    assert weights.get_weight_for_signal(
        "alpha", "SPORTS", "KXWNBAGAME-26JUL22NYLVA-NYL", features
    ) == pytest.approx(0.8)
    assert weights.get_weight_for_signal(
        "global_only", "SPORTS", ticker, features
    ) == pytest.approx(0.7)
    assert weights.get_weight_for_signal(
        "unknown", "SPORTS", ticker, features
    ) == pytest.approx(1.0)
    assert ledger.read_bytes() == before_bytes
    assert ledger.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert not list(tmp_path.glob("ledger.db-*"))


def test_read_only_trust_weights_retry_brief_operational_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = tmp_path / "ledger.db"
    _write_trust_ledger(ledger, [("alpha", 0.75)])
    real_connect = sqlite3.connect
    attempts = 0
    sleeps: list[float] = []

    def flaky_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise sqlite3.OperationalError("database is briefly unavailable")
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(seed.sqlite3, "connect", flaky_connect)
    monkeypatch.setattr(seed.time, "sleep", sleeps.append)

    weights = seed.ReadOnlyTrustWeights.from_ledger(ledger)

    assert attempts == 3
    assert sleeps == list(seed.READ_ONLY_TRUST_RETRY_DELAYS_SECONDS)
    assert weights.get_weight("alpha") == pytest.approx(0.75)


def test_read_only_trust_weights_raise_busy_after_bounded_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = tmp_path / "ledger.db"
    _write_trust_ledger(ledger, [("alpha", 0.75)])
    attempts = 0
    sleeps: list[float] = []

    def busy_connect(*_args: Any, **_kwargs: Any) -> sqlite3.Connection:
        nonlocal attempts
        attempts += 1
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(seed.sqlite3, "connect", busy_connect)
    monkeypatch.setattr(seed.time, "sleep", sleeps.append)

    with pytest.raises(
        seed.ReadOnlyTrustSnapshotBusy,
        match="read-only trust snapshot failed: OperationalError",
    ):
        seed.ReadOnlyTrustWeights.from_ledger(ledger)

    assert attempts == len(seed.READ_ONLY_TRUST_RETRY_DELAYS_SECONDS) + 1
    assert sleeps == list(seed.READ_ONLY_TRUST_RETRY_DELAYS_SECONDS)


def test_missing_ledger_fails_without_creating_it(tmp_path: Path) -> None:
    ledger = tmp_path / "missing" / "ledger.db"

    with pytest.raises(seed.SportsModelSeedUnavailable, match="missing"):
        seed.ReadOnlyTrustWeights.from_ledger(ledger)

    assert not ledger.exists()
    assert not ledger.parent.exists()


@pytest.mark.parametrize(
    "scope",
    [
        "challenger_model|nfl|winner|pre",
        "challenger_model|mlb|spread|pre",
        "challenger_model|wnba|winner|pre",
    ],
)
def test_unsupported_active_sports_promotion_blocks_before_public_fetch(
    tmp_path: Path,
    scope: str,
) -> None:
    fetched: list[str] = []

    def forbidden_fetch(series: str) -> dict[str, Any]:
        fetched.append(series)
        raise AssertionError("promotion guard must run before public fetch")

    output = tmp_path / "seed.json"
    status_path = tmp_path / "status.json"
    code, status = seed.run_scheduled_seed(
        output_path=output,
        status_path=status_path,
        lock_path=tmp_path / "seed.lock",
        ledger_path=tmp_path / "missing-ledger.db",
        fetch_series=forbidden_fetch,
        promotion=FakePromotionRegistry([scope]),
        sources=(),
        source_warmer=lambda _sources, _now: [],
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 1
    assert status["status"] == "REFRESH_FAILED:UnsupportedGovernedSportsPromotion"
    assert status["stage"] == "promotion_guard"
    assert status["unsupported_active_promotions"] == [scope]
    assert fetched == []
    assert not output.exists()
    assert _read_json(status_path) == status


def test_lock_contention_does_not_overwrite_durable_owner_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status_path = tmp_path / "status.json"
    durable = {
        "status": "STAGE",
        "stage": "governed_forecast",
        "run_id": "active-owner",
        "last_success_at": "2026-07-22T14:55:00+00:00",
        "last_success_run_id": "prior-success",
        "last_success_seed_sha256": "a" * 64,
    }
    status_path.write_text(json.dumps(durable, indent=2), encoding="utf-8")
    before = status_path.read_bytes()

    @contextmanager
    def unavailable_lock(_path: Path):
        yield False

    monkeypatch.setattr(seed, "_refresh_lock", unavailable_lock)
    code, skipped = seed.run_scheduled_seed(
        output_path=tmp_path / "seed.json",
        status_path=status_path,
        lock_path=tmp_path / "seed.lock",
        ledger_path=tmp_path / "ledger.db",
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 75
    assert skipped["status"] == "SKIPPED_LOCK_HELD"
    assert skipped["last_success_run_id"] == "prior-success"
    assert status_path.read_bytes() == before


def test_one_series_failure_preserves_seed_and_last_success_binding(
    tmp_path: Path,
) -> None:
    output = tmp_path / "seed.json"
    prior_seed = b'{"prior":"authoritative-seed"}'
    output.write_bytes(prior_seed)
    status_path = tmp_path / "status.json"
    prior = {
        "status": "REFRESH_OK",
        "last_success_at": "2026-07-22T14:55:00+00:00",
        "last_success_run_id": "prior-run",
        "last_success_seed_sha256": hashlib.sha256(prior_seed).hexdigest(),
    }
    status_path.write_text(json.dumps(prior), encoding="utf-8")

    def partial_fetch(series: str) -> dict[str, Any]:
        if series == "KXMLBGAME":
            return {"markets": []}
        raise RuntimeError("simulated WNBA endpoint failure")

    code, failed = seed.run_scheduled_seed(
        output_path=output,
        status_path=status_path,
        lock_path=tmp_path / "seed.lock",
        ledger_path=tmp_path / "unused-ledger.db",
        fetch_series=partial_fetch,
        promotion=FakePromotionRegistry(),
        sources=(),
        source_warmer=lambda _sources, _now: [],
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 1
    assert failed["status"] == "REFRESH_FAILED:SportsModelSeedUnavailable"
    assert failed["stage"] == "public_winner_fetch"
    assert "KXWNBAGAME" in failed["error"]
    assert failed["last_success_at"] == prior["last_success_at"]
    assert failed["last_success_run_id"] == prior["last_success_run_id"]
    assert (
        failed["last_success_seed_sha256"]
        == prior["last_success_seed_sha256"]
    )
    assert output.read_bytes() == prior_seed


def _write_bound_prior_seed(
    output: Path,
    status_path: Path,
    *,
    generated_at: datetime,
    digest_override: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    generated_text = generated_at.astimezone(timezone.utc).isoformat()
    payload = {
        "source": AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
        "producer": seed.TASK_NAME,
        "producer_run_id": "prior-run",
        "generated_at": generated_text,
        "execution_authority": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    seed_bytes = output.read_bytes()
    prior = {
        "status": "REFRESH_OK",
        "last_success_at": generated_text,
        "last_success_run_id": "prior-run",
        "last_success_seed_sha256": (
            digest_override or hashlib.sha256(seed_bytes).hexdigest()
        ),
        "artifact_source": AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE,
        "execution_authority": False,
    }
    status_path.write_text(json.dumps(prior), encoding="utf-8")
    return seed_bytes, prior


def _raise_busy_trust_snapshot(_cls: type, _path: Path) -> None:
    raise seed.ReadOnlyTrustSnapshotBusy(
        "read-only trust snapshot failed: OperationalError"
    )


def test_busy_trust_snapshot_skips_with_fresh_hash_bound_prior_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "sports_model_seed_authoritative.json"
    status_path = tmp_path / "sports_model_seed_authoritative_status.json"
    prior_seed, prior = _write_bound_prior_seed(
        output,
        status_path,
        generated_at=NOW - timedelta(minutes=5),
    )
    monkeypatch.setattr(
        seed.ReadOnlyTrustWeights,
        "from_ledger",
        classmethod(_raise_busy_trust_snapshot),
    )

    code, skipped = seed.run_scheduled_seed(
        output_path=output,
        status_path=status_path,
        lock_path=tmp_path / "seed.lock",
        ledger_path=tmp_path / "busy-ledger.db",
        fetch_series=_empty_page_fetch,
        promotion=FakePromotionRegistry(),
        sources=(),
        source_warmer=lambda _sources, _now: [],
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 75
    assert skipped["status"] == "SKIPPED_TRUST_SNAPSHOT_BUSY"
    assert skipped["stage"] == "read_only_trust_snapshot"
    assert skipped["retryable"] is True
    assert skipped["using_last_success"] is True
    assert skipped["last_success_age_seconds"] == pytest.approx(300.0)
    assert skipped["last_success_at"] == prior["last_success_at"]
    assert skipped["last_success_run_id"] == prior["last_success_run_id"]
    assert (
        skipped["last_success_seed_sha256"]
        == prior["last_success_seed_sha256"]
    )
    assert skipped["seed_sha256"] == prior["last_success_seed_sha256"]
    assert output.read_bytes() == prior_seed
    assert _read_json(status_path) == skipped
    binding = validate_authoritative_model_seed_binding(
        seed_path=output,
        status_path=status_path,
        now=NOW,
    )
    assert binding["seed_sha256"] == prior["last_success_seed_sha256"]
    assert binding["status"] == "SKIPPED_TRUST_SNAPSHOT_BUSY"


@pytest.mark.parametrize("invalid_prior", ["missing", "stale", "hash_mismatch"])
def test_busy_trust_snapshot_fails_when_prior_seed_is_not_reusable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_prior: str,
) -> None:
    output = tmp_path / "sports_model_seed_authoritative.json"
    status_path = tmp_path / "sports_model_seed_authoritative_status.json"
    generated_at = NOW - (
        timedelta(seconds=seed.DISPLAY_MODEL_MAX_AGE_SECONDS + 1)
        if invalid_prior == "stale"
        else timedelta(minutes=5)
    )
    prior_seed, _prior = _write_bound_prior_seed(
        output,
        status_path,
        generated_at=generated_at,
        digest_override=("0" * 64 if invalid_prior == "hash_mismatch" else None),
    )
    if invalid_prior == "missing":
        output.unlink()
    monkeypatch.setattr(
        seed.ReadOnlyTrustWeights,
        "from_ledger",
        classmethod(_raise_busy_trust_snapshot),
    )

    code, failed = seed.run_scheduled_seed(
        output_path=output,
        status_path=status_path,
        lock_path=tmp_path / "seed.lock",
        ledger_path=tmp_path / "busy-ledger.db",
        fetch_series=_empty_page_fetch,
        promotion=FakePromotionRegistry(),
        sources=(),
        source_warmer=lambda _sources, _now: [],
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 1
    assert failed["status"] == "REFRESH_FAILED:ReadOnlyTrustSnapshotBusy"
    assert failed["stage"] == "read_only_trust_snapshot"
    assert failed["retryable"] is True
    assert failed["using_last_success"] is False
    assert failed["prior_seed_binding_error"] == "SportsBoardRefreshUnavailable"
    assert _read_json(status_path) == failed
    if invalid_prior == "missing":
        assert not output.exists()
    else:
        assert output.read_bytes() == prior_seed


def test_empty_valid_pages_publish_bound_authoritative_seed_without_authority(
    tmp_path: Path,
) -> None:
    output = tmp_path / "sports_model_seed_authoritative.json"
    status_path = tmp_path / "sports_model_seed_authoritative_status.json"
    ledger = tmp_path / "ledger.db"
    _write_trust_ledger(ledger)

    # A crypto-only promotion is unrelated to the governed sports roster and
    # must not stop the exact MLB/WNBA winner seed.
    promotion = FakePromotionRegistry(["crypto_model|btc|winner|hourly"])
    code, status = seed.run_scheduled_seed(
        output_path=output,
        status_path=status_path,
        lock_path=tmp_path / "seed.lock",
        ledger_path=ledger,
        fetch_series=_empty_page_fetch,
        promotion=promotion,
        sources=(),
        source_warmer=lambda _sources, _now: [],
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 0
    assert status["status"] == "REFRESH_OK"
    assert status["covered_series"] == list(seed.TARGET_SERIES)
    assert status["coverage_complete"] is True
    assert status["current_pregame_market_count"] == 0
    assert status["forecast_count"] == 0
    assert status["execution_authority"] is False
    assert status["promotion_authority"] is False
    assert status["trust_authority"] is False
    assert status["capital_authority"] is False
    assert status["no_ledger_writes"] is True
    assert status["no_paper_or_book_tape_writes"] is True
    assert status["retired_paper_or_shadow_pnl_consulted"] is False
    assert status["paper_result_promotion_gate_consulted"] is False
    assert status["canary_result_consulted"] is False
    assert status["negative_scope_performance_gate_consulted"] is False
    assert status["bankroll_or_trade_performance_gate_consulted"] is False

    payload = _read_json(output)
    persisted_status = _read_json(status_path)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert payload["source"] == AUTHORITATIVE_MODEL_SEED_ARTIFACT_SOURCE
    assert payload["producer"] == seed.TASK_NAME
    assert payload["producer_run_id"] == status["run_id"]
    assert payload["requested_series"] == list(seed.TARGET_SERIES)
    assert payload["covered_series"] == list(seed.TARGET_SERIES)
    assert payload["coverage_complete"] is True
    assert payload["execution_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["trust_authority"] is False
    assert persisted_status["last_success_at"] == payload["generated_at"]
    assert persisted_status["last_success_run_id"] == payload["producer_run_id"]
    assert persisted_status["last_success_seed_sha256"] == digest

    binding = validate_authoritative_model_seed_binding(
        seed_path=output,
        status_path=status_path,
        now=NOW,
    )
    assert binding == {
        "seed_sha256": digest,
        "producer_run_id": payload["producer_run_id"],
        "generated_at": payload["generated_at"],
        "status": "REFRESH_OK",
    }


def test_promotion_change_during_run_aborts_before_seed_replace(
    tmp_path: Path,
) -> None:
    output = tmp_path / "sports_model_seed_authoritative.json"
    prior = b'{"prior":"still-authoritative"}'
    output.write_bytes(prior)
    ledger = tmp_path / "ledger.db"
    _write_trust_ledger(ledger)
    promotion = FakePromotionRegistry()

    def mutate_registry(_sources: object, _now: datetime) -> list[str]:
        promotion.active.append("challenger_model|nfl|winner|pre")
        return []

    code, status = seed.run_scheduled_seed(
        output_path=output,
        status_path=tmp_path / "status.json",
        lock_path=tmp_path / "seed.lock",
        ledger_path=ledger,
        fetch_series=_empty_page_fetch,
        promotion=promotion,
        sources=(),
        source_warmer=mutate_registry,
        clock=lambda: NOW,
        monotonic=lambda: 10.0,
    )

    assert code == 1
    assert status["status"] == "REFRESH_FAILED:SportsModelSeedUnavailable"
    assert "changed during seed generation" in status["error"]
    assert output.read_bytes() == prior


def test_installer_defaults_to_disabled_five_minute_ignore_new_task() -> None:
    root = Path(__file__).resolve().parent.parent
    installer = (
        root / "scripts" / "install_sports_model_seed_task.ps1"
    ).read_text(encoding="utf-8")
    runner = (root / "scripts" / "run_sports_model_seed.py").read_text(
        encoding="utf-8"
    )
    legacy_monitor = (
        root / "scripts" / "run_dummy_mispricing_monitor.py"
    ).read_text(encoding="utf-8")

    assert '[string]$TaskName = "DummySportsModelSeed"' in installer
    assert "[int]$IntervalMinutes = 5" in installer
    assert "[int]$TimeoutMinutes = 3" in installer
    assert "if ($IntervalMinutes -ne 5)" in installer
    assert "$cadence = 5" in installer
    assert "$TimeoutMinutes -gt 3" in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert "-ExecutionTimeLimit (New-TimeSpan -Minutes $timeout)" in installer
    assert "Disable-ScheduledTask -TaskName $TaskName" in installer
    assert "InstalledDisabledForValidation = $true" in installer
    assert "run_sports_model_seed.py" in installer
    assert "run_scheduled_seed" in runner
    assert "autonomy.session" not in runner
    assert "AutonomyLedger" not in runner
    assert "mispricing_monitor" not in runner
    assert "sports_model_seed_authoritative" not in legacy_monitor
    assert "AUTHORITATIVE_MODEL_SEED_PATH" not in legacy_monitor
