from __future__ import annotations

from autonomy.backtest import run_backtest
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def test_recent_unsettled_default_source_blocks_canary_capability_not_shadow(
    tmp_path, monkeypatch,
):
    import autonomy.backtest as backtest

    real_gate = backtest._recal_oos_gate
    monkeypatch.setattr(
        backtest,
        "_recal_oos_gate",
        lambda conn, signals, settlements, incumbent: real_gate(
            conn,
            signals,
            settlements,
            incumbent,
            holdout_fraction=0.25,
            min_holdout=1,
            min_holdout_clusters=1,
        ),
    )
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        for index in range(25):
            ticker = f"MTEST-EVENT{index}-CONTRACT"
            result = index % 2 == 0
            ledger.record_signal(Signal(
                source="market_prior",
                market_ticker=ticker,
                probability_yes=0.5,
                uncertainty=0.1,
                rationale="fixture",
            ))
            ledger.record_signal(Signal(
                source="sharp",
                market_ticker=ticker,
                probability_yes=0.9 if result else 0.1,
                uncertainty=0.1,
                rationale="fixture",
            ))
            ledger.record_settlement(ticker, result)
        proven = run_backtest(
            ledger, bootstrap_weights=True, include_diagnostics=False,
        )
        assert proven["recal_oos_gate"]["held_out_improvement_verified"] is True
        assert proven["live_source_capability_matrix"][
            "ready_for_live_canary"
        ] is True

        # Both observations remain accepted on the research tape. Only the
        # default-fusing one is a live-capability blocker while it is ungraded.
        untested_ticker = "MTEST-NEW-EVENT-CONTRACT"
        assert ledger.record_signal(Signal(
            source="untested_default",
            market_ticker=untested_ticker,
            probability_yes=0.7,
            uncertainty=0.2,
            rationale="new default source",
        )) is True
        assert ledger.record_signal(Signal(
            source="untested_challenger",
            market_ticker=untested_ticker,
            probability_yes=0.6,
            uncertainty=0.2,
            rationale="new challenger",
            features={"challenger_only": True},
        )) is True

        report = run_backtest(
            ledger, bootstrap_weights=False, include_diagnostics=False,
        )
        matrix = report["live_source_capability_matrix"]
        default_scope = next(
            scope for scope in matrix["scopes"]
            if scope.startswith("untested_default|")
        )
        challenger_scope = next(
            scope for scope in matrix["scopes"]
            if scope.startswith("untested_challenger|")
        )
        assert matrix["ready_for_live_canary"] is False
        assert default_scope in matrix["blocking_scopes"]
        assert matrix["scopes"][default_scope][
            "requires_live_capability_proof"
        ] is True
        assert matrix["scopes"][challenger_scope][
            "requires_live_capability_proof"
        ] is False
        assert matrix["shadow_collection_allowed"] is True
        assert matrix["fusion_mutated"] is False
        assert matrix["execution_authority"] is False
    finally:
        ledger.close()
