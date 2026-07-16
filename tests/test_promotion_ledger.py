"""Hash-chained promotion ledger: append, verify, tamper, daily counting."""
from __future__ import annotations

import json

import pytest

from autonomy.promotion_ledger import (
    ACTION_ABORT,
    ACTION_DEMOTE,
    ACTION_ESCALATE,
    ACTION_PROMOTE,
    GENESIS_HASH,
    PromotionLedger,
    PromotionLedgerError,
)

SCOPE = "crypto_ta_foundry|btc|15m_direction|15m"


def test_empty_ledger_reads_empty(tmp_path):
    ledger = PromotionLedger(tmp_path / "chain.jsonl")
    assert ledger.read_verified() == ()
    assert ledger.entries_on_date("2026-07-16") == []


def test_append_links_chain_from_genesis(tmp_path):
    ledger = PromotionLedger(tmp_path / "chain.jsonl")
    first = ledger.append(
        action=ACTION_PROMOTE, scope=SCOPE,
        payload={"stage": 1}, at="2026-07-16T09:00:00+00:00",
    )
    second = ledger.append(
        action=ACTION_ESCALATE, scope=SCOPE,
        payload={"stage": 2}, at="2026-07-17T09:00:00+00:00",
    )
    assert first.previous_hash == GENESIS_HASH
    assert second.previous_hash == first.entry_hash
    assert first.sequence == 0 and second.sequence == 1
    entries = ledger.read_verified()
    assert [e.action for e in entries] == [ACTION_PROMOTE, ACTION_ESCALATE]
    # Payload snapshot survives round-trip verbatim.
    assert entries[0].payload == {"stage": 1}


def test_tampered_payload_breaks_verification(tmp_path):
    path = tmp_path / "chain.jsonl"
    ledger = PromotionLedger(path)
    ledger.append(action=ACTION_PROMOTE, scope=SCOPE, payload={"stage": 1})
    line = json.loads(path.read_text(encoding="utf-8").strip())
    line["payload"]["stage"] = 2  # rewrite history
    path.write_text(json.dumps(line) + "\n", encoding="utf-8")
    with pytest.raises(PromotionLedgerError, match="tampered"):
        ledger.read_verified()


def test_broken_link_breaks_verification(tmp_path):
    path = tmp_path / "chain.jsonl"
    ledger = PromotionLedger(path)
    ledger.append(action=ACTION_PROMOTE, scope=SCOPE, payload={})
    ledger.append(action=ACTION_DEMOTE, scope=SCOPE, payload={})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    # Drop the first entry: the second's previous_hash no longer matches.
    path.write_text(lines[1] + "\n", encoding="utf-8")
    with pytest.raises(PromotionLedgerError, match="chain is broken"):
        ledger.read_verified()


def test_corrupt_line_and_malformed_entry_raise(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(PromotionLedgerError, match="not JSON"):
        PromotionLedger(path).read_verified()
    path.write_text(json.dumps({"sequence": 0}) + "\n", encoding="utf-8")
    with pytest.raises(PromotionLedgerError, match="malformed"):
        PromotionLedger(path).read_verified()


def test_append_refuses_to_extend_a_broken_chain(tmp_path):
    path = tmp_path / "chain.jsonl"
    ledger = PromotionLedger(path)
    ledger.append(action=ACTION_PROMOTE, scope=SCOPE, payload={})
    path.write_text("garbage\n", encoding="utf-8")
    with pytest.raises(PromotionLedgerError):
        ledger.append(action=ACTION_DEMOTE, scope=SCOPE, payload={})


def test_invalid_action_and_blank_scope_rejected(tmp_path):
    ledger = PromotionLedger(tmp_path / "chain.jsonl")
    with pytest.raises(PromotionLedgerError, match="unknown promotion action"):
        ledger.append(action="SIDEWAYS", scope=SCOPE, payload={})
    with pytest.raises(PromotionLedgerError, match="scope is required"):
        ledger.append(action=ACTION_PROMOTE, scope="  ", payload={})


def test_entries_on_date_counts_utc_days(tmp_path):
    ledger = PromotionLedger(tmp_path / "chain.jsonl")
    ledger.append(action=ACTION_PROMOTE, scope="a|b|c|d",
                  payload={}, at="2026-07-16T01:00:00+00:00")
    ledger.append(action=ACTION_ESCALATE, scope="e|f|g|h",
                  payload={}, at="2026-07-16T23:00:00+00:00")
    ledger.append(action=ACTION_ABORT, scope="*",
                  payload={}, at="2026-07-16T23:30:00+00:00")
    ledger.append(action=ACTION_PROMOTE, scope="i|j|k|l",
                  payload={}, at="2026-07-17T00:30:00+00:00")
    today = ledger.entries_on_date("2026-07-16")
    assert [e.action for e in today] == [ACTION_PROMOTE, ACTION_ESCALATE, ACTION_ABORT]
    assert len(ledger.entries_on_date("2026-07-17")) == 1
