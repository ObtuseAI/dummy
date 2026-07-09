from __future__ import annotations


def fixture_ledger():
    from predator_mesh.v17.outcome_ledger import OutcomeLedger

    ledger = OutcomeLedger()
    ledger.append(
        record_type="MARKET_DISCOVERED",
        market_id="KXDEMO-TRUTH",
        event_id="EVT-DEMO",
        domain="sports",
        payload={"event_type": "game_winner"},
        proof_refs=["fixture-market-proof"],
        source_refs=["fixture-source"],
    )
    ledger.append(
        record_type="FORECAST_SNAPSHOT_CREATED",
        market_id="KXDEMO-TRUTH",
        event_id="EVT-DEMO",
        domain="sports",
        payload={"probability": 0.7, "confidence": 0.65},
        proof_refs=["fixture-forecast-proof"],
        source_refs=["fixture-source"],
    )
    ledger.append(
        record_type="OUTCOME_OBSERVED",
        market_id="KXDEMO-TRUTH",
        event_id="EVT-DEMO",
        domain="sports",
        payload={"resolved": True, "outcome": 1.0},
        proof_refs=["fixture-outcome-proof"],
        source_refs=["fixture-settlement-source"],
    )
    return ledger


def fixture_forecasts_and_outcomes():
    from predator_mesh.v17.forecasts import ForecastSnapshot
    from predator_mesh.v17.outcomes import OutcomeObservation, SettlementTruth

    forecasts = [
        ForecastSnapshot(
            market_id="KXDEMO-TRUTH-1",
            event_id="EVT-DEMO-1",
            domain="sports",
            probability=0.7,
            confidence=0.65,
            horizon="1d",
            evidence_stack=["fixture-source"],
            model_refs=["baseline"],
            market_implied_probability=0.6,
        ),
        ForecastSnapshot(
            market_id="KXDEMO-TRUTH-2",
            event_id="EVT-DEMO-2",
            domain="weather",
            probability=0.3,
            confidence=0.55,
            horizon="1d",
            evidence_stack=["fixture-weather"],
            model_refs=["baseline"],
            market_implied_probability=0.4,
        ),
    ]
    outcomes = [
        OutcomeObservation(
            market_id="KXDEMO-TRUTH-1",
            event_id="EVT-DEMO-1",
            domain="sports",
            truth=SettlementTruth.RESOLVED_TRUE,
            confidence="HIGH",
            source_refs=["fixture-settlement"],
        ),
        OutcomeObservation(
            market_id="KXDEMO-TRUTH-2",
            event_id="EVT-DEMO-2",
            domain="weather",
            truth=SettlementTruth.RESOLVED_FALSE,
            confidence="MEDIUM",
            source_refs=["fixture-settlement"],
        ),
    ]
    return forecasts, outcomes
