from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dummy.chronos import (
    CausalEvent,
    CausalOrderError,
    CausalTimeline,
    ClockDomain,
    TimeEvidence,
    TimestampSource,
    validate_causal_order,
)


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def _evidence(
    seconds: int,
    source: TimestampSource,
    *,
    verified: bool = True,
) -> TimeEvidence:
    return TimeEvidence(
        at=NOW + timedelta(seconds=seconds),
        source=source,
        provenance=f"fixture:{source.value}:{seconds}",
        verified=verified,
    )


def _timeline(**overrides: object) -> CausalTimeline:
    values: dict[str, object] = {
        "domain": ClockDomain.FIFTEEN_MINUTE,
        "observed": _evidence(0, TimestampSource.EXCHANGE),
        "published": _evidence(1, TimestampSource.PROVIDER_VERIFIED),
        "received": _evidence(2, TimestampSource.LOCAL_RECEIPT),
        "decided": _evidence(3, TimestampSource.DECISION_ENGINE),
        "market_close": _evidence(60, TimestampSource.MARKET_SCHEDULE),
        "settled": _evidence(120, TimestampSource.SETTLEMENT_FEED),
    }
    values.update(overrides)
    return CausalTimeline(**values)  # type: ignore[arg-type]


def test_valid_timeline_is_serializable_and_utc() -> None:
    timeline = _timeline()
    payload = timeline.to_dict()
    assert payload["domain"] == "fifteen_minute"
    assert payload["received"]["at"].endswith("Z")  # type: ignore[index,union-attr]


def test_local_receipt_is_verified_by_definition() -> None:
    with pytest.raises(ValueError, match="verified by definition"):
        _evidence(2, TimestampSource.LOCAL_RECEIPT, verified=False)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"observed": _evidence(3, TimestampSource.EXCHANGE)},
            "observation occurs after local receipt",
        ),
        (
            {"decided": _evidence(1, TimestampSource.DECISION_ENGINE)},
            "decision occurs before local receipt",
        ),
        (
            {"decided": _evidence(61, TimestampSource.DECISION_ENGINE)},
            "decision occurs after market close",
        ),
        (
            {"settled": _evidence(59, TimestampSource.SETTLEMENT_FEED)},
            "settlement occurs before market close",
        ),
        (
            {
                "published": _evidence(
                    1,
                    TimestampSource.PROVIDER_VERIFIED,
                    verified=False,
                )
            },
            "unverified publication time",
        ),
        (
            {
                "observed": _evidence(
                    0,
                    TimestampSource.EXCHANGE,
                    verified=False,
                )
            },
            "unverified observation timestamp",
        ),
        (
            {
                "market_close": _evidence(
                    60,
                    TimestampSource.MARKET_SCHEDULE,
                    verified=False,
                )
            },
            "unverified market close timestamp",
        ),
    ],
)
def test_invalid_causal_timelines_fail_closed(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _timeline(**overrides)


def test_settlement_requires_market_close_evidence() -> None:
    with pytest.raises(ValueError, match="settlement requires market close"):
        _timeline(market_close=None)


def test_causal_events_require_parent_before_child() -> None:
    parent = CausalEvent("quote", NOW, NOW)
    child = CausalEvent(
        "forecast",
        NOW + timedelta(seconds=1),
        NOW + timedelta(seconds=2),
        ("quote",),
    )
    assert validate_causal_order([parent, child]) == (parent, child)

    with pytest.raises(CausalOrderError, match="missing before"):
        validate_causal_order([child, parent])


def test_causal_events_reject_duplicate_ids_and_invalid_time() -> None:
    event = CausalEvent("quote", NOW, NOW)
    with pytest.raises(CausalOrderError, match="duplicate event_id"):
        validate_causal_order([event, event])
    with pytest.raises(CausalOrderError, match="after it was recorded"):
        CausalEvent("future", NOW + timedelta(seconds=1), NOW)


def test_clock_domains_are_unique_and_explicit() -> None:
    values = [domain.value for domain in ClockDomain]
    assert len(values) == len(set(values))
    assert {"fifteen_minute", "possession", "inning", "settlement"} <= set(values)
