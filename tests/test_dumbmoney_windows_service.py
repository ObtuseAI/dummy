from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from autonomy.executor import Executor
from autonomy.ontology import SessionMode
from live_firewall.dumbmoney_capital import verify_signed_envelope
from live_firewall.dumbmoney_command_feed import CommandFeedPollResult
from live_firewall.dumbmoney_windows_service import (
    CELL_TOKEN_TARGET_REF,
    CONFIG_RELATIVE_PATH,
    CONFIG_SCHEMA,
    CORE_ENDPOINT_REF,
    CORE_READINESS_RELATIVE_PATH,
    DATA_ROOT_RELATIVE_PATH,
    KALSHI_KEY_ID_TARGET_REF,
    KALSHI_PRIVATE_KEY_TARGET_REF,
    READINESS_KEY_TARGET_REF,
    READINESS_REF,
    READINESS_RELATIVE_PATH,
    READINESS_SCHEMA,
    SERVICE_NAME,
    START_MODE,
    CoreEndpoint,
    DumbMoneyDummyKalshiService,
    DumbMoneyWindowsServiceError,
    DummyKalshiRunnerConfig,
    RunnerSecrets,
    kalshi_account_hash,
    load_runner_config,
    load_secrets,
)


NOW = datetime(2026, 7, 26, 22, 0, 0, tzinfo=timezone.utc)


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _key(seed: int) -> tuple[str, bytes, str]:
    private = Ed25519PrivateKey.from_private_bytes(bytes([seed]) * 32)
    public = private.public_key().public_bytes_raw()
    return (
        hashlib.sha256(public).hexdigest(),
        public,
        base64.urlsafe_b64encode(public).decode("ascii").rstrip("="),
    )


def _config(
    tmp_path: Path,
    *,
    readiness_private: Ed25519PrivateKey,
    key_id: str = "kalshi-fixture-key",
) -> DummyKalshiRunnerConfig:
    core_id, core, _ = _key(1)
    operator_id, operator, _ = _key(2)
    promoter_id, promoter, _ = _key(3)
    research_id, research, _ = _key(4)
    evaluator_id, evaluator, _ = _key(6)
    readiness_id = hashlib.sha256(
        readiness_private.public_key().public_bytes_raw()
    ).hexdigest()
    return DummyKalshiRunnerConfig(
        release_id="release-fixture-1",
        core_readiness_path=tmp_path / "core-readiness.json",
        data_root=tmp_path / "data",
        readiness_path=tmp_path / "readiness.json",
        core_public_keys={core_id: core},
        operator_public_keys={operator_id: operator},
        promoter_public_keys={promoter_id: promoter},
        research_public_keys={research_id: research},
        evaluator_public_keys={evaluator_id: evaluator},
        expected_account_hash=kalshi_account_hash(key_id, 0),
        kalshi_subaccount_number=0,
        fund_lock_sha256=_hash("fund-lock"),
        service_manifest_sha256=_hash("manifest"),
        role_public_keys_sha256=_hash("roles"),
        core_runner_config_sha256=_hash("core-config"),
        risk_policy_sha256=_hash("risk"),
        readiness_signer_public_key_sha256=readiness_id,
        poll_interval_seconds=5,
        readiness_ttl_seconds=30,
        broker_truth_max_age_seconds=30,
        config_sha256=_hash("runner-config"),
    )


def _public_config_payload(
    program_data: Path,
    *,
    readiness_private: Ed25519PrivateKey,
    key_id: str,
) -> dict:
    core_id, _, core = _key(1)
    operator_id, _, operator = _key(2)
    promoter_id, _, promoter = _key(3)
    research_id, _, research = _key(4)
    evaluator_id, _, evaluator = _key(6)
    return {
        "schema": CONFIG_SCHEMA,
        "service_name": SERVICE_NAME,
        "release_id": "release-fixture-1",
        "core_endpoint_ref": CORE_ENDPOINT_REF,
        "core_readiness_path": str(
            (program_data / CORE_READINESS_RELATIVE_PATH).resolve()
        ),
        "core_cell_token_target": CELL_TOKEN_TARGET_REF,
        "kalshi_key_id_target": KALSHI_KEY_ID_TARGET_REF,
        "kalshi_private_key_target": KALSHI_PRIVATE_KEY_TARGET_REF,
        "readiness_signing_key_target": READINESS_KEY_TARGET_REF,
        "start_mode": START_MODE,
        "data_root": str((program_data / DATA_ROOT_RELATIVE_PATH).resolve()),
        "readiness_ref": READINESS_REF,
        "readiness_path": str(
            (program_data / READINESS_RELATIVE_PATH).resolve()
        ),
        "core_public_keys_base64url": {core_id: core},
        "operator_public_keys_base64url": {operator_id: operator},
        "promoter_public_keys_base64url": {promoter_id: promoter},
        "research_public_keys_base64url": {research_id: research},
        "evaluator_public_keys_base64url": {evaluator_id: evaluator},
        "expected_account_hash": kalshi_account_hash(key_id, 0),
        "kalshi_subaccount_number": 0,
        "fund_lock_sha256": _hash("fund-lock"),
        "service_manifest_sha256": _hash("manifest"),
        "role_public_keys_sha256": _hash("roles"),
        "core_runner_config_sha256": _hash("core-config"),
        "risk_policy_sha256": _hash("risk"),
        "readiness_signer_public_key_sha256": hashlib.sha256(
            readiness_private.public_key().public_bytes_raw()
        ).hexdigest(),
        "poll_interval_seconds": 5,
        "readiness_ttl_seconds": 30,
        "broker_truth_max_age_seconds": 30,
    }


class _Credentials:
    def __init__(self, values: dict[str, bytes]) -> None:
        self.values = values
        self.targets: list[str] = []

    def read_bytes(self, target: str) -> bytes:
        self.targets.append(target)
        return self.values[target]


def test_config_is_raw_byte_pinned_and_secrets_use_only_four_targets(
    tmp_path: Path,
) -> None:
    program_data = tmp_path / "ProgramData"
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    key_id = "kalshi-fixture-key"
    payload = _public_config_payload(
        program_data,
        readiness_private=readiness,
        key_id=key_id,
    )
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    config_path = program_data / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(raw)
    config = load_runner_config(
        config_path,
        hashlib.sha256(raw).hexdigest(),
        program_data,
    )

    rsa_private = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pem = rsa_private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    provider = _Credentials(
        {
            "DumbMoney/DummyCellToken": b"t" * 64,
            "DumbMoney/KalshiApiKeyId": key_id.encode(),
            "DumbMoney/KalshiPrivateKeyPem": pem,
            "DumbMoney/DummyReadinessEd25519": bytes([9]) * 32,
        }
    )
    secrets = load_secrets(provider, config)

    assert secrets.cell_token == "t" * 64
    assert secrets.kalshi_key_id == key_id
    assert provider.targets == [
        "DumbMoney/DummyCellToken",
        "DumbMoney/KalshiApiKeyId",
        "DumbMoney/KalshiPrivateKeyPem",
        "DumbMoney/DummyReadinessEd25519",
    ]


class _NoNetworkTransport:
    def __init__(self) -> None:
        self.calls = 0
        self.endpoint: CoreEndpoint | None = None

    def set_endpoint(self, endpoint: CoreEndpoint) -> None:
        self.endpoint = endpoint

    def liveness(self) -> None:
        self.calls += 1

    def contract_get(self, *_args, **_kwargs):
        raise AssertionError("contract transport must not run during setup")

    def command_get(self, *_args, **_kwargs):
        raise AssertionError("command transport must not run during setup")

    def journal_anchor_post(self, *_args, **_kwargs):
        raise AssertionError("anchor transport must not run during setup")

    def close(self) -> None:
        return


class _BrokerTruth:
    def __init__(self, snapshot: dict) -> None:
        self.value = snapshot
        self.calls = 0

    def snapshot(self) -> dict:
        self.calls += 1
        return dict(self.value)


def _secrets(readiness: Ed25519PrivateKey) -> RunnerSecrets:
    return RunnerSecrets(
        cell_token="t" * 64,
        kalshi_key_id="kalshi-fixture-key",
        kalshi_private_key_pem=b"unused-in-unit-service",
        readiness_private_key=readiness,
    )


def test_startup_is_network_silent_and_readiness_is_signed_blocked(
    tmp_path: Path,
) -> None:
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    config = _config(tmp_path, readiness_private=readiness)
    transport = _NoNetworkTransport()
    broker = _BrokerTruth({})
    service = DumbMoneyDummyKalshiService(
        config,
        _secrets(readiness),
        core_transport=transport,  # type: ignore[arg-type]
        broker_truth=broker,
        clock=lambda: NOW,
    )
    try:
        service.start()
        envelope = json.loads(config.readiness_path.read_text())
        verified = verify_signed_envelope(
            envelope,
            trusted_public_keys={
                config.readiness_signer_public_key_sha256: (
                    readiness.public_key().public_bytes_raw()
                )
            },
            now=NOW,
            expected_body_schema=READINESS_SCHEMA,
        )

        assert transport.calls == 0
        assert broker.calls == 0
        assert verified.body["authority"] == {
            "broker": "KALSHI",
            "mode": START_MODE,
            "execution_enabled": False,
        }
        assert verified.body["health"]["status"] == "BLOCKED"
    finally:
        service.close()


def test_service_components_use_sqlite_wal_journals_and_close_them(
    tmp_path: Path,
) -> None:
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    config = _config(tmp_path, readiness_private=readiness)
    transport = _NoNetworkTransport()
    service = DumbMoneyDummyKalshiService(
        config,
        _secrets(readiness),
        core_transport=transport,  # type: ignore[arg-type]
        broker_truth=_BrokerTruth({}),
        clock=lambda: NOW,
    )
    service.start()
    try:
        service._initialize_components()
        capital_path = config.data_root / "capital-operational.db"
        command_path = config.data_root / "command-feed.db"
        assert capital_path.is_file()
        assert command_path.is_file()
        assert not (config.data_root / "capital-operational.jsonl").exists()
        assert not (config.data_root / "command-feed.jsonl").exists()

        for path in (capital_path, command_path):
            with sqlite3.connect(path) as connection:
                assert connection.execute(
                    "PRAGMA journal_mode"
                ).fetchone()[0] == "wal"
                assert connection.execute(
                    "SELECT event_count FROM journal_metadata "
                    "WHERE singleton = 1"
                ).fetchone() == (0,)
    finally:
        service.close()

    assert service._capital_journal is None
    assert service._command_journal is None


def test_legacy_live_executor_cannot_construct_firewall_without_dumbmoney(
    tmp_path: Path,
) -> None:
    executor = Executor(
        SessionMode.LIVE,
        session_path=tmp_path / "session.json",
        kill_path=tmp_path / "KILL",
        capital_envelope_adapter=None,
    )

    with pytest.raises(RuntimeError, match="mandatory for LIVE"):
        executor._make_firewall()


class _CommandFeed:
    def poll_once(self) -> CommandFeedPollResult:
        return CommandFeedPollResult(
            page_accepted=True,
            cursor_sequence=1,
            cursor_digest="1" * 64,
            commands_applied=1,
            required_action="APPLY_SIGNED_CONTROLS",
            submission_allowed=True,
            reason="fixture current",
        )

    def submission_allowed(self) -> bool:
        return True


class _CapitalAdapter:
    def __init__(self) -> None:
        self.receipts: list[dict] = []

    def record_broker_bootstrap(self, receipt: dict) -> None:
        self.receipts.append(receipt)


class _JournalHead:
    def head(self) -> tuple[int, str]:
        return 0, "0" * 64

    def close(self) -> None:
        return


class _ExposureHead:
    def anchor_head(self) -> tuple[int, str]:
        return 0, "0" * 64


class _JournalAnchorClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def anchor(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _RejectingJournalAnchorClient:
    def anchor(self, **_kwargs) -> None:
        raise RuntimeError("Core rejected rolled-back journal")


def _install_anchor_fixtures(
    service: DumbMoneyDummyKalshiService,
) -> _JournalAnchorClient:
    client = _JournalAnchorClient()
    service._capital_journal = _JournalHead()  # type: ignore[assignment]
    service._command_journal = _JournalHead()  # type: ignore[assignment]
    service._exposure_tracker = _ExposureHead()  # type: ignore[assignment]
    service._journal_anchor_client = client  # type: ignore[assignment]
    return client


class _ReconciliationSweeper:
    def __init__(
        self,
        *,
        unresolved_reservations: int,
        unresolved_positions: int,
    ) -> None:
        self.unresolved_reservations = unresolved_reservations
        self.unresolved_positions = unresolved_positions
        self.calls = 0

    def run_once(self) -> dict:
        self.calls += 1
        return {
            "unresolved_reservations": self.unresolved_reservations,
            "unresolved_positions": self.unresolved_positions,
        }


def test_anchor_rejection_blocks_before_broker_contact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    config = _config(tmp_path, readiness_private=readiness)
    transport = _NoNetworkTransport()
    broker = _BrokerTruth({})
    service = DumbMoneyDummyKalshiService(
        config,
        _secrets(readiness),
        core_transport=transport,  # type: ignore[arg-type]
        broker_truth=broker,
        journal_anchor_client=(  # type: ignore[arg-type]
            _RejectingJournalAnchorClient()
        ),
        clock=lambda: NOW,
    )
    service._components_ready = True
    service._capital_adapter = _CapitalAdapter()  # type: ignore[assignment]
    service._command_feed = _CommandFeed()  # type: ignore[assignment]
    service._capital_journal = _JournalHead()  # type: ignore[assignment]
    service._command_journal = _JournalHead()  # type: ignore[assignment]
    service._exposure_tracker = _ExposureHead()  # type: ignore[assignment]
    monkeypatch.setattr(
        "live_firewall.dumbmoney_windows_service._core_endpoint_from_readiness",
        lambda *_args, **_kwargs: CoreEndpoint(
            base_url="http://127.0.0.1:8765",
            instance_id="00000000-0000-0000-0000-000000000001",
            observed_at="2026-07-26T22:00:00Z",
            valid_until="2026-07-26T22:01:00Z",
        ),
    )
    try:
        service.start()
        with pytest.raises(
            RuntimeError,
            match="rolled-back journal",
        ):
            service.run_once()
        state = service.state()
        assert broker.calls == 0
        assert state.health_status == "BLOCKED"
        assert state.rollback_anchor_current is False
        assert state.execution_enabled is False
    finally:
        service.close()


def test_pending_restart_reconciliation_blocks_otherwise_flat_book(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    config = _config(tmp_path, readiness_private=readiness)
    transport = _NoNetworkTransport()
    broker = _BrokerTruth({
        "schema": "dummy.kalshi-broker-truth.v1",
        "venue": "dummy_kalshi",
        "account_hash": config.expected_account_hash,
        "subaccount_number": 0,
        "observed_at": "2026-07-26T22:00:00Z",
        "broker_snapshot_sha256": _hash("flat-with-pending"),
        "flat_book_observed": True,
        "total_exposure_cents": 0,
        "open_order_count": 0,
        "market_exposure_cents": {},
        "correlated_exposure_cents": {},
        "unresolved_open_orders": 0,
        "unresolved_positions": 0,
    })
    sweeper = _ReconciliationSweeper(
        unresolved_reservations=1,
        unresolved_positions=0,
    )
    service = DumbMoneyDummyKalshiService(
        config,
        _secrets(readiness),
        core_transport=transport,  # type: ignore[arg-type]
        broker_truth=broker,
        reconciliation_sweeper=sweeper,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    service._components_ready = True
    service._capital_adapter = _CapitalAdapter()  # type: ignore[assignment]
    service._command_feed = _CommandFeed()  # type: ignore[assignment]
    anchors = _install_anchor_fixtures(service)
    monkeypatch.setattr(
        "live_firewall.dumbmoney_windows_service._core_endpoint_from_readiness",
        lambda *_args, **_kwargs: CoreEndpoint(
            base_url="http://127.0.0.1:8765",
            instance_id="00000000-0000-0000-0000-000000000001",
            observed_at="2026-07-26T22:00:00Z",
            valid_until="2026-07-26T22:01:00Z",
        ),
    )
    try:
        service.start()
        result = service.run_once()
        state = service.state()

        assert result["status"] == "RECONCILIATION_BLOCKED"
        assert state.reason == "UNRESOLVED_BROKER_ORDERS_OR_POSITIONS"
        assert state.unresolved_open_orders == 1
        assert state.execution_enabled is False
        assert sweeper.calls == 1
        assert len(anchors.calls) == 6
    finally:
        service.close()


def test_unresolved_broker_book_stays_reconciliation_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    config = _config(tmp_path, readiness_private=readiness)
    transport = _NoNetworkTransport()
    snapshot_body = {
        "schema": "dummy.kalshi-broker-truth.v1",
        "venue": "dummy_kalshi",
        "account_hash": config.expected_account_hash,
        "subaccount_number": 0,
        "observed_at": "2026-07-26T22:00:00Z",
        "broker_snapshot_sha256": _hash("broker-snapshot"),
        "flat_book_observed": False,
        "total_exposure_cents": 100,
        "open_order_count": 1,
        "market_exposure_cents": {"KXTEST": 100},
        "correlated_exposure_cents": {"KXTEST": 100},
        "unresolved_open_orders": 1,
        "unresolved_positions": 1,
    }
    broker = _BrokerTruth(snapshot_body)
    service = DumbMoneyDummyKalshiService(
        config,
        _secrets(readiness),
        core_transport=transport,  # type: ignore[arg-type]
        broker_truth=broker,
        execution_cycle=lambda **_kwargs: {"orders_submitted": 1},
        clock=lambda: NOW,
    )
    adapter = _CapitalAdapter()
    service._components_ready = True
    service._capital_adapter = adapter  # type: ignore[assignment]
    service._command_feed = _CommandFeed()  # type: ignore[assignment]
    anchors = _install_anchor_fixtures(service)
    monkeypatch.setattr(
        "live_firewall.dumbmoney_windows_service._core_endpoint_from_readiness",
        lambda *_args, **_kwargs: CoreEndpoint(
            base_url="http://127.0.0.1:8765",
            instance_id="00000000-0000-0000-0000-000000000001",
            observed_at="2026-07-26T22:00:00Z",
            valid_until="2026-07-26T22:01:00Z",
        ),
    )
    try:
        service.start()
        result = service.run_once()
        state = service.state()

        assert result["status"] == "RECONCILIATION_BLOCKED"
        assert state.mode == START_MODE
        assert state.execution_enabled is False
        assert state.reconciled_once is False
        assert state.unresolved_open_orders == 1
        assert state.unresolved_positions == 1
        assert len(adapter.receipts) == 1
        assert len(anchors.calls) == 6
    finally:
        service.close()


def test_second_pass_blocked_cycle_cannot_publish_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    readiness = Ed25519PrivateKey.from_private_bytes(bytes([9]) * 32)
    config = _config(tmp_path, readiness_private=readiness)
    transport = _NoNetworkTransport()
    broker = _BrokerTruth({
        "schema": "dummy.kalshi-broker-truth.v1",
        "venue": "dummy_kalshi",
        "account_hash": config.expected_account_hash,
        "subaccount_number": 0,
        "observed_at": "2026-07-26T22:00:00Z",
        "broker_snapshot_sha256": _hash("flat-broker-snapshot"),
        "flat_book_observed": True,
        "total_exposure_cents": 0,
        "open_order_count": 0,
        "market_exposure_cents": {},
        "correlated_exposure_cents": {},
        "unresolved_open_orders": 0,
        "unresolved_positions": 0,
    })
    cycle_calls: list[dict] = []

    def blocked_cycle(**kwargs):
        cycle_calls.append(kwargs)
        return {
            "schema": "dummy.dumbmoney-execution-cycle.v1",
            "status": "BLOCKED",
            "broker_contacted": False,
            "orders_submitted": 0,
            "broker_snapshot_sha256": _hash("flat-broker-snapshot"),
        }

    service = DumbMoneyDummyKalshiService(
        config,
        _secrets(readiness),
        core_transport=transport,  # type: ignore[arg-type]
        broker_truth=broker,
        execution_cycle=blocked_cycle,
        clock=lambda: NOW,
    )
    adapter = _CapitalAdapter()
    service._components_ready = True
    service._capital_adapter = adapter  # type: ignore[assignment]
    service._command_feed = _CommandFeed()  # type: ignore[assignment]
    anchors = _install_anchor_fixtures(service)
    monkeypatch.setattr(
        "live_firewall.dumbmoney_windows_service._core_endpoint_from_readiness",
        lambda *_args, **_kwargs: CoreEndpoint(
            base_url="http://127.0.0.1:8765",
            instance_id="00000000-0000-0000-0000-000000000001",
            observed_at="2026-07-26T22:00:00Z",
            valid_until="2026-07-26T22:01:00Z",
        ),
    )
    try:
        service.start()
        first = service.run_once()
        first_state = service.state()
        assert first["status"] == "RECONCILIATION_COMPLETE"
        assert first_state.health_status == "BLOCKED"
        assert first_state.reason == "INITIAL_RECONCILIATION_COMPLETE"
        assert first_state.execution_enabled is False
        assert first_state.rollback_anchor_current is True
        result = service.run_once()
        state = service.state()

        assert result["status"] == "BLOCKED"
        assert state.health_status == "BLOCKED"
        assert state.reason == "EXECUTION_CYCLE_BLOCKED"
        assert state.execution_enabled is False
        assert state.rollback_anchor_current is True
        assert len(cycle_calls) == 1
        assert cycle_calls[0]["broker_snapshot"] == broker.value
        assert len(anchors.calls) == 12

        service.execution_cycle = lambda **_kwargs: {
            "schema": "dummy.dumbmoney-execution-cycle.v1",
            "status": "BLOCKED",
            "broker_contacted": False,
            "orders_submitted": 0,
            "broker_snapshot_sha256": _hash("different-snapshot"),
        }
        with pytest.raises(
            DumbMoneyWindowsServiceError,
            match="execution cycle result is invalid",
        ):
            service.run_once()
        assert service.state().execution_enabled is False
        assert service.state().broker_truth_fresh is False
    finally:
        service.close()
