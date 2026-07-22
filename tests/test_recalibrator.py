from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.learner import Learner
from calibration.recalibrator import ProbabilityRecalibrator
from calibration.schema import ForecastRecordV2, SettlementRecord


def _forecast(
    index: int,
    probability: str,
    category: str = "Sports",
    *,
    timestamp: datetime | None = None,
    forecast_id: str | None = None,
) -> ForecastRecordV2:
    return ForecastRecordV2(
        forecast_id=forecast_id or f"f-{index}",
        market_ticker=f"M-{index}",
        contract_ticker=f"M-{index}-YES",
        category=category,
        model_route="test",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal(probability),
        final_probability=Decimal(probability),
        confidence_bucket="medium",
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def test_recalibrator_is_identity_with_insufficient_data(tmp_path):
    recalibrator = ProbabilityRecalibrator(tmp_path / "recalibrator.json", min_samples=3)
    assert recalibrator.fit([], []) is False
    assert recalibrator.apply(Decimal("0.61"), "Sports") == Decimal("0.6100")


def test_recalibrator_corrects_observed_category_bias(tmp_path):
    forecasts = [_forecast(index, "0.30") for index in range(3)]
    settlements = [
        SettlementRecord(
            market_ticker=record.market_ticker,
            contract_ticker=record.contract_ticker,
            outcome=1,
            settled_at=datetime.now(timezone.utc),
            source="test",
        )
        for record in forecasts
    ]
    recalibrator = ProbabilityRecalibrator(tmp_path / "recalibrator.json", min_samples=3)
    assert recalibrator.fit(forecasts, settlements) is True
    # The raw +0.70 correction is capped at +0.15.
    assert recalibrator.apply(Decimal("0.30"), "Sports") == Decimal("0.4500")


def test_equity_rows_cannot_contaminate_global_recalibration(tmp_path):
    base = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
    forecasts = [
        ForecastRecordV2(
            forecast_id=f"equity-{index}",
            market_ticker=f"SPX-{index}",
            contract_ticker=f"SPX-{index}-YES",
            category="Equities",
            model_route="claimed-valuation-model",
            market_implied_probability=Decimal("0.5"),
            dummy_probability=Decimal("0.01"),
            final_probability=Decimal("0.01"),
            confidence_bucket="high",
            timestamp=base,
        )
        for index in range(3)
    ]
    settlements = [
        SettlementRecord(
            market_ticker=forecast.market_ticker,
            contract_ticker=forecast.contract_ticker,
            outcome=1,
            settled_at=base + timedelta(hours=1),
            source="test",
        )
        for forecast in forecasts
    ]
    recalibrator = ProbabilityRecalibrator(
        tmp_path / "recalibrator.json",
        min_samples=1,
    )

    assert recalibrator.fit(forecasts, settlements) is False
    assert recalibrator.sample_counts == {}
    assert recalibrator.apply(Decimal("0.50"), "Sports") == Decimal("0.5000")


def test_recalibrator_ignores_post_settlement_forecasts(tmp_path):
    settled_at = datetime(2026, 7, 17, 20, tzinfo=timezone.utc)
    forecast = _forecast(
        0,
        "0.99",
        timestamp=settled_at + timedelta(seconds=1),
    )
    settlement = SettlementRecord(
        market_ticker=forecast.market_ticker,
        contract_ticker=forecast.contract_ticker,
        outcome=1,
        settled_at=settled_at,
        source="test",
    )
    recalibrator = ProbabilityRecalibrator(
        tmp_path / "recalibrator.json", min_samples=1,
    )

    assert recalibrator.fit([forecast], [settlement]) is False
    assert recalibrator.sample_counts == {}


def test_recalibrator_counts_one_latest_forecast_per_contract(tmp_path):
    base = datetime(2026, 7, 17, 18, tzinfo=timezone.utc)
    duplicates = [
        _forecast(
            0,
            probability,
            category="Crypto",
            timestamp=base + timedelta(minutes=minute),
            forecast_id=f"duplicate-{minute}",
        )
        for minute, probability in enumerate(("0.20", "0.30", "0.40"))
    ]
    first_settlement = SettlementRecord(
        market_ticker="M-0",
        contract_ticker="M-0-YES",
        outcome=1,
        settled_at=base + timedelta(hours=1),
        source="test",
    )
    recalibrator = ProbabilityRecalibrator(
        tmp_path / "recalibrator.json", min_samples=3,
    )

    assert recalibrator.fit(duplicates, [first_settlement]) is False
    assert recalibrator.sample_counts == {"global": 1, "category:crypto": 1}

    unique = [
        _forecast(1, "0.30", category="Crypto", timestamp=base),
        _forecast(2, "0.30", category="Crypto", timestamp=base),
    ]
    settlements = [
        first_settlement,
        *[
            SettlementRecord(
                market_ticker=record.market_ticker,
                contract_ticker=record.contract_ticker,
                outcome=1,
                settled_at=base + timedelta(hours=1),
                source="test",
            )
            for record in unique
        ],
    ]
    assert recalibrator.fit([*duplicates, *unique], settlements) is True
    assert recalibrator.sample_counts == {"global": 3, "category:crypto": 3}
    # The duplicate contract contributes its latest 0.40 forecast once.
    assert recalibrator.apply(Decimal("0.40"), "Crypto") == Decimal("0.5500")


def _signals():
    return [
        {"source": "market_prior", "probability_yes": 0.5, "features": {}},
        {"source": "model", "probability_yes": 0.9, "features": {}},
    ]


def test_correlated_settlements_apply_one_average_multiplier(tmp_path):
    single_ledger = AutonomyLedger(tmp_path / "single.db")
    cluster_ledger = AutonomyLedger(tmp_path / "cluster.db")
    try:
        Learner(single_ledger).apply_settlement("M-0", True, signals=_signals())
        clustered = Learner(cluster_ledger)
        for index in range(5):
            clustered.apply_settlement(
                f"M-{index}", True, signals=_signals(), cluster_weight=0.2
            )
        assert cluster_ledger.get_weight("model") == pytest.approx(
            single_ledger.get_weight("model"), rel=1e-9
        )
    finally:
        single_ledger.close()
        cluster_ledger.close()


def test_equity_settlement_cannot_update_global_or_scoped_trust(tmp_path):
    ledger = AutonomyLedger(tmp_path / "equity.db")
    try:
        learner = Learner(ledger)
        before = ledger.get_weight("model", default=1.0)

        updated = learner.apply_settlement(
            "KXTSLAA-26JUL22-B350",
            True,
            signals=_signals(),
        )

        assert updated == {}
        assert ledger.get_weight("model", default=1.0) == before
    finally:
        ledger.close()


def test_dormant_trust_decays_toward_prior(tmp_path):
    ledger = AutonomyLedger(tmp_path / "decay.db")
    try:
        ledger.update_weight("model", 2.0)
        stale = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        ledger._conn.execute("UPDATE source_trust SET updated_at=? WHERE source='model'", (stale,))
        ledger._conn.commit()
        updated = Learner(ledger).decay_dormant_weights(starvation_days=30)
        assert 1.0 < updated["model"] < 2.0
    finally:
        ledger.close()
