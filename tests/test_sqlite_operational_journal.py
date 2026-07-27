from __future__ import annotations

import json
import multiprocessing
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from live_firewall.operational_journal import (
    AppendOnlyOperationalJournal,
    OPERATIONAL_EVENT_SCHEMA,
    OperationalJournalError,
    canonical_json,
    sha256_json,
)
from live_firewall.sqlite_operational_journal import (
    SQLITE_OPERATIONAL_JOURNAL_SCHEMA,
    SQLiteOperationalJournal,
)


NOW = datetime(2026, 7, 26, 12, 30, tzinfo=timezone.utc)


def _claim_in_process(
    database_path: str,
    worker_id: int,
    start: Any,
    results: Any,
) -> None:
    journal = SQLiteOperationalJournal(
        Path(database_path),
        now_fn=lambda: NOW,
        busy_timeout_seconds=10,
    )
    try:
        if not journal.healthy:
            results.put(("unhealthy", journal.error))
            return
        if not start.wait(timeout=15):
            results.put(("timeout", worker_id))
            return

        def no_prior_claim(rows: tuple[dict[str, Any], ...]) -> None:
            if any(row.get("kind") == "dispatch.claimed" for row in rows):
                raise OperationalJournalError("dispatch is already claimed")

        event = journal.append(
            "dispatch.claimed",
            {"worker_id": worker_id},
            outbox_id=f"dispatch-claim:{worker_id}",
            allow_existing_outbox=False,
            validate_existing=no_prior_claim,
            validate_existing_latest_kinds=("dispatch.claimed",),
        )
        results.put(("committed", event["sequence"]))
    except OperationalJournalError as exc:
        results.put(("rejected", str(exc)))
    finally:
        journal.close()


def test_restart_preserves_chain_idempotency_and_outbox_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "operational.db"
    journal = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    assert journal.healthy, journal.error

    source = journal.append(
        "capital.reserved",
        {"reservation_id": "reservation-1", "cents": 125},
        outbox_id="reservation:1",
    )
    assert (
        journal.append(
            "capital.reserved",
            {"reservation_id": "reservation-1", "cents": 125},
            outbox_id="reservation:1",
        )
        == source
    )
    with pytest.raises(
        OperationalJournalError,
        match="reused with different content",
    ):
        journal.append(
            "capital.reserved",
            {"reservation_id": "reservation-1", "cents": 126},
            outbox_id="reservation:1",
        )

    other = journal.append(
        "capital.reserved",
        {"reservation_id": "reservation-2", "cents": 75},
        outbox_id="reservation:2",
    )
    acknowledgement = journal.acknowledge_outbox(
        "reservation:1",
        acknowledgement={"receipt_id": "receipt-1"},
    )
    assert journal.pending_outbox() == (other,)
    journal.close()

    restarted = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    assert restarted.healthy, restarted.error
    rows = restarted.events()
    assert [row["sequence"] for row in rows] == [1, 2, 3]
    assert rows[0] == source
    assert rows[2] == acknowledgement
    assert rows[2]["previous_sha256"] == rows[1]["event_sha256"]
    assert rows[0]["schema"] == OPERATIONAL_EVENT_SCHEMA
    assert restarted.pending_outbox() == (other,)

    with pytest.raises(OperationalJournalError, match="already claimed"):
        restarted.append(
            "capital.reserved",
            {"reservation_id": "reservation-1", "cents": 125},
            outbox_id="reservation:1",
            allow_existing_outbox=False,
        )
    assert restarted.healthy
    restarted.close()


def test_event_contract_matches_jsonl_reference(tmp_path: Path) -> None:
    sqlite_journal = SQLiteOperationalJournal(
        tmp_path / "contract.db",
        now_fn=lambda: NOW,
    )
    jsonl_journal = AppendOnlyOperationalJournal(
        tmp_path / "contract.jsonl",
        now_fn=lambda: NOW,
    )
    assert sqlite_journal.head() == (0, "0" * 64)
    assert jsonl_journal.head() == (0, "0" * 64)

    sqlite_source = sqlite_journal.append(
        "broker.bootstrap.recorded",
        {"receipt_id": "bootstrap-1", "orders": []},
        outbox_id="bootstrap:1",
    )
    jsonl_source = jsonl_journal.append(
        "broker.bootstrap.recorded",
        {"receipt_id": "bootstrap-1", "orders": []},
        outbox_id="bootstrap:1",
    )
    assert sqlite_source == jsonl_source
    assert sqlite_journal.head() == (
        sqlite_source["sequence"],
        sqlite_source["event_sha256"],
    )
    assert jsonl_journal.head() == sqlite_journal.head()

    sqlite_ack = sqlite_journal.acknowledge_outbox(
        "bootstrap:1",
        acknowledgement={"delivered": True},
    )
    jsonl_ack = jsonl_journal.acknowledge_outbox(
        "bootstrap:1",
        acknowledgement={"delivered": True},
    )
    assert sqlite_ack == jsonl_ack
    assert sqlite_journal.events() == jsonl_journal.events()
    assert sqlite_journal.pending_outbox() == jsonl_journal.pending_outbox()
    assert sqlite_journal.head() == (
        sqlite_ack["sequence"],
        sqlite_ack["event_sha256"],
    )
    assert jsonl_journal.head() == sqlite_journal.head()
    sqlite_journal.close()


def test_jsonl_reference_supports_bounded_latest_kind_validation(
    tmp_path: Path,
) -> None:
    journal = AppendOnlyOperationalJournal(
        tmp_path / "reference.jsonl",
        now_fn=lambda: NOW,
    )
    journal.append("state", {"cursor": 1})
    latest = journal.append("state", {"cursor": 2})
    journal.append("unrelated", {"value": 3})
    observed: list[tuple[dict[str, Any], ...]] = []

    journal.append(
        "state",
        {"cursor": 3},
        validate_existing=observed.append,
        validate_existing_latest_kinds=("state",),
    )
    assert observed == [(latest,)]


def test_two_live_instances_incrementally_observe_committed_tail(
    tmp_path: Path,
) -> None:
    path = tmp_path / "two-live-instances.db"
    first = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    second = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    assert first.healthy and second.healthy

    first_event = first.append(
        "command.applied",
        {"command_id": "command-1"},
        outbox_id="command:1",
    )
    assert second.events(after_sequence=0, limit=1) == (first_event,)

    second_event = second.append(
        "command.applied",
        {"command_id": "command-2"},
        outbox_id="command:2",
    )
    assert first.events(after_sequence=first_event["sequence"]) == (
        second_event,
    )
    assert first.healthy and second.healthy
    first.close()
    second.close()


def test_serialized_operation_rolls_back_all_appends_and_cached_head(
    tmp_path: Path,
) -> None:
    path = tmp_path / "transaction-rollback.db"
    journal = SQLiteOperationalJournal(path, now_fn=lambda: NOW)

    with pytest.raises(RuntimeError, match="handler failed"):
        with journal.serialized_operation():
            journal.append("command.received", {"command_id": "one"})
            journal.append("command.applied", {"command_id": "one"})
            raise RuntimeError("handler failed after second append")

    assert journal.healthy, journal.error
    assert journal.events() == ()
    replacement = journal.append(
        "command.failed",
        {"command_id": "one"},
    )
    assert replacement["sequence"] == 1
    assert replacement["previous_sha256"] == "0" * 64
    journal.close()


def test_latest_kind_validation_view_is_bounded_and_atomic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "latest-kind-cas.db"
    journal = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    with journal.serialized_operation():
        for index in range(100):
            journal.append("irrelevant.telemetry", {"index": index})
        prior = journal.append(
            "command-feed.state.persisted",
            {"cursor": 10},
        )
        for index in range(100, 200):
            journal.append("irrelevant.telemetry", {"index": index})

    observed: list[tuple[dict[str, Any], ...]] = []

    def validate_latest(rows: tuple[dict[str, Any], ...]) -> None:
        observed.append(rows)
        assert rows == (prior,)

    appended = journal.append(
        "command-feed.state.persisted",
        {"cursor": 11},
        validate_existing=validate_latest,
        validate_existing_latest_kinds=("command-feed.state.persisted",),
    )
    assert appended["sequence"] == 202
    assert observed == [(prior,)]
    journal.close()


def test_begin_immediate_makes_cross_process_validation_one_shot(
    tmp_path: Path,
) -> None:
    path = tmp_path / "claims.db"
    initial = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    assert initial.healthy, initial.error
    initial.close()

    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_claim_in_process,
            args=(str(path), worker_id, start, results),
        )
        for worker_id in range(4)
    ]
    for process in processes:
        process.start()
    start.set()
    observed = [results.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0

    assert sum(result[0] == "committed" for result in observed) == 1
    assert sum(result[0] == "rejected" for result in observed) == 3

    restarted = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    claims = restarted.events(kind="dispatch.claimed")
    assert len(claims) == 1
    assert claims[0]["sequence"] == 1
    restarted.close()


def test_live_instance_detects_mid_chain_tamper_plus_valid_tail_append(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-tamper.db"
    journal = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    journal.append("authority.granted", {"scope": "first"})
    journal.append("authority.granted", {"scope": "second"})

    with sqlite3.connect(path) as connection:
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'trigger' "
            "AND name = 'operational_events_no_update'"
        ).fetchone()[0]
        event_json = connection.execute(
            "SELECT event_json FROM operational_events WHERE sequence = 1"
        ).fetchone()[0]
        event = json.loads(event_json)
        event["payload"]["scope"] = "tampered"
        connection.execute("DROP TRIGGER operational_events_no_update")
        connection.execute(
            "UPDATE operational_events SET event_json = ? WHERE sequence = 1",
            (canonical_json(event),),
        )
        connection.execute(trigger_sql)
        event_count, head = connection.execute(
            "SELECT event_count, head_sha256 FROM journal_metadata "
            "WHERE singleton = 1"
        ).fetchone()
        tail = {
            "schema": OPERATIONAL_EVENT_SCHEMA,
            "sequence": event_count + 1,
            "recorded_at": "2026-07-26T12:31:00Z",
            "kind": "authority.granted",
            "payload": {"scope": "valid-tail"},
            "previous_sha256": head,
        }
        tail["event_sha256"] = sha256_json(tail)
        connection.execute(
            "INSERT INTO operational_events ("
            "sequence, kind, outbox_id, acknowledges_outbox_id, "
            "previous_sha256, event_sha256, event_json"
            ") VALUES (?, ?, NULL, NULL, ?, ?, ?)",
            (
                tail["sequence"],
                tail["kind"],
                tail["previous_sha256"],
                tail["event_sha256"],
                canonical_json(tail),
            ),
        )

    assert not journal.healthy
    assert journal.error is not None
    assert "hash" in journal.error.casefold()
    journal.close()


@pytest.mark.parametrize(
    ("mutation_sql", "expected_error"),
    [
        (
            "CREATE INDEX unauthorized_payload_idx "
            "ON operational_events(event_json)",
            "schema object set mismatch",
        ),
        ("PRAGMA user_version = 99", "schema version mismatch"),
    ],
)
def test_live_instance_rejects_schema_or_version_mutation(
    tmp_path: Path,
    mutation_sql: str,
    expected_error: str,
) -> None:
    path = tmp_path / "schema-mutation.db"
    journal = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    journal.append("authority.granted", {"scope": "one"})

    with sqlite3.connect(path) as connection:
        connection.execute(mutation_sql)

    assert not journal.healthy
    assert journal.error is not None
    assert expected_error in journal.error
    journal.close()


@pytest.mark.parametrize("tamper", ["event", "head"])
def test_restart_fails_closed_on_event_or_head_tamper(
    tmp_path: Path,
    tamper: str,
) -> None:
    path = tmp_path / f"tamper-{tamper}.db"
    journal = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    journal.append("authority.granted", {"scope": "single-order"})
    journal.close()

    with sqlite3.connect(path) as connection:
        if tamper == "head":
            connection.execute(
                "UPDATE journal_metadata SET head_sha256 = ? "
                "WHERE singleton = 1",
                ("f" * 64,),
            )
        else:
            trigger_sql = connection.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'trigger' "
                "AND name = 'operational_events_no_update'"
            ).fetchone()[0]
            event_json = connection.execute(
                "SELECT event_json FROM operational_events WHERE sequence = 1"
            ).fetchone()[0]
            event = json.loads(event_json)
            event["payload"]["scope"] = "tampered-unbounded"
            connection.execute("DROP TRIGGER operational_events_no_update")
            connection.execute(
                "UPDATE operational_events SET event_json = ? "
                "WHERE sequence = 1",
                (canonical_json(event),),
            )
            connection.execute(trigger_sql)

    restarted = SQLiteOperationalJournal(path, now_fn=lambda: NOW)
    assert not restarted.healthy
    assert restarted.error is not None
    assert any(
        marker in restarted.error.casefold()
        for marker in ("hash", "head")
    )
    with pytest.raises(OperationalJournalError, match="unhealthy"):
        restarted.events()
    restarted.close()


def test_bounded_incremental_reads_use_kind_and_outbox_indexes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bounded.db"
    journal = SQLiteOperationalJournal(
        path,
        now_fn=lambda: NOW,
        scan_batch_size=7,
    )
    with journal.serialized_operation():
        for index in range(2_000):
            journal.append(
                "kind.even" if index % 2 == 0 else "kind.odd",
                {"index": index},
                outbox_id=f"event:{index}",
            )

    page = journal.events(
        kind="kind.even",
        after_sequence=40,
        limit=6,
    )
    assert len(page) == 6
    assert [row["sequence"] for row in page] == [41, 43, 45, 47, 49, 51]

    pending_page = journal.pending_outbox(
        after_sequence=1_980,
        limit=4,
    )
    assert [row["sequence"] for row in pending_page] == [
        1_981,
        1_982,
        1_983,
        1_984,
    ]
    journal.close()

    with sqlite3.connect(path) as connection:
        metadata = connection.execute(
            "SELECT schema, event_count FROM journal_metadata "
            "WHERE singleton = 1"
        ).fetchone()
        assert metadata == (SQLITE_OPERATIONAL_JOURNAL_SCHEMA, 2_000)

        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert "operational_events_kind_sequence_idx" in indexes
        assert "operational_events_outbox_sequence_idx" in indexes
        assert "operational_events_ack_target_idx" in indexes

        kind_plan = " ".join(
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT event_json FROM operational_events "
                "WHERE kind = ? AND sequence > ? "
                "ORDER BY sequence LIMIT ?",
                ("kind.even", 40, 6),
            )
        )
        assert "operational_events_kind_sequence_idx" in kind_plan

        outbox_plan = " ".join(
            str(row[3])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT event_json FROM operational_events "
                "WHERE outbox_id = ?",
                ("event:1999",),
            )
        )
        assert "INDEX" in outbox_plan
        assert "SCAN operational_events" not in outbox_plan
