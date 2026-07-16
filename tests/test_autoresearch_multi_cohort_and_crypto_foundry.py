from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.crypto_paper_twin import select_price_target
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.crypto_ta_foundry import (
    CryptoTechnicalFoundrySignal,
    technical_foundry_features,
)
from dummy.autoresearch.campaign import run_loop1_campaign
from dummy.autoresearch.ledger_pipeline import (
    LedgerEvidenceRow,
    build_ledger_partition_plan,
)
from dummy.autoresearch.multi_cohort import cohort_base_genome


NOW = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)


def _ohlcv(count: int = 90) -> list[dict[str, float]]:
    rows = []
    for index in range(count):
        close = 100.0 + index * 0.25
        rows.append(
            {
                "open": close - 0.15,
                "high": close + 0.35,
                "low": close - 0.40,
                "close": close,
                "volume": 1000.0 + index * 12.0,
            }
        )
    return rows


def _market(ticker: str, strike: float = 115.0) -> MarketView:
    return MarketView(
        ticker=ticker,
        title="BTC listed target",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=(NOW + timedelta(hours=1)).isoformat(),
        yes_bid=44,
        yes_ask=46,
        no_bid=54,
        no_ask=56,
        volume=1000,
        liquidity=500,
        raw={"strike_type": "greater", "floor_strike": strike},
    )


def test_clean_room_crypto_foundry_is_sparse_bounded_and_challenger_only() -> None:
    rows = _ohlcv()
    features = technical_foundry_features(rows)
    assert features["bar_count"] == 90
    assert -1.0 <= features["score"] <= 1.0
    assert features["active_components"] >= 3
    signal = CryptoTechnicalFoundrySignal(
        fetch_state=lambda _asset: {
            "spot": rows[-1]["close"],
            "dvol": 55.0,
            "minute_ohlcv": rows,
            "hourly_ohlcv": rows,
            "daily_ohlcv": rows,
        },
        hours_to_close=lambda _market: 1.0,
    ).generate(_market("KXBTC-26JUL1513-B115"))
    assert signal is not None
    assert signal.source == "crypto_technical_foundry"
    assert signal.features["challenger_only"] is True
    assert signal.features["promotion_eligible"] is True
    assert abs(signal.features["shift_in_horizon_sigma"]) <= 0.35


def test_hourly_price_target_selection_declares_listed_strike_authority() -> None:
    candidates = []
    for index, ev in enumerate((4.0, 7.0)):
        candidates.append(
            {
                "eligible": True,
                "uncertainty": 0.2,
                "timeframe": "1h",
                "market": _market(f"KXBTC-26JUL1513-B{114 + index}", 114 + index),
                "target": {"valid": True, "target_type": "above", "floor": 114 + index},
                "best": {"side": "yes", "price_cents": 46, "ev_cents": ev},
                "probability_yes": 0.6,
                "market_probability": 0.45,
            }
        )
    selected, ladder = select_price_target(candidates, "recursive")
    assert selected is candidates[1]
    assert ladder["strike_adjustment_enabled"] is True
    assert ladder["strike_adjustment_authority"].endswith("listed_targets_only")
    assert ladder["settlement_informed_selection"] is False


def test_hourly_and_daily_crypto_receive_distinct_strike_aware_genomes() -> None:
    hourly = cohort_base_genome("crypto|btc|price_ladder|hourly")
    daily = cohort_base_genome("crypto|btc|price_ladder|daily+")
    assert hourly is not None and daily is not None
    assert hourly.genome_id != daily.genome_id
    assert hourly.horizon == "hourly"
    assert daily.horizon == "daily+"
    hourly_genes = {gene.name: gene.value for gene in hourly.genes}
    assert hourly_genes["strike.listed_targets_only"] is True
    assert hourly_genes["strike.counterfactual_requires_frozen_ladder"] is True


def _component_row(index: int) -> LedgerEvidenceRow:
    decision = NOW + timedelta(days=index)
    source = "mlb_pa_live_winner"
    return LedgerEvidenceRow.create(
        decision_id=f"decision-{index}",
        market_ticker=f"KXMLBGAME-26JUL{15 + index}CHCCIN-CHC",
        event_cluster_id=f"game-{index}",
        decision_at=decision,
        settlement_received_at=decision + timedelta(hours=8),
        incumbent_probability=0.55,
        market_prior_probability=0.50,
        forecast_uncertainty=0.15,
        result_yes=index % 2 == 0,
        action="BUY_YES",
        side="yes",
        price_cents=50,
        count=1,
        source_family_ids=("market_prior", "sports_elo"),
        fill_count=0,
        settled_pnl_cents=None,
        vertical="sports",
        subject="mlb",
        market_type="winner",
        phase="pre",
        horizon_or_phase="pre",
        market_regime="balanced_40_60",
        forced_coverage=False,
        input_digest=f"input-{index}",
        component_source=source,
        component_probability=0.58,
        component_features_digest=f"features-{index}",
    )


def test_component_lineage_activates_only_across_all_three_partitions(
    tmp_path: Path,
) -> None:
    del tmp_path
    rows = tuple(_component_row(index) for index in range(3))
    scope = "sports|mlb|winner|pre"
    plan = build_ledger_partition_plan(rows, scope=scope)
    base = cohort_base_genome(scope)
    assert base is not None
    report = run_loop1_campaign(
        rows=rows,
        plan=plan,
        base_genome=base,
        created_at=NOW + timedelta(days=4),
        per_experiment_compute_budget=100.0,
    )
    assert report["component_lineage"]["status"] == "ELIGIBLE_REPLAYED"
    assert report["component_lineage"]["experiment_run"] is True
    assert report["genuine_private_candidate_trials"] == 6
    assert "component-evidence" in {
        candidate["lineage_id"] for candidate in report["candidates"]
    }
