from __future__ import annotations

from datetime import datetime, timezone

import pytest

from autonomy.ontology import MarketView, Vertical

from dummy.agents import market_view_observation
from dummy.organisms import (
    EpisodeValidationError,
    freeze_calibration_message,
    freeze_incumbent_forecast_message,
    freeze_market_quote_message,
)
from dummy.protocols import MessageEnvelope, MessageType


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)
MARKET_ID = "KXBTC15M-26JUL142215-15"


def _market_message(*, with_depth: bool = True) -> MessageEnvelope:
    raw = {"yes_ask_depth": 4, "no_ask_depth": 3} if with_depth else {}
    market = MarketView(
        ticker=MARKET_ID,
        title="BTC higher in 15 minutes?",
        vertical=Vertical.CRYPTO,
        status="open",
        close_time="2026-07-14T22:15:00Z",
        yes_bid=49,
        yes_ask=51,
        no_bid=49,
        no_ask=51,
        volume=100,
        liquidity=200,
        raw=raw,
    )
    return market_view_observation(
        market,
        sender="scanner-v1",
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="scanner-v1",
        policy_version="phase3-policy-v1",
    )


def _incumbent_message() -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type=MessageType.FORECAST,
        sender="btc-incumbent-specialist-v1",
        market_id=MARKET_ID,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="btc-incumbent-v1",
        policy_version="phase3-policy-v1",
        limitations=("shadow_only",),
        payload={
            "probability": 0.70,
            "uncertainty": 0.08,
            "source_family": "crypto-coinbase-distribution",
            "incumbent_source": "crypto_distribution",
        },
    )


def test_phase2_messages_freeze_into_phase3_evidence_without_refetch() -> None:
    quote = freeze_market_quote_message(
        _market_message(),
        source_reference="fixture://quote",
        observed_at_verified=True,
    )
    incumbent = freeze_incumbent_forecast_message(
        _incumbent_message(),
        source_reference="fixture://incumbent",
        observed_at_verified=True,
    )
    assert quote.payload["kind"] == "market_quote"
    assert quote.payload["yes_ask_depth"] == 4
    assert incumbent.payload["kind"] == "incumbent_forecast"
    assert incumbent.payload["probability_yes"] == 0.70
    assert incumbent.payload["source_family"] == "crypto-coinbase-distribution"


def test_market_bridge_fails_closed_without_witnessed_side_depth() -> None:
    with pytest.raises(EpisodeValidationError, match="side-specific ask depth"):
        freeze_market_quote_message(
            _market_message(with_depth=False),
            source_reference="fixture://quote",
            observed_at_verified=True,
        )


def test_unverified_incumbent_timestamp_is_rejected() -> None:
    with pytest.raises(EpisodeValidationError, match="unverified provider"):
        freeze_incumbent_forecast_message(
            _incumbent_message(),
            source_reference="fixture://incumbent",
            observed_at_verified=False,
        )


def test_calibration_bridge_keeps_unverified_map_inert() -> None:
    message = MessageEnvelope.create(
        message_type=MessageType.CALIBRATION_UPDATE,
        sender="btc-calibrator-v1",
        market_id=MARKET_ID,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="calibration-map-v1",
        policy_version="phase3-policy-v1",
        payload={
            "original_probability": 0.70,
            "calibrated_probability": 0.75,
        },
    )
    evidence = freeze_calibration_message(
        message,
        source_reference="fixture://calibration",
        observed_at_verified=True,
        map_verified=False,
    )
    assert evidence.payload["verified"] is False
    assert evidence.payload["offset"] == 0.0
