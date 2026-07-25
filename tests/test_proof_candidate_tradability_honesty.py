"""A proof candidate must never claim tradability it did not observe.

The read-only discovery path synthesises placeholder metadata when it never
reached the market -- no GET made, or the GET raised. That placeholder used to
carry ``trading_allowed=False``, so the emitted packet and report said
``market_tradable: false`` while ``market_status`` said ``unknown`` two fields
away.

"Not tradable" and "we never looked" are different facts. JSON has ``null`` for
the second, and the distinction matters because these packets get promoted to
the canonical candidate that a live proof reads.
"""
from __future__ import annotations

from core.kalshi_market_validator import ContractMetadata, MarketMetadata
from core.proof_order_candidate import build_validated_proof_candidate_v3

CAPS = {"max_order_count": 1, "max_single_order_cents": 100}
CTX = {
    "descriptor_hash": "D",
    "caps_hash": "C",
    "live_submit_hash": "L",
    "evidence_registry_hash": "E",
    "previous_real_broker_attempt_status": "NONE",
    "runtime_approval_hash": "R",
    "current_live_submit_hash": "L",
}


def _metadata(status, trading_allowed, contract_status, contract_tradable):
    return MarketMetadata(
        ticker="KXTEST-26DEC1-T1",
        status=status,
        open_time=None,
        close_time=None,
        trading_allowed=trading_allowed,
        min_price_cents=1,
        max_price_cents=99,
        tick_size_cents=1,
        contracts=[
            ContractMetadata(
                ticker="KXTEST-26DEC1-T1",
                status=contract_status,
                tradable=contract_tradable,
            )
        ],
    )


def _build(metadata, **kw):
    return build_validated_proof_candidate_v3(metadata, CAPS, CTX, **kw)


class TestUnobservedMarketIsNotUntradable:
    def test_unknown_market_status_yields_null_tradability(self):
        candidate = _build(
            _metadata("unknown", False, "unknown", False),
            candidate_found=False,
            price_source="unknown",
            price_validated=False,
            read_only_metadata_contact=False,
        )
        assert candidate.market_tradable is None, "unobserved market must not claim untradable"
        assert candidate.contract_tradable is None

    def test_unknown_status_still_reports_status_unknown(self):
        candidate = _build(
            _metadata("unknown", False, "unknown", False),
            candidate_found=False,
            price_source="unknown",
            price_validated=False,
            read_only_metadata_contact=False,
        )
        assert candidate.market_status == "unknown"
        assert candidate.contract_status == "unknown"

    def test_null_is_distinguishable_from_false_in_the_packet(self):
        """The whole point: a consumer must be able to tell them apart."""
        unobserved = _build(
            _metadata("unknown", False, "unknown", False),
            candidate_found=False, price_source="unknown",
            price_validated=False, read_only_metadata_contact=False,
        )
        observed_closed = _build(
            _metadata("closed", False, "closed", False),
            candidate_found=False, price_source="metadata",
            price_validated=False, read_only_metadata_contact=True,
        )
        assert unobserved.market_tradable is None
        assert observed_closed.market_tradable is False
        assert unobserved.market_tradable is not observed_closed.market_tradable


class TestObservedMarketKeepsItsObservedValue:
    def test_observed_open_and_tradable_is_true(self):
        candidate = _build(
            _metadata("open", True, "open", True),
            candidate_found=True,
            price_source="metadata",
            price_validated=True,
            read_only_metadata_contact=True,
        )
        assert candidate.market_tradable is True
        assert candidate.contract_tradable is True

    def test_observed_closed_is_false_not_null(self):
        candidate = _build(
            _metadata("closed", False, "closed", False),
            candidate_found=False,
            price_source="metadata",
            price_validated=False,
            read_only_metadata_contact=True,
        )
        assert candidate.market_tradable is False
        assert candidate.contract_tradable is False

    def test_open_market_with_untradable_contract_keeps_both_facts(self):
        candidate = _build(
            _metadata("open", True, "closed", False),
            candidate_found=False,
            price_source="metadata",
            price_validated=False,
            read_only_metadata_contact=True,
        )
        assert candidate.market_tradable is True
        assert candidate.contract_tradable is False


class TestMissingContract:
    def test_no_contract_yields_unknown_not_false(self):
        metadata = MarketMetadata(
            ticker="KXTEST-26DEC1-T1",
            status="open",
            open_time=None,
            close_time=None,
            trading_allowed=True,
            min_price_cents=1,
            max_price_cents=99,
            tick_size_cents=1,
            contracts=[],
        )
        candidate = _build(
            metadata,
            candidate_found=False,
            price_source="metadata",
            price_validated=False,
            read_only_metadata_contact=True,
        )
        assert candidate.contract_status == "unknown"
        assert candidate.contract_tradable is None
