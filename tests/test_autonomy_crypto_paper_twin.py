from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from autonomy.crypto_paper_twin import (
    COHORTS,
    CRYPTO_COVERAGE_LANE,
    CRYPTO_COVERAGE_VERSION,
    HOURLY_CALIBRATED_STRATEGY,
    CryptoPaperTwin,
    PaperTwinLedger,
    ResearchGenome,
    TrustSnapshot,
    _candidate,
    bucket_start,
    cohort_for_market,
    cohort_for_ticker,
    compounding_proposal,
    fit_hourly_calibration_profile,
    forced_crypto_coverage_decision,
    market_listing_duration_hours,
    maker_fill_witness,
    price_target_metadata,
    select_price_target,
    target_candidate_blockers,
    timeframe_state,
)
from autonomy.ontology import Forecast, MarketView, Vertical
from autonomy.signals.commodities_spot import CommoditiesSpotVolSignal
from scripts.run_dummy_crypto_paper_twin import (
    _append_rotating_jsonl,
    _console_summary,
    _summary,
)


NOW = datetime(2026, 7, 10, 7, 15, tzinfo=timezone.utc)


def _market(asset: str, timeframe: str = "1h") -> MarketView:
    strike = {"BTC": 99.0, "ETH": 49.0, "SOL": 24.0}[asset]
    if timeframe == "15m":
        ticker = f"KX{asset}15M-26JUL100730-00"
        close_time = NOW + timedelta(minutes=15)
        open_time = NOW
        strike_type = "greater_or_equal"
    else:
        series = {"BTC": "KXBTCD", "ETH": "KXETHD", "SOL": "KXSOLD"}[asset]
        if timeframe == "1h":
            ticker = f"{series}-26JUL1008-T{strike:g}"
            close_time = NOW + timedelta(minutes=30)
            open_time = close_time - timedelta(hours=1)
        elif timeframe == "1d":
            ticker = f"{series}-26JUL1117-T{strike:g}"
            close_time = NOW + timedelta(days=1)
            open_time = close_time - timedelta(hours=24)
        elif timeframe == "1w":
            ticker = f"{series}-26JUL1717-T{strike:g}"
            close_time = NOW + timedelta(days=5)
            open_time = close_time - timedelta(days=7)
        else:
            raise ValueError(timeframe)
        strike_type = "greater"
    return MarketView(
        ticker=ticker,
        title=f"{asset} {timeframe} threshold",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=close_time.isoformat(),
        yes_bid=40,
        yes_ask=42,
        no_bid=58,
        no_ask=60,
        volume=10_000,
        liquidity=1_000,
        raw={
            "strike_type": strike_type,
            "floor_strike": strike,
            "cap_strike": None,
            "open_time": open_time.isoformat(),
        },
    )


def _state(asset: str) -> dict:
    spot = {"BTC": 100.0, "ETH": 50.0, "SOL": 25.0}[asset]
    minute = [spot * (1.0 + index / 100_000.0) for index in range(350)]
    hourly = [spot * (0.97 + index / 10_000.0) for index in range(350)]
    return {
        "asset": asset,
        "spot": minute[-1],
        "coinbase_spot": minute[-1],
        "kraken_spot": minute[-1] * 1.0001,
        "venue_divergence_bps": 1.0,
        "hourly_closes": hourly,
        "minute_closes": minute,
        "minute_volumes": [100.0 + index for index in range(350)],
        "book_imbalance": 0.2,
        "microprice_basis_bps": 1.5,
        "dvol": 50.0,
        "dvol_at_ms": int(NOW.timestamp() * 1000),
        "coinbase_hourly_at_s": int(NOW.timestamp()),
        "coinbase_minute_at_s": int(NOW.timestamp()),
        "coinbase_hourly_age_s": 0.0,
        "coinbase_minute_age_s": 0.0,
    }


def _commodity_market(asset: str, timeframe: str) -> MarketView:
    series = {
        ("WTI", "1d"): "KXWTI",
        ("NATGAS", "1d"): "KXNATGASD",
        ("GOLD", "1d"): "KXGOLDD",
        ("WTI", "1w"): "KXWTIW",
        ("NATGAS", "1w"): "KXNATGASW",
        ("GOLD", "1w"): "KXGOLDW",
    }[(asset, timeframe)]
    strike = {"WTI": 79.0, "NATGAS": 3.0, "GOLD": 4_500.0}[asset]
    close = NOW + timedelta(days=2 if timeframe == "1d" else 5)
    return MarketView(
        ticker=f"{series}-26JUL15-T{strike:g}",
        title=f"{asset} {timeframe} threshold",
        vertical=Vertical.COMMODITIES,
        status="active",
        close_time=close.isoformat(),
        yes_bid=40,
        yes_ask=42,
        no_bid=58,
        no_ask=60,
        volume=10_000,
        liquidity=1_000,
        raw={"strike_type": "greater", "floor_strike": strike},
    )


class FakeHub:
    def __init__(self):
        self.states = {asset: _state(asset) for asset in ("BTC", "ETH", "SOL")}

    def clear(self):
        return None

    def state(self, asset):
        return self.states[asset]

    def flat_spot_and_vol(self, asset):
        return float(self.states[asset]["spot"]), 0.50

    def ewma_spot_and_vol(self, asset):
        return float(self.states[asset]["spot"]), 0.50


class FakeScanner:
    def scan(self):
        crypto = [
            _market(asset, timeframe)
            for timeframe in ("15m", "1h", "1d", "1w")
            for asset in ("BTC", "ETH", "SOL")
        ]
        commodities = [
            _commodity_market(asset, timeframe)
            for timeframe in ("1d", "1w")
            for asset in ("WTI", "NATGAS", "GOLD")
        ]
        return crypto + commodities


def _twin(tmp_path, *, now=NOW, results=None, trades=None):
    ledger = PaperTwinLedger(tmp_path / "paper.db")
    return CryptoPaperTwin(
        ledger=ledger,
        scanner=FakeScanner(),
        hub=FakeHub(),
        commodity_signal=CommoditiesSpotVolSignal(
            fetch_spot_and_vol=lambda symbol: {
                "CL=F": (80.0, 0.35),
                "NG=F": (3.2, 0.45),
                "GC=F": (4_600.0, 0.25),
            }[symbol],
        ),
        trust=TrustSnapshot({
            "market_prior@CRYPTO": 0.1,
            "crypto_spot_vol@CRYPTO": 8.0,
            "crypto_ewma_t@CRYPTO": 8.0,
        }),
        fetch_result=lambda ticker: (results or {}).get(ticker, {}),
        fetch_orderbook=lambda ticker: {"yes": [[41, 5]], "no": [[59, 5]]},
        fetch_trades=lambda ticker, start, end: list(trades or []),
        now_fn=lambda: now,
        proposed_genome_path=tmp_path / "missing.json",
    )


def test_parallel_paper_cycle_records_explanations_and_never_has_authority(tmp_path):
    twin = _twin(tmp_path)
    try:
        report = twin.run_cycle()
        assert report["status"] == "CYCLE_OK"
        assert report["observations_written"] == 57
        assert report["trades_opened"] >= 6
        assert set(report["lanes"]) == {"15m", "1h", "1d", "1w"}
        assert set(report["cohorts"]) == {"CRYPTO", "COMMODITIES"}
        assert set(report["cohorts"]["COMMODITIES"]) == {"1d", "1w"}
        assert report["authority"]["independent_of_shadow_or_live_session"] is True
        assert report["authority"]["continues_during_authorized_live_operation"] is True
        assert report["authority"]["execution_authority"] is False
        assert report["authority"]["capital_authority"] is False
        assert report["evidence_quarantine"]["counts_toward_canary"] is False
        forced = report["forced_crypto_coverage"]
        assert forced["designated_scopes"] == 12
        assert forced["scopes_observed_this_cycle"] == 12
        assert forced["coverage_gap_count"] == 0
        assert forced["targets_observed_this_cycle"] == 12
        assert forced["forced_trades_recorded_this_cycle"] == 12
        assert forced["summary"]["open_decisions"] == 12
        assert forced["counts_toward_promotion"] is False
        assert forced["counts_toward_readiness"] is False
        assert all(row["counts_toward_promotion"] is False for row in forced["matrix"])
        assert twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM crypto_coverage_trades "
            "WHERE counts_toward_promotion!=0 OR counts_toward_readiness!=0 "
            "OR broker_contacted!=0"
        ).fetchone()[0] == 0
        assert twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM trades WHERE strategy=?",
            (CRYPTO_COVERAGE_LANE,),
        ).fetchone()[0] == 0
        assert CRYPTO_COVERAGE_LANE not in report["timeframe_comparison"]
        assert report["hourly_calibration"]["profile"]["model_share"] == 0.0
        assert report["hourly_calibration"]["profile"]["status"] == (
            "COLLECTING_FORWARD_EVIDENCE"
        )
        assert report["hourly_calibration"]["forward_ledger"]["forecasts"] == 3
        assert report["hourly_calibration"]["production_effect"] == "none"
        assert report["hourly_calibration"]["execution_authority"] is False
        assert report["lanes"]["1h"][HOURLY_CALIBRATED_STRATEGY]["trades"] == 0
        assert report["phase_2_forward_selection"]["candidate_gates"]["15m"]["recursive"][
            "auto_apply"
        ] is False
        assert any(
            "diagnostic-only" in blocker
            for blocker in report["phase_2_forward_selection"]["candidate_gates"]["15m"][
                "exploratory"
            ]["blockers"]
        )
        assert report["phase_3_execution"]["policy_challengers"]["execution_authority"] is False
        throughput = report["phase_3_execution"]["throughput_classes"]
        assert throughput, "cycle report must classify throughput"
        assert sum(throughput.values()) == report["observations_written"]
        # No observation should carry the legacy unclassified reason as its class.
        assert set(throughput) <= {
            "traded", "policy_rejected", "no_listed_market",
            "no_two_sided_book", "forecast_incomplete",
        }
        explanations = report["recent_explanations"]
        assert explanations
        assert all("Paper-only" in row["explanation"] or "No paper order" in row["explanation"]
                   for row in explanations)
        routed = {
            (row["timeframe"], row["asset"], row["ticker"])
            for row in twin.ledger.connection.execute(
                "SELECT timeframe,asset,ticker FROM observations "
                "WHERE vertical='CRYPTO' AND ticker IS NOT NULL"
            )
        }
        assert {asset for _timeframe, asset, _ticker in routed} == {"BTC", "ETH", "SOL"}
        assert all("15M-" in ticker for timeframe, _asset, ticker in routed if timeframe == "15m")
        assert all("15M-" not in ticker for timeframe, _asset, ticker in routed if timeframe == "1h")
        weekly_routed = twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM observations WHERE vertical='CRYPTO' "
            "AND timeframe='1w' AND ticker IS NOT NULL"
        ).fetchone()[0]
        assert weekly_routed == 9
        commodity_observations = twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM observations WHERE vertical='COMMODITIES' "
            "AND timeframe IN ('1d','1w') AND ticker IS NOT NULL"
        ).fetchone()[0]
        assert commodity_observations == 18
        assert report["phase_4_canary_decision"]["gates_by_vertical"][
            "COMMODITIES"
        ]["1d"]["incumbent"]["live_canary_ready"] is False
    finally:
        twin.close()


def test_same_lane_never_pyramids_same_asset_expiry(tmp_path):
    twin = _twin(tmp_path)
    try:
        first = twin.run_cycle()
        first_count = first["trades_opened"]
        first_forced = first["forced_crypto_trades_recorded"]
        second = twin.run_cycle()
        assert first_count > 0
        assert first_forced == 12
        assert second["trades_opened"] == 0
        assert second["forced_crypto_trades_recorded"] == 0
        assert second["observations_written"] == 57
        assert second["hourly_calibration_forecasts_recorded"] == 0
    finally:
        twin.close()


def test_legacy_hourly_contracts_are_preserved_outside_native_15m_cohort(tmp_path):
    twin = _twin(tmp_path)
    try:
        twin.run_cycle()
        twin.ledger.connection.execute(
            "UPDATE observations SET ticker='KXBTCD-26JUL1008-T99' "
            "WHERE timeframe='15m' AND ticker IS NOT NULL"
        )
        twin.ledger.connection.execute(
            "UPDATE trades SET ticker='KXBTCD-26JUL1008-T99' WHERE timeframe='15m'"
        )
        twin.ledger.connection.commit()
    finally:
        twin.close()

    ledger = PaperTwinLedger(tmp_path / "paper.db")
    try:
        quarantine = ledger.legacy_quarantine_summary()
        assert quarantine["observations"] > 0
        assert quarantine["trades"] > 0
        assert ledger.lane_summary("exploratory", "15m")["trades"] == 0
    finally:
        ledger.close()


def test_settlement_uses_simulated_taker_quote_and_keeps_paper_quarantined(tmp_path):
    first = _twin(tmp_path)
    try:
        report = first.run_cycle()
        assert report["trades_opened"] > 0
    finally:
        first.close()
    results = {
        _market(asset, timeframe).ticker: {"result": "yes"}
        for timeframe in ("15m", "1h", "1d", "1w")
        for asset in ("BTC", "ETH", "SOL")
    }
    results.update({
        _commodity_market(asset, timeframe).ticker: {"result": "yes"}
        for timeframe in ("1d", "1w")
        for asset in ("WTI", "NATGAS", "GOLD")
    })
    second = _twin(tmp_path, now=NOW + timedelta(hours=1), results=results)
    try:
        report = second.run_cycle()
        assert report["settlements_recorded"] > 0
        assert report["forced_crypto_settlements_recorded"] == 12
        assert report["forced_crypto_coverage"]["summary"]["settled_decisions"] == 12
        assert report["hourly_calibration_settlements_recorded"] == 3
        assert report["hourly_calibration"]["forward_ledger"][
            "settled_event_clusters"
        ] == 1
        settled = sum(
            lane[strategy]["settled_trades"]
            for lane in report["lanes"].values()
            for strategy in ("incumbent", "recursive", "exploratory")
        )
        assert settled > 0
        assert report["phase_4_canary_decision"]["live_canary_ready"] is False
    finally:
        second.close()


def test_maker_fill_requires_public_trade_through_or_queue_consumption():
    order = {
        "side": "yes",
        "maker_price_cents": 41,
        "maker_queue_ahead": 5.0,
        "maker_queue_snapshot": 1,
        "created_at": NOW.isoformat(),
        "maker_expires_at": (NOW + timedelta(minutes=1)).isoformat(),
    }
    no_fill = maker_fill_witness(order, [{
        "taker_book_side": "ask",
        "yes_price_dollars": "0.41",
        "count_fp": "5",
        "created_time": (NOW + timedelta(seconds=30)).isoformat(),
    }])
    assert no_fill is None
    fill = maker_fill_witness(order, [{
        "taker_book_side": "ask",
        "yes_price_dollars": "0.40",
        "count_fp": "1",
        "trade_id": "public-1",
        "created_time": (NOW + timedelta(seconds=30)).isoformat(),
    }])
    assert fill["reason"] == "public_trade_through"


def test_later_cycle_reconciles_maker_lane_from_public_prints(tmp_path):
    first = _twin(tmp_path)
    try:
        opened = first.run_cycle()
        assert opened["trades_opened"] > 0
    finally:
        first.close()
    public_print = {
        "taker_book_side": "ask",
        "yes_price_dollars": "0.40",
        "no_price_dollars": "0.58",
        "count_fp": "20",
        "trade_id": "public-through",
        "created_time": (NOW + timedelta(seconds=30)).isoformat(),
    }
    second = _twin(tmp_path, now=NOW + timedelta(minutes=2), trades=[public_print])
    try:
        report = second.run_cycle()
        assert report["maker_updates"] > 0
        maker_fills = sum(
            lane[strategy]["maker_fills"]
            for lane in report["lanes"].values()
            for strategy in ("incumbent", "recursive", "exploratory")
        )
        assert maker_fills > 0
    finally:
        second.close()


def test_timeframe_inputs_are_distinct_and_recursive_epoch_is_frozen(tmp_path):
    state = _state("BTC")
    fast = timeframe_state(state, "15m")
    hourly = timeframe_state(state, "1h")
    assert fast["minute_closes"]
    assert hourly["minute_closes"] == []

    ledger = PaperTwinLedger(tmp_path / "paper.db")
    try:
        first = ledger.ensure_epoch(
            ResearchGenome(0.75, 8, 0.25, 75), now=NOW,
        )
        second = ledger.ensure_epoch(
            ResearchGenome(0.50, 12, 0.18, 65), now=NOW + timedelta(hours=1),
        )
        assert second["epoch_id"] == first["epoch_id"]
        assert json.loads(second["genome_json"])["shrinkage"] == 0.75
    finally:
        ledger.close()


def test_native_15m_keeps_final_four_minutes_while_hourly_retains_cutoff(tmp_path):
    twin = _twin(tmp_path)
    try:
        native = replace(
            _market("BTC", "15m"),
            close_time=(NOW + timedelta(minutes=4)).isoformat(),
        )
        hourly = replace(
            _market("BTC", "1h"),
            close_time=(NOW + timedelta(minutes=4)).isoformat(),
        )
        assert twin._markets_for_asset([native], "BTC", "15m", NOW) == [native]
        assert twin._markets_for_asset([hourly], "BTC", "1h", NOW) == []
    finally:
        twin.close()


def test_price_target_metadata_supports_kalshi_thresholds_buckets_and_direction():
    above = _market("BTC", "1h")
    below = replace(
        above,
        raw={**above.raw, "strike_type": "less", "floor_strike": None,
             "cap_strike": 101.0},
    )
    bucket = replace(
        above,
        raw={**above.raw, "strike_type": "between", "floor_strike": 99.0,
             "cap_strike": 101.0},
    )
    direction = _market("BTC", "15m")
    invalid_direction = replace(
        direction,
        raw={**direction.raw, "floor_strike": None},
    )

    assert price_target_metadata(above, "1h")["target_type"] == "above"
    assert price_target_metadata(below, "1h")["target_type"] == "below"
    assert price_target_metadata(bucket, "1h")["target_type"] == "bucket"
    assert price_target_metadata(direction, "15m")["valid"] is True
    assert price_target_metadata(invalid_direction, "15m") == {
        "contract_family": "15m_direction",
        "target_type": "opening_reference_direction",
        "strike_type": "greater_or_equal",
        "floor": None,
        "cap": None,
        "label": "invalid or missing opening reference",
        "valid": False,
        "invalid_reason": "missing_valid_15m_opening_reference",
    }


def test_target_selector_prefers_an_eligible_target_over_blocked_higher_ev():
    blocked_market = _market("BTC", "1h")
    eligible_market = replace(
        blocked_market,
        ticker="KXBTCD-26JUL1008-T101",
        raw={**blocked_market.raw, "floor_strike": 101.0},
    )
    candidates = [
        {
            "eligible": False,
            "reason": "entry 90c>75c",
            "market": blocked_market,
            "target": price_target_metadata(blocked_market, "1h"),
            "probability_yes": 0.95,
            "market_probability": 0.60,
            "uncertainty": 0.10,
            "best": {"side": "yes", "price_cents": 70, "ev_cents": 20.0},
        },
        {
            "eligible": True,
            "reason": "eligible",
            "market": eligible_market,
            "target": price_target_metadata(eligible_market, "1h"),
            "probability_yes": 0.65,
            "market_probability": 0.55,
            "uncertainty": 0.10,
            "best": {"side": "yes", "price_cents": 50, "ev_cents": 4.0},
        },
    ]

    selected, audit = select_price_target(candidates, "incumbent")

    assert selected["market"].ticker == eligible_market.ticker
    assert audit["targets_evaluated"] == 2
    assert audit["eligible_targets"] == 1
    assert audit["ranked_candidates"][0]["selected"] is True
    assert audit["optimizes_raw_win_rate"] is False


def test_target_candidate_can_choose_no_and_invalid_strikes_fail_closed():
    market = replace(
        _market("BTC", "1h"),
        yes_bid=80, yes_ask=82, no_bid=18, no_ask=20,
    )
    forecast = Forecast(
        market_ticker=market.ticker,
        probability_yes=0.10,
        uncertainty=0.05,
        sources_used={"fixture": 1.0},
        market_implied_yes=0.81,
        edge_yes=-0.71,
        rationale="fixture",
    )

    candidate = _candidate(
        market, forecast, None, strategy="incumbent", timeframe="1h",
        genome=ResearchGenome(0.75, 8, 0.25, 75),
    )
    invalid_market = replace(
        market,
        raw={**market.raw, "floor_strike": None},
    )
    invalid = _candidate(
        invalid_market, forecast, None, strategy="incumbent", timeframe="1h",
        genome=ResearchGenome(0.75, 8, 0.25, 75),
    )

    assert candidate["eligible"] is True
    assert candidate["best"]["side"] == "no"
    assert invalid["eligible"] is False
    assert invalid["reason"] == "missing_valid_floor_strike"


def test_forced_crypto_coverage_chooses_a_side_but_never_promotes():
    market = _market("BTC", "15m")
    forecast = Forecast(
        market_ticker=market.ticker,
        probability_yes=0.52,
        uncertainty=0.20,
        sources_used={"fixture": 1.0},
        market_implied_yes=0.50,
        edge_yes=0.02,
        rationale="fixture",
    )
    candidate = _candidate(
        market, forecast, None, strategy="exploratory", timeframe="15m",
        genome=ResearchGenome(0.75, 8, 0.25, 75),
    )
    candidate["eligible"] = False
    candidate["reason"] = "conservative EV below normal gate"
    candidate["event_cluster"] = "coverage-cluster"

    forced = forced_crypto_coverage_decision(candidate, "BTC")

    assert forced["coverage_version"] == CRYPTO_COVERAGE_VERSION
    assert forced["lane"] == CRYPTO_COVERAGE_LANE
    assert forced["side"] in {"yes", "no"}
    assert forced["normal_policy_eligible"] is False
    assert forced["counts_toward_promotion"] is False
    assert forced["counts_toward_readiness"] is False
    assert "FORCED PAPER" in forced["explanation"]
    assert "excluded from model promotion" in forced["explanation"]


def _hourly_target_ladder(asset: str) -> list[MarketView]:
    base = _market(asset, "1h")
    series = {"BTC": "KXBTCD", "ETH": "KXETHD", "SOL": "KXSOLD"}[asset]
    center = {"BTC": 100.0, "ETH": 50.0, "SOL": 25.0}[asset]
    return [
        replace(
            base,
            ticker=f"{series}-26JUL1008-T{center * 0.98:g}",
            yes_bid=20, yes_ask=22, no_bid=78, no_ask=80,
            raw={**base.raw, "strike_type": "less", "floor_strike": None,
                 "cap_strike": center * 0.98},
        ),
        replace(
            base,
            ticker=f"{series}-26JUL1008-B{center:g}",
            yes_bid=35, yes_ask=37, no_bid=63, no_ask=65,
            raw={**base.raw, "strike_type": "between", "floor_strike": center * 0.99,
                 "cap_strike": center * 1.01},
        ),
        replace(
            base,
            ticker=f"{series}-26JUL1008-T{center * 1.02:g}",
            yes_bid=25, yes_ask=27, no_bid=73, no_ask=75,
            raw={**base.raw, "strike_type": "greater", "floor_strike": center * 1.02,
                 "cap_strike": None},
        ),
        replace(
            base,
            ticker=f"{series}-26JUL1008-T{center * 1.04:g}",
            yes_bid=None, yes_ask=1, no_bid=99, no_ask=None,
            raw={**base.raw, "strike_type": "greater", "floor_strike": center * 1.04,
                 "cap_strike": None},
        ),
    ]


class TargetLadderScanner(FakeScanner):
    def scan(self):
        markets = super().scan()
        markets = [
            market for market in markets
            if not (
                market.vertical is Vertical.CRYPTO
                and cohort_for_market(market).timeframe == "1h"
            )
        ]
        return markets + [
            market
            for asset in ("BTC", "ETH", "SOL")
            for market in _hourly_target_ladder(asset)
        ]


def test_cycle_audits_and_selects_full_hourly_target_ladder_for_all_crypto(tmp_path):
    twin = _twin(tmp_path)
    twin.scanner = TargetLadderScanner()
    try:
        report = twin.run_cycle()
        rows = twin.ledger.connection.execute(
            "SELECT asset,ticker,diagnostics_json FROM observations "
            "WHERE cycle_id=? AND vertical='CRYPTO' AND timeframe='1h' "
            "AND strategy='incumbent' ORDER BY asset",
            (report["cycle_id"],),
        ).fetchall()

        assert {str(row["asset"]) for row in rows} == {"BTC", "ETH", "SOL"}
        for row in rows:
            audit = json.loads(str(row["diagnostics_json"]))["price_target_selection"]
            assert audit["targets_evaluated"] == 3
            assert audit["valid_targets"] == 3
            assert audit["target_type_counts"] == {"above": 1, "below": 1, "bucket": 1}
            assert audit["listed_targets_seen"] == 4
            assert audit["listed_valid_targets"] == 4
            assert audit["listed_complete_two_sided_quotes"] == 3
            assert audit["listed_target_type_counts"] == {
                "above": 2, "below": 1, "bucket": 1,
            }
            assert audit["listed_targets_excluded_from_scoring"] == 1
            assert audit["selected_ticker"] == row["ticker"]
            assert sum(item["selected"] for item in audit["ranked_candidates"]) == 1
        current = report["price_target_selection"]["current_cycle"]
        assert {row["asset"] for row in current if row["timeframe"] == "1h"} == {
            "BTC", "ETH", "SOL",
        }
        assert report["price_target_selection"]["raw_win_rate_is_not_the_objective"] is True
        forced_hourly = [
            row for row in report["forced_crypto_coverage"]["matrix"]
            if row["timeframe"] == "1h"
        ]
        assert sum(row["targets_observed_this_cycle"] for row in forced_hourly) == 9
        assert twin.ledger.connection.execute(
            "SELECT COUNT(*) FROM crypto_coverage_trades WHERE timeframe='1h'"
        ).fetchone()[0] == 9
        duplicate_positions = twin.ledger.connection.execute(
            "SELECT strategy,asset,event_cluster,COUNT(*) FROM trades "
            "WHERE vertical='CRYPTO' AND timeframe='1h' "
            "GROUP BY strategy,asset,event_cluster HAVING COUNT(*)>1"
        ).fetchall()
        assert duplicate_positions == []
    finally:
        twin.close()


def test_target_candidates_freeze_and_settle_rejected_target_regret(tmp_path):
    first = _twin(tmp_path)
    first.scanner = TargetLadderScanner()
    try:
        initial = first.run_cycle()
        rows = first.ledger.connection.execute(
            "SELECT asset,ticker,rank_selected,eligible,reason FROM target_candidate_forecasts "
            "WHERE vertical='CRYPTO' AND timeframe='1h' AND strategy='incumbent' "
            "ORDER BY asset,ticker"
        ).fetchall()
        assert len(rows) == 9
        assert sum(int(row["rank_selected"]) for row in rows) == 3
        assert all(int(row["eligible"]) in {0, 1} for row in rows)
        assert initial["target_candidate_forecasts_recorded"] >= 36
    finally:
        first.close()

    results = {
        market.ticker: {"result": "yes"}
        for asset in ("BTC", "ETH", "SOL")
        for market in _hourly_target_ladder(asset)
    }
    second = _twin(tmp_path, now=NOW + timedelta(hours=1), results=results)
    second.scanner = TargetLadderScanner()
    try:
        report = second.run_cycle()
        settled = second.ledger.connection.execute(
            "SELECT COUNT(*) FROM target_candidate_forecasts "
            "WHERE vertical='CRYPTO' AND timeframe='1h' AND result_yes IS NOT NULL"
        ).fetchone()[0]
        regret = report["price_target_selection"]["rejection_regret"]
        assert report["target_candidate_settlements_recorded"] >= 36
        assert settled >= 36
        assert regret["counts"]["settled_forecasts"] >= 36
        assert regret["blocker_diagnostics"]
        assert regret["counterfactual_is_fill_evidence"] is False
        assert regret["automatic_gate_tuning"] is False
        assert regret["execution_authority"] is False
        settled_rows = second.ledger.connection.execute(
            "SELECT asset,rank_selected,eligible,reason FROM target_candidate_forecasts "
            "WHERE vertical='CRYPTO' AND timeframe='1h' AND strategy='incumbent' "
            "AND result_yes IS NOT NULL"
        ).fetchall()
        expected: dict[str, int] = {}
        for row in settled_rows:
            if not bool(row["rank_selected"]) or not bool(row["eligible"]):
                for blocker in target_candidate_blockers(
                    str(row["reason"]), eligible=bool(row["eligible"]),
                ):
                    key = f"CRYPTO:{row['asset']}:1h:incumbent:{blocker}"
                    expected[key] = expected.get(key, 0) + 1
        actual = {
            str(item["group"]): int(item["settled_forecasts"])
            for item in regret["blocker_diagnostics"]
            if ":1h:incumbent:" in str(item["group"])
        }
        assert expected
        assert all(actual.get(key) == count for key, count in expected.items())
    finally:
        second.close()


def test_exact_crypto_and_commodity_horizon_allowlist():
    crypto = {
        (cohort.asset, cohort.timeframe)
        for cohort in COHORTS if cohort.vertical is Vertical.CRYPTO
    }
    commodities = {
        (cohort.asset, cohort.timeframe)
        for cohort in COHORTS if cohort.vertical is Vertical.COMMODITIES
    }
    assert crypto == {
        (asset, timeframe)
        for asset in ("BTC", "ETH", "SOL")
        for timeframe in ("15m", "1h", "1d", "1w")
    }
    assert commodities == {
        (asset, timeframe)
        for asset in ("WTI", "NATGAS", "GOLD")
        for timeframe in ("1d", "1w")
    }
    assert cohort_for_ticker("KXDOGE15M-26JUL100430-30") is None
    assert cohort_for_ticker("KXBTCMAXW-26JUL10-T80000") is None
    assert cohort_for_ticker("KXBTCD-26JUL1017-T63999.99") is None
    assert cohort_for_ticker("KXWTIW-26JUL1014-T75.99").asset == "WTI"
    assert cohort_for_market(_market("BTC", "1h")).timeframe == "1h"
    assert cohort_for_market(_market("BTC", "1d")).timeframe == "1d"
    assert cohort_for_market(_market("BTC", "1w")).timeframe == "1w"
    monday = datetime(2026, 7, 6, tzinfo=timezone.utc)
    assert bucket_start(NOW, "1w") == monday.isoformat()


def test_kalshi_weekly_btc_listing_is_routed_from_event_duration():
    market = MarketView(
        ticker="KXBTCD-26JUL1017-T63999.99",
        title="Bitcoin price on Jul 10, 2026?",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time="2026-07-10T21:00:00+00:00",
        yes_bid=55,
        yes_ask=57,
        no_bid=43,
        no_ask=45,
        volume=3_250_909,
        liquidity=1_000,
        raw={
            "open_time": "2026-07-03T20:00:00Z",
            "strike_type": "greater",
            "floor_strike": 63_999.99,
            "cap_strike": None,
        },
    )

    assert market_listing_duration_hours(market) == 169.0
    assert cohort_for_market(market).timeframe == "1w"


def test_compounding_and_canary_outputs_never_grant_live_authority():
    proposal = compounding_proposal([])
    assert proposal["capital_authority"] is False
    assert proposal["live_application"] is False


def _hourly_calibration_row(
    index: int,
    *,
    raw_probability: float,
    market_probability: float,
    outcome: int | None,
) -> dict:
    return {
        "forecast_id": f"forecast-{index}",
        "event_cluster": f"cluster-{index}",
        "observed_at": (NOW + timedelta(hours=index)).isoformat(),
        "settled_at": (NOW + timedelta(hours=index + 1)).isoformat(),
        "raw_probability": raw_probability,
        "market_probability": market_probability,
        "result_yes": outcome,
    }


def test_hourly_calibration_zero_weights_a_harmful_model():
    rows = [
        _hourly_calibration_row(
            index,
            raw_probability=0.20 if index % 2 else 0.80,
            market_probability=0.80 if index % 2 else 0.20,
            outcome=index % 2,
        )
        for index in range(30)
    ]

    profile = fit_hourly_calibration_profile(rows)

    assert profile.status == "MARKET_ANCHORED_HOLD"
    assert profile.fitted_model_share == 0.0
    assert profile.model_share == 0.0
    assert profile.walk_forward_forecasts == 20
    assert profile.walk_forward_advantage_ci95["lower"] == 0.0


def test_hourly_calibration_requires_positive_later_walk_forward_evidence():
    rows = [
        _hourly_calibration_row(
            index,
            raw_probability=0.90 if index % 2 else 0.10,
            market_probability=0.50,
            outcome=index % 2,
        )
        for index in range(30)
    ]
    # An unresolved future row must not influence the fitted profile.
    rows.append(_hourly_calibration_row(
        99, raw_probability=0.01, market_probability=0.99, outcome=None,
    ))

    profile = fit_hourly_calibration_profile(rows)

    assert profile.status == "ACTIVE_FORWARD_CALIBRATION"
    assert profile.model_share == 0.5
    assert profile.settled_forecasts == 30
    assert profile.event_clusters == 30
    assert profile.walk_forward_advantage_ci95["lower"] > 0
    assert profile.fitted_through == rows[29]["settled_at"]


def test_scheduler_summary_preserves_dashboard_contract_without_heavy_sections(tmp_path):
    report = {
        "report_name": "crypto-paper-twin",
        "cycle_id": "cycle-1",
        "started_at": NOW.isoformat(),
        "completed_at": (NOW + timedelta(seconds=10)).isoformat(),
        "status": "CYCLE_OK",
        "markets_seen": 12,
        "observations_written": 4,
        "trades_opened": 1,
        "settlements_recorded": 2,
        "target_candidate_forecasts_recorded": 7,
        "target_candidate_settlements_recorded": 3,
        "lanes": {"BTC_1h": {"status": "ACTIVE"}},
        "cohorts": [{"asset": "BTC", "timeframe": "1h"}],
        "price_target_selection": {
            "rejection_regret": {"counts": {"candidate_forecasts": 7}}
        },
        "forced_crypto_coverage": {
            "designated_scopes": 12,
            "scopes_observed_this_cycle": 10,
            "coverage_gap_count": 2,
            "summary": {"open_decisions": 11},
        },
        "authority": {
            "broker_contacted": False,
            "execution_authority": False,
            "capital_authority": False,
        },
        "errors": [],
        "phase_3_execution": {"large_trace": "x" * 500_000},
        "recent_explanations": [{"large_trace": "y" * 500_000}],
    }

    summary = _summary(report, tmp_path / "full-report.json")
    console = _console_summary(summary)

    assert summary["paper_mode"] == "LIVE_PUBLIC_READ_ONLY_SIMULATION"
    assert summary["lanes"] == report["lanes"]
    assert summary["cohorts"] == report["cohorts"]
    assert summary["target_candidate_counts"] == {"candidate_forecasts": 7}
    assert summary["forced_crypto_coverage"]["summary"]["open_decisions"] == 11
    assert "phase_3_execution" not in summary
    assert "recent_explanations" not in summary
    assert len(json.dumps(summary)) < 100_000
    assert "lanes" not in console
    assert console["execution_authority"] is False
    assert len(json.dumps(console)) < 4_000


def test_scheduler_jsonl_log_rotates_and_stays_bounded(tmp_path):
    log = tmp_path / "scheduler.jsonl"
    log.write_text("x" * 1_024, encoding="utf-8")

    _append_rotating_jsonl(log, {"cycle_id": "cycle-1"}, max_bytes=1_024, backups=2)

    assert (tmp_path / "scheduler.jsonl.1").stat().st_size == 1_024
    assert json.loads(log.read_text(encoding="utf-8"))["cycle_id"] == "cycle-1"

    log.write_text("y" * 1_024, encoding="utf-8")
    _append_rotating_jsonl(log, {"cycle_id": "cycle-2"}, max_bytes=1_024, backups=2)

    assert (tmp_path / "scheduler.jsonl.2").stat().st_size == 1_024
    assert json.loads(log.read_text(encoding="utf-8"))["cycle_id"] == "cycle-2"


def _obs_row(strategy, action, diagnostics, cycle_id="c1"):
    return {
        "cycle_id": cycle_id,
        "strategy": strategy,
        "vertical": Vertical.CRYPTO,
        "timeframe": "1h",
        "bucket_start": "2026-07-10T00:00:00+00:00",
        "asset": "BTC",
        "action": action,
        "explanation": "x",
        "diagnostics": diagnostics,
        "created_at": "2026-07-10T00:00:00+00:00",
    }


def test_classify_throughput_covers_every_cause():
    from autonomy.crypto_paper_twin import (
        classify_throughput, is_actionable_throughput, is_expected_abstention,
    )

    common = dict(forecasted_markets=0)
    assert classify_throughput(
        action="ABSTAIN", listed_markets=0, two_sided_markets=0,
        candidates=0, eligible_candidates=0, **common,
    ) == "no_listed_market"
    assert classify_throughput(
        action="ABSTAIN", listed_markets=1, two_sided_markets=0,
        candidates=0, eligible_candidates=0, **common,
    ) == "no_two_sided_book"
    assert classify_throughput(
        action="ABSTAIN", listed_markets=1, two_sided_markets=1,
        candidates=0, eligible_candidates=0, **common,
    ) == "forecast_incomplete"
    assert classify_throughput(
        action="ABSTAIN", listed_markets=2, two_sided_markets=2,
        candidates=2, eligible_candidates=0, forecasted_markets=2,
    ) == "policy_rejected"
    assert classify_throughput(
        action="BUY_YES", listed_markets=1, two_sided_markets=1,
        candidates=1, eligible_candidates=1, forecasted_markets=1,
    ) == "traded"
    # Only genuine pipeline gaps are actionable; selectivity and absence are not.
    assert is_actionable_throughput("no_two_sided_book")
    assert is_actionable_throughput("forecast_incomplete")
    assert not is_actionable_throughput("policy_rejected")
    assert not is_actionable_throughput("no_listed_market")
    assert is_expected_abstention("no_listed_market")
    assert not is_expected_abstention("policy_rejected")


def test_throughput_class_counts_uses_recorded_class(tmp_path):
    ledger = PaperTwinLedger(tmp_path / "paper.db")
    cycle = ledger.start_cycle(datetime(2026, 7, 10, tzinfo=timezone.utc))
    ledger.record_observation(_obs_row("exploratory", "ABSTAIN", {
        "throughput_class": "no_listed_market", "listed_nearest_expiry_markets": 0,
    }, cycle_id=cycle))
    ledger.record_observation(_obs_row("exploratory", "ABSTAIN", {
        "throughput_class": "no_two_sided_book", "listed_nearest_expiry_markets": 1,
    }, cycle_id=cycle))
    ledger.record_observation(_obs_row("exploratory", "BUY_YES", {
        "throughput_class": "traded",
    }, cycle_id=cycle))
    counts = ledger.throughput_class_counts()
    ledger.close()
    assert counts == {"no_listed_market": 1, "no_two_sided_book": 1, "traded": 1}


def test_throughput_class_counts_derives_for_legacy_rows(tmp_path):
    """Rows written before the class field derive it from preserved counts."""
    ledger = PaperTwinLedger(tmp_path / "paper.db")
    cycle = ledger.start_cycle(datetime(2026, 7, 10, tzinfo=timezone.utc))
    # Legacy abstain with no throughput_class: listed but one-sided book.
    ledger.record_observation(_obs_row("exploratory", "ABSTAIN", {
        "listed_nearest_expiry_markets": 1,
        "two_sided_markets": 0,
        "nearest_expiry_markets": 0,
        "candidate_markets": 0,
        "eligible_candidates": 0,
    }, cycle_id=cycle))
    # Legacy abstain, market never listed.
    ledger.record_observation(_obs_row("exploratory", "ABSTAIN", {
        "listed_nearest_expiry_markets": 0,
        "candidate_markets": 0,
    }, cycle_id=cycle))
    counts = ledger.throughput_class_counts()
    ledger.close()
    assert counts == {"no_listed_market": 1, "no_two_sided_book": 1}
