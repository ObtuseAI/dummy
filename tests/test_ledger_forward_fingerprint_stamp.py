"""Signals for registered forward candidates get their fingerprint stamped."""
from __future__ import annotations

import json

import pytest

from autonomy.ledger import AutonomyLedger as Ledger
from autonomy.ontology import Signal


SCOPE_SOURCE = "market_debias"
MLB_TICKER = "KXMLBGAME-26JUL23TEST-AAA"


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    registrations = tmp_path / "promotion_forward_registrations.json"
    registrations.write_text(json.dumps({
        "registrations": [{
            "scope": "market_debias|mlb|na|pre",
            "candidate_fingerprint": "a" * 64,
            "registered_at": "2026-07-22T00:00:00+00:00",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(
        Ledger, "_FORWARD_REGISTRATIONS_PATH", registrations, raising=True,
    )
    ledger = Ledger(tmp_path / "ledger.db")
    yield ledger
    ledger.close()


def _signal(source: str, ticker: str, features: dict | None = None) -> Signal:
    return Signal(
        source=source,
        market_ticker=ticker,
        probability_yes=0.55,
        uncertainty=0.1,
        rationale="test",
        features=dict(features or {}),
    )


def _stored_features(ledger: Ledger, source: str) -> dict:
    row = ledger._conn.execute(
        "SELECT features FROM signals WHERE source=? ORDER BY id DESC LIMIT 1",
        (source,),
    ).fetchone()
    assert row is not None
    return json.loads(row[0])


def test_registered_scope_signal_is_stamped(ledger):
    signal = _signal(SCOPE_SOURCE, MLB_TICKER, {"vertical": "sports"})
    assert ledger.record_signal(signal) is True
    stored = _stored_features(ledger, SCOPE_SOURCE)
    assert stored.get("promotion_candidate_fingerprint") == "a" * 64


def test_unregistered_source_is_untouched(ledger):
    signal = _signal("sports_elo", MLB_TICKER)
    assert ledger.record_signal(signal) is True
    stored = _stored_features(ledger, "sports_elo")
    assert "promotion_candidate_fingerprint" not in stored


def test_existing_fingerprint_is_never_overwritten(ledger):
    signal = _signal(
        SCOPE_SOURCE, MLB_TICKER,
        {"vertical": "sports", "promotion_candidate_fingerprint": "b" * 64},
    )
    assert ledger.record_signal(signal) is True
    stored = _stored_features(ledger, SCOPE_SOURCE)
    assert stored["promotion_candidate_fingerprint"] == "b" * 64


def test_missing_registrations_file_disables_stamping(tmp_path, monkeypatch):
    monkeypatch.setattr(
        Ledger,
        "_FORWARD_REGISTRATIONS_PATH",
        tmp_path / "missing.json",
        raising=True,
    )
    ledger = Ledger(tmp_path / "ledger.db")
    try:
        signal = _signal(SCOPE_SOURCE, MLB_TICKER, {"vertical": "sports"})
        assert ledger.record_signal(signal) is True
        stored = _stored_features(ledger, SCOPE_SOURCE)
        assert "promotion_candidate_fingerprint" not in stored
    finally:
        ledger.close()
