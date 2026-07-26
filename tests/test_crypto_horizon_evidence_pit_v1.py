from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import pytest

import autonomy.crypto_horizon_evidence as horizon_evidence
from autonomy.crypto_horizon_evidence import (
    CryptoHorizonEvidenceMatrix,
    CryptoHorizonEvidenceStore,
    MalformedCryptoContract,
    PointInTimeViolation,
    deterministic_provenance_hash,
    expanding_window_calibration,
    state_provenance_manifest,
    validate_crypto_contract,
    validate_point_in_time,
)
from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.crypto_spot import CryptoSpotVolSignal


AS_OF = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def _state(offset_seconds: int = -60) -> dict:
    stamp = int((AS_OF + timedelta(seconds=offset_seconds)).timestamp())
    received_at_s = float(AS_OF.timestamp())
    candle = {
        "at_s": stamp, "open_time_s": stamp, "close_time_s": stamp + 60,
        "received_at_s": received_at_s,
        "interval_s": 60, "closed": True,
        "low": 99_900.0, "high": 100_100.0,
        "open": 99_950.0, "close": 100_000.0, "volume": 11.0,
    }
    return {
        "asset": "BTC", "spot": 100_000.0, "coinbase_spot": 100_000.0,
        "kraken_spot": 100_010.0, "hourly_source": "coinbase",
        "received_at_s": received_at_s,
        "hourly_closes": [99_000.0, 100_000.0],
        "daily_closes": [95_000.0, 100_000.0],
        "minute_closes": [99_900.0, 100_000.0], "minute_volumes": [10.0, 11.0],
        "minute_ohlcv": [candle], "five_minute_ohlcv": [],
        "hourly_ohlcv": [], "daily_ohlcv": [],
        "coinbase_hourly_at_s": stamp, "coinbase_minute_at_s": stamp,
        "dvol": 55.0, "dvol_at_ms": stamp * 1000,
        "book_imbalance": 0.1, "microprice_basis_bps": 0.2,
    }


def _market(*, fetched_at: datetime | None = None) -> MarketView:
    return MarketView(
        ticker="KXBTC15M-21JUL261215-15", title="BTC direction",
        vertical=Vertical.CRYPTO, status="open",
        close_time=(AS_OF + timedelta(minutes=15)).isoformat(),
        yes_bid=45, yes_ask=47, no_bid=53, no_ask=55,
        volume=500, liquidity=10_000,
        raw={"open_time": AS_OF.isoformat(), "strike_type": "greater",
             "floor_strike": 100_000},
        fetched_at=(fetched_at or AS_OF - timedelta(seconds=5)).isoformat(),
    )


class _Source:
    name = "pit_fixture"

    def applicable(self, market: MarketView) -> bool:
        return True

    def generate(self, market: MarketView) -> Signal:
        return Signal(
            source=self.name, market_ticker=market.ticker,
            probability_yes=0.7, uncertainty=0.2, rationale="fixture",
            features={"challenger_only": True},
            created_at=(AS_OF - timedelta(seconds=1)).isoformat(),
        )


class _NoFetchHub:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.state_calls: list[str] = []

    def clear(self) -> None:
        self.clear_calls += 1

    def state(self, asset: str) -> dict[str, Any]:
        self.state_calls.append(asset)
        raise AssertionError("supplied-state cycles must not fetch live state")


class _StaticHub:
    def __init__(self, state: dict[str, Any]) -> None:
        self.snapshot = state
        self.clear_calls = 0
        self.state_calls: list[str] = []

    def clear(self) -> None:
        self.clear_calls += 1

    def state(self, asset: str) -> dict[str, Any]:
        self.state_calls.append(asset)
        return self.snapshot


class _CountingSource(_Source):
    def __init__(self, name: str = "counting_fixture") -> None:
        self.name = name
        self.hook_calls = 0
        self.applicable_calls = 0
        self.generate_calls = 0

    def on_cycle_start(self) -> None:
        self.hook_calls += 1

    def applicable(self, market: MarketView) -> bool:
        self.applicable_calls += 1
        return True

    def generate(self, market: MarketView) -> Signal:
        self.generate_calls += 1
        return super().generate(market)


class _StateReadingSource(_Source):
    name = "state_reader"

    def __init__(
        self,
        fetch_state: Callable[[str], dict[str, Any]],
        *,
        mutate: bool = False,
    ) -> None:
        self.fetch_state = fetch_state
        self.mutate = mutate
        self.seen_state: dict[str, Any] | None = None

    def generate(self, market: MarketView) -> Signal:
        self.seen_state = self.fetch_state("BTC")
        observed_hash = deterministic_provenance_hash(self.seen_state)
        if self.mutate:
            self.seen_state["spot"] = 1.0
        signal = super().generate(market)
        return replace(
            signal,
            source=self.name,
            features={"observed_state_hash": observed_hash},
        )


class _ClockReadingSource(_Source):
    name = "clock_reader"

    def __init__(self) -> None:
        self.hours_to_close: Callable[[MarketView], float] = lambda _market: 999.0

    def generate(self, market: MarketView) -> Signal:
        signal = super().generate(market)
        return replace(
            signal,
            source=self.name,
            features={"hours_to_close": self.hours_to_close(market)},
        )


def test_provenance_hash_is_order_independent() -> None:
    left = {"source": "coinbase", "nested": {"b": 2, "a": [1, 2]},
            "observed_at": AS_OF}
    right = {"observed_at": AS_OF, "nested": {"a": [1, 2], "b": 2},
             "source": "coinbase"}
    assert deterministic_provenance_hash(left) == deterministic_provenance_hash(right)
    assert deterministic_provenance_hash(left) != deterministic_provenance_hash(
        {**right, "source": "kraken"}
    )


def test_point_in_time_rejects_future_market_and_source() -> None:
    validate_point_in_time(_market(), _state(), AS_OF)
    with pytest.raises(PointInTimeViolation, match="future source observation"):
        validate_point_in_time(_market(), _state(1), AS_OF)
    with pytest.raises(PointInTimeViolation, match="fetched after as_of"):
        validate_point_in_time(
            _market(fetched_at=AS_OF + timedelta(seconds=1)), _state(), AS_OF
        )


def test_point_in_time_rejects_future_candle_close() -> None:
    state = _state()
    state["minute_ohlcv"][0]["close_time_s"] = AS_OF.timestamp() + 1

    with pytest.raises(
        PointInTimeViolation,
        match=r"future source observation: minute_ohlcv\[0\]\.close_time_s",
    ):
        validate_point_in_time(_market(), state, AS_OF)


def test_point_in_time_rejects_future_candle_receipt() -> None:
    state = _state()
    state["minute_ohlcv"][0]["received_at_s"] = AS_OF.timestamp() + 1

    with pytest.raises(
        PointInTimeViolation,
        match=r"future source observation: minute_ohlcv\[0\]\.received_at_s",
    ):
        validate_point_in_time(_market(), state, AS_OF)


def test_point_in_time_requires_closed_candle_before_receipt() -> None:
    open_state = _state()
    open_state["minute_ohlcv"][0]["closed"] = False
    with pytest.raises(PointInTimeViolation, match="is not a closed candle"):
        validate_point_in_time(_market(), open_state, AS_OF)

    early_receipt = _state()
    early_receipt["minute_ohlcv"][0]["received_at_s"] = (
        early_receipt["minute_ohlcv"][0]["close_time_s"] - 1
    )
    with pytest.raises(PointInTimeViolation, match="received before candle close"):
        validate_point_in_time(_market(), early_receipt, AS_OF)


def test_point_in_time_rejects_future_five_minute_candle_and_tracks_provenance() -> None:
    state = _state()
    future_five_minute = {
        **state["minute_ohlcv"][0],
        "at_s": AS_OF.timestamp() - 299,
        "open_time_s": AS_OF.timestamp() - 299,
        "close_time_s": AS_OF.timestamp() + 1,
        "interval_s": 300,
    }
    state["five_minute_ohlcv"] = [future_five_minute]

    with pytest.raises(
        PointInTimeViolation,
        match=r"future source observation: five_minute_ohlcv\[0\]\.close_time_s",
    ):
        validate_point_in_time(_market(), state, AS_OF)

    future_five_minute["close_time_s"] = AS_OF.timestamp()
    future_five_minute["at_s"] = AS_OF.timestamp() - 300
    future_five_minute["open_time_s"] = AS_OF.timestamp() - 300
    manifest = state_provenance_manifest("BTC", state, AS_OF)
    assert manifest["row_counts"]["five_minute_ohlcv"] == 1
    assert (
        manifest["source_observation_times"][
            "five_minute_ohlcv[0].close_time_s"
        ]
        == AS_OF.isoformat()
    )


def test_matrix_quarantines_future_state_without_scoring(tmp_path) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store, sources=[_Source()], now_fn=lambda: AS_OF
    )
    try:
        report = matrix.run_cycle([_market()], states={"BTC": _state(1)}, as_of=AS_OF)
        assert report["received_at"] == AS_OF.isoformat()
        attempts = store.attempts(cycle_id=report["cycle_id"])
        assert len(attempts) == 1
        assert attempts[0]["status"] == "PIT_REJECTED"
        assert attempts[0]["probability_yes"] is None
        assert report["settled_evidence"]["settled_forecasts"] == 0
    finally:
        matrix.close()


def test_supplied_state_mapping_never_falls_through_to_live_hub(tmp_path) -> None:
    hub = _NoFetchHub()
    source = _CountingSource()
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        hub=hub,
        sources=[source],
        now_fn=lambda: AS_OF,
    )
    try:
        report = matrix.run_cycle([_market()], states={}, as_of=AS_OF)
        attempt = store.attempts(cycle_id=report["cycle_id"])[0]

        assert hub.clear_calls == 0
        assert hub.state_calls == []
        assert source.hook_calls == 0
        assert source.applicable_calls == 0
        assert source.generate_calls == 0
        assert attempt["status"] == "PIT_REJECTED"
        assert attempt["error_type"] == "MissingSuppliedState"
        assert attempt["probability_yes"] is None
    finally:
        matrix.close()


def test_states_none_captures_live_once_before_decision_cutoff(tmp_path) -> None:
    hub = _StaticHub(_state())
    clock = iter(
        [
            AS_OF - timedelta(seconds=2),
            AS_OF + timedelta(seconds=1),
            AS_OF + timedelta(seconds=2),
            AS_OF + timedelta(seconds=3),
        ]
    )
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        hub=hub,
        sources=[_Source()],
        now_fn=lambda: next(clock),
    )
    try:
        report = matrix.run_cycle([_market()])
        attempt = store.attempts(cycle_id=report["cycle_id"])[0]

        assert hub.clear_calls == 1
        assert hub.state_calls == ["BTC"]
        assert attempt["status"] == "EMITTED"
        assert report["received_at"] == (
            AS_OF + timedelta(seconds=2)
        ).isoformat()
    finally:
        matrix.close()


def test_explicit_replay_binds_source_horizon_to_as_of(tmp_path) -> None:
    source = _ClockReadingSource()
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        sources=[source],
        now_fn=lambda: AS_OF + timedelta(days=5),
    )
    try:
        report = matrix.run_cycle(
            [_market()],
            states={"BTC": _state()},
            as_of=AS_OF,
        )
        attempt = store.attempts(cycle_id=report["cycle_id"])[0]
        features = json.loads(attempt["features_json"])
        provenance = json.loads(attempt["provenance_json"])

        assert attempt["status"] == "EMITTED"
        assert features["hours_to_close"] == pytest.approx(0.25)
        assert source.hours_to_close(_market()) == pytest.approx(0.25)
        assert provenance["source_time_cutoff"] == AS_OF.isoformat()
        assert provenance["as_of_at"] == AS_OF.isoformat()
    finally:
        matrix.close()


def test_spot_replay_is_invariant_to_wall_clock_and_binds_event_clock(
    tmp_path,
    monkeypatch,
) -> None:
    replay_as_of = datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc)
    market = replace(
        _market(),
        close_time=(replay_as_of + timedelta(minutes=15)).isoformat(),
        fetched_at=(replay_as_of - timedelta(seconds=5)).isoformat(),
        raw={
            "open_time": replay_as_of.isoformat(),
            "strike_type": "greater",
            "floor_strike": 100_000.0,
        },
    )
    state = _state()
    state["hourly_closes"] = [
        100_000.0 + ((index % 5) - 2) * 500.0 + index * 10.0
        for index in range(40)
    ]
    event_times: list[datetime | None] = []

    def event_bump(now: datetime | None = None) -> float:
        event_times.append(now)
        return 0.04 if now == replay_as_of else 0.0

    monkeypatch.setattr("autonomy.crypto_events.active_bump", event_bump)
    results: list[tuple[float, float, dict[str, Any]]] = []
    for index, wall_clock in enumerate(
        (
            replay_as_of + timedelta(days=1),
            replay_as_of + timedelta(days=365),
        )
    ):
        store = CryptoHorizonEvidenceStore(tmp_path / f"matrix-{index}.db")
        matrix = CryptoHorizonEvidenceMatrix(
            store=store,
            sources=[CryptoSpotVolSignal()],
            now_fn=lambda wall_clock=wall_clock: wall_clock,
        )
        try:
            report = matrix.run_cycle(
                [market],
                states={"BTC": state},
                as_of=replay_as_of,
            )
            attempt = store.attempts(cycle_id=report["cycle_id"])[0]
            results.append(
                (
                    float(attempt["probability_yes"]),
                    float(attempt["uncertainty"]),
                    json.loads(attempt["features_json"]),
                )
            )
        finally:
            matrix.close()

    assert event_times == [replay_as_of, replay_as_of]
    assert results[0] == results[1]
    assert results[0][2]["hours_to_close"] == pytest.approx(0.25)


def test_source_and_provenance_share_one_cycle_owned_snapshot(tmp_path) -> None:
    hub = _NoFetchHub()
    forbidden_calls: list[str] = []

    def forbidden_state(asset: str) -> dict[str, Any]:
        forbidden_calls.append(asset)
        raise AssertionError("prebuilt source callback must be rebound")

    source = _StateReadingSource(forbidden_state)
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        hub=hub,
        sources=[source],
        now_fn=lambda: AS_OF,
    )
    supplied_state = _state()
    try:
        report = matrix.run_cycle(
            [_market()],
            states={"BTC": supplied_state},
            as_of=AS_OF,
        )
        attempt = store.attempts(cycle_id=report["cycle_id"])[0]
        provenance = json.loads(attempt["provenance_json"])

        assert hub.clear_calls == 0
        assert hub.state_calls == []
        assert forbidden_calls == []
        assert attempt["status"] == "EMITTED"
        assert source.seen_state is matrix._cycle_state_hub.state("BTC")
        assert source.seen_state is not supplied_state
        observed_hash = deterministic_provenance_hash(source.seen_state)
        assert attempt["state_hash"] == observed_hash
        assert provenance["state_hash"] == observed_hash
        assert provenance["cycle_state_hashes"] == {"BTC": observed_hash}
        assert json.loads(attempt["features_json"])["observed_state_hash"] == (
            observed_hash
        )
    finally:
        matrix.close()


def test_every_registered_hub_source_uses_matrix_cycle_state(tmp_path) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    prebuilt_sources = horizon_evidence.build_registered_crypto_sources()
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        sources=prebuilt_sources,
        now_fn=lambda: AS_OF,
    )
    state_callback_names = {
        "crypto_empirical_regime",
        "crypto_technical_composite",
        "crypto_technical_foundry",
        "crypto_dvol_implied",
        "crypto_structure_swing",
        "crypto_macro_regime",
        "crypto_equities_flow",
        "crypto_blend_sigma",
        "crypto_vrp_regime",
        "crypto_btc_leadlag",
        "crypto_patience_confirm",
        "crypto_kama_momentum",
    }
    spot_callback_names = {"crypto_spot_vol", "crypto_ewma_t"}
    seen: set[str] = set()
    timed: set[str] = set()
    try:
        for source in matrix.sources:
            source_name = str(source.name)
            if source_name in state_callback_names:
                callback = source.fetch_state
            elif source_name in spot_callback_names:
                callback = source.fetch_spot_and_vol
            elif source_name == "crypto_chartist":
                callback = source._fetch_state
            else:
                continue
            assert getattr(callback, "__self__", None) is matrix._cycle_state_hub
            seen.add(source_name)
            if source_name in spot_callback_names:
                time_callback = source._hours_to_close
                assert (
                    getattr(source.decision_time_fn, "__self__", None)
                    is matrix
                )
            else:
                time_callback = source.hours_to_close
            assert getattr(time_callback, "__self__", None) is matrix
            timed.add(source_name)

        assert seen == state_callback_names | spot_callback_names | {
            "crypto_chartist"
        }
        assert timed == seen
        patience = next(
            source
            for source in matrix.sources
            if source.name == "crypto_patience_confirm"
        )
        assert (
            getattr(patience.parent.fetch_state, "__self__", None)
            is matrix._cycle_state_hub
        )
        debias = next(
            source for source in matrix.sources if source.name == "market_debias"
        )
        assert getattr(debias._market_context, "__self__", None) is matrix
    finally:
        matrix.close()


def test_cycle_rejects_every_emission_if_source_mutates_snapshot(tmp_path) -> None:
    source = _StateReadingSource(lambda _asset: _state(), mutate=True)
    follower = _CountingSource("must_not_consume_mutated_state")
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        sources=[source, follower],
        now_fn=lambda: AS_OF,
    )
    try:
        report = matrix.run_cycle(
            [_market()],
            states={"BTC": _state()},
            as_of=AS_OF,
        )
        attempts = store.attempts(cycle_id=report["cycle_id"])

        assert follower.generate_calls == 0
        assert {attempt["status"] for attempt in attempts} == {"PIT_REJECTED"}
        assert {attempt["error_type"] for attempt in attempts} == {
            "CycleStateMutation"
        }
        assert all(attempt["probability_yes"] is None for attempt in attempts)
        assert all(attempt["state_hash"] is None for attempt in attempts)
        assert report["status"] == "CYCLE_PARTIAL"
    finally:
        matrix.close()


@pytest.mark.parametrize(
    "raw",
    [
        {"strike_type": "greater", "floor_strike": 0.0},
        {"strike_type": "less", "cap_strike": -1.0},
        {"strike_type": "greater", "floor_strike": "nan"},
        {
            "strike_type": "between",
            "floor_strike": 100_000.0,
            "cap_strike": 100_000.0,
        },
        {"strike_type": "greater"},
        {"strike_type": "unsupported", "floor_strike": 100_000.0},
    ],
)
def test_malformed_contract_is_rejected_before_every_source_and_live_fetch(
    tmp_path,
    raw,
) -> None:
    hub = _NoFetchHub()
    sources = [_CountingSource("source_a"), _CountingSource("source_b")]
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store,
        hub=hub,
        sources=sources,
        now_fn=lambda: AS_OF,
    )
    market = replace(
        _market(),
        raw={"open_time": AS_OF.isoformat(), **raw},
    )
    try:
        with pytest.raises(MalformedCryptoContract):
            validate_crypto_contract(market)

        report = matrix.run_cycle([market], as_of=AS_OF)
        attempts = store.attempts(cycle_id=report["cycle_id"])

        assert hub.clear_calls == 0
        assert hub.state_calls == []
        assert len(attempts) == 2
        assert {attempt["status"] for attempt in attempts} == {
            "CONTRACT_REJECTED"
        }
        assert {attempt["error_type"] for attempt in attempts} == {
            "MalformedCryptoContract"
        }
        assert all(attempt["probability_yes"] is None for attempt in attempts)
        assert all(source.hook_calls == 0 for source in sources)
        assert all(source.applicable_calls == 0 for source in sources)
        assert all(source.generate_calls == 0 for source in sources)
        assert report["status"] == "CYCLE_PARTIAL"
    finally:
        matrix.close()


def _settled_row(
    forecast_id: str,
    decision_at: datetime | str,
    settled_at: datetime | str | None,
) -> dict:
    return {
        "forecast_id": forecast_id,
        "as_of_at": (
            decision_at.isoformat() if isinstance(decision_at, datetime) else decision_at
        ),
        "settled_at": (
            settled_at.isoformat() if isinstance(settled_at, datetime) else settled_at
        ),
        "probability_yes": 0.7,
        "market_probability": 0.5,
        "result_yes": 1,
        "event_cluster": f"cluster-{forecast_id}",
    }


def test_expanding_calibration_waits_for_outcome_release_not_forecast_order(
    monkeypatch,
) -> None:
    t0 = AS_OF
    rows = [
        _settled_row("late", t0, t0 + timedelta(hours=4)),
        _settled_row(
            "released", t0 + timedelta(hours=1), t0 + timedelta(hours=2)
        ),
        _settled_row("test", t0 + timedelta(hours=3), t0 + timedelta(hours=5)),
    ]
    fitted_ids: list[list[str]] = []

    def capture_fit(training_rows) -> float:
        fitted_ids.append([str(row["forecast_id"]) for row in training_rows])
        return 0.0

    monkeypatch.setattr(horizon_evidence, "_fit_market_blend", capture_fit)
    report = expanding_window_calibration(rows, min_train=1, min_forward=1)

    # The forecast created first is still unresolved at the test decision. It
    # must not train that decision; only the outcome released at hour 2 may.
    assert fitted_ids[0] == ["released"]
    assert "late" not in fitted_ids[0]
    assert report["forward_forecasts"] == 1
    audit = report["point_in_time_training"]
    assert audit["release_rule"] == "settled_at_strictly_before_test_as_of_at"
    assert audit["training_rows_min"] == 1
    assert audit["training_rows_max"] == 1
    assert audit["earlier_forecast_rows_with_outcomes_unreleased_at_test_decision"] == 2


def test_expanding_calibration_blocks_same_cycle_and_unknown_timestamps(
    monkeypatch,
) -> None:
    t0 = AS_OF
    rows = [
        _settled_row("released", t0, t0 + timedelta(hours=1)),
        _settled_row(
            "equal-boundary",
            t0 + timedelta(minutes=30),
            t0 + timedelta(hours=2),
        ),
        _settled_row("same-a", t0 + timedelta(hours=2), t0 + timedelta(hours=3)),
        _settled_row("same-b", t0 + timedelta(hours=2), t0 + timedelta(hours=3)),
        _settled_row("missing-settlement", t0 - timedelta(hours=1), None),
        _settled_row(
            "naive-decision", "2026-07-21T10:00:00", t0 + timedelta(hours=4)
        ),
    ]
    fitted_ids: list[list[str]] = []

    def capture_fit(training_rows) -> float:
        fitted_ids.append([str(row["forecast_id"]) for row in training_rows])
        return 0.0

    monkeypatch.setattr(horizon_evidence, "_fit_market_blend", capture_fit)
    report = expanding_window_calibration(rows, min_train=1, min_forward=1)

    # Both forecasts in the hour-2 decision batch see exactly the same frozen
    # history. A settlement at the hour-2 boundary is not "strictly before."
    assert fitted_ids[:2] == [["released"], ["released"]]
    assert report["forward_forecasts"] == 2
    audit = report["point_in_time_training"]
    assert audit["same_decision_batch_can_train_each_other"] is False
    assert audit["timestamp_valid_rows"] == 4
    assert audit["timestamp_excluded_rows"] == 2
    assert audit["timestamp_exclusion_reasons"] == {
        "invalid_decision_timestamp": 1,
        "missing_settlement_timestamp": 1,
    }
