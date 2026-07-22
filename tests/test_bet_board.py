"""Wave-15: the bet board (every priced market, ranked, league x bet type)."""
from __future__ import annotations

import pytest

from autonomy.bet_board import assemble_bet_board
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.picks import FUSED_SOURCE


def _emit(ledger, ticker, p, market_p=None, when=None, source=FUSED_SOURCE):
    from datetime import datetime, timedelta, timezone

    created = when or (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    features = {"challenger_only": False, "is_fused_output": True}
    if market_p is not None:
        features["market_implied_yes"] = market_p
    ledger.record_signal(Signal(
        source=source, market_ticker=ticker, probability_yes=p,
        uncertainty=0.1, rationale="r", created_at=created, features=features))


def test_board_groups_computes_edge_and_keeps_legacy_rows_unclassified(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _emit(ledger, "KXMLBGAME-26JUL18NYYBOS-NYY", 0.71, market_p=0.55)   # +16 edge
    _emit(ledger, "KXWNBATOTAL-26JUL18LVANYL-T164", 0.58, market_p=0.55)  # +3
    _emit(ledger, "KXWNBA1HTOTAL-26JUL18LVANYL-T80", 0.44, market_p=0.50)  # -6
    board = assemble_bet_board(conn=ledger._conn)
    assert board["rows"] == 3
    assert "mlb" in board["groups"] and "winner" in board["groups"]["mlb"]
    mlb = board["groups"]["mlb"]["winner"][0]
    assert abs(mlb["edge"] - 0.16) < 1e-9
    assert mlb["pick"] is None and mlb["tier"] is None
    assert mlb["tier_policy_version"] == "unattributed"
    assert mlb["tier_reason"] == "legacy_missing_or_invalid_tier_snapshot"
    assert board["generated_at"] == max(row["as_of"] for row in board["top"])
    # Segment bet types carry their segment label.
    assert "h1_total" in board["groups"]["wnba"]
    assert board["groups"]["wnba"]["h1_total"][0]["pick"] is None


def test_board_uses_latest_emission_and_drops_settled(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    ticker = "KXMLBGAME-26JUL18NYYBOS-NYY"
    from datetime import datetime, timedelta, timezone

    early = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    late = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _emit(ledger, ticker, 0.40, market_p=0.5, when=early)
    _emit(ledger, ticker, 0.66, market_p=0.5, when=late)
    settled = "KXMLBGAME-26JUL18AAABBB-AAA"
    _emit(ledger, settled, 0.80, market_p=0.5)
    ledger.record_settlement(settled, True)
    board = assemble_bet_board(conn=ledger._conn)
    assert board["rows"] == 1
    assert board["top"][0]["probability"] == 0.66


def test_board_no_pick_band_and_missing_market_prob(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _emit(ledger, "KXMLBGAME-26JUL18CCCDDD-CCC", 0.505)      # coin flip, no market
    board = assemble_bet_board(conn=ledger._conn)
    row = board["top"][0]
    assert row["pick"] is None and row["tier"] is None
    assert row["edge"] is None and row["market_probability"] is None


def test_board_missing_db_is_an_error_payload_not_a_crash(tmp_path):
    board = assemble_bet_board(
        db_path=str(tmp_path / "absent" / "ledger.db"),
        artifact_path=tmp_path / "absent" / "bet_board.json")
    assert board["rows"] == 0
    assert "groups" in board


class _Mkt:
    def __init__(self, ticker, title, *, yes_ask=50, no_ask=50):
        from datetime import datetime, timedelta, timezone

        self.ticker, self.title = ticker, title
        self.yes_ask, self.no_ask = yes_ask, no_ask
        self.yes_bid = yes_ask - 1 if isinstance(yes_ask, int) else None
        self.no_bid = no_ask - 1 if isinstance(no_ask, int) else None
        self.liquidity = 500
        self.fetched_at = datetime.now(timezone.utc).isoformat()
        self.close_time = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat()
        self.status = "active"


class _Fc:
    def __init__(self, p, market_p, unc=0.1):
        self.probability_yes = p
        self.market_implied_yes = market_p
        self.uncertainty = unc


def test_cycle_artifact_writes_and_serves_first(tmp_path):
    from autonomy.bet_board import write_board_artifact

    path = tmp_path / "bet_board.json"
    written = write_board_artifact(
        [
            (_Mkt("KXMLBGAME-26JUL18NYYBOS-NYY", "Yankees vs Red Sox Winner?"),
             _Fc(0.71, 0.55)),
            (_Mkt("KXWNBA1HTOTAL-26JUL18LVANYL-T80", "Aces vs Liberty 1H Total?"),
             _Fc(0.44, 0.50)),
        ],
        path=path,
    )
    assert written["rows"] == 2
    assert written["top"][0]["title"] == "Yankees vs Red Sox Winner?"
    assert written["top"][0]["edge"] == 0.16
    assert written["top"][0]["event_date"] == "2026-07-18"
    assert written["top"][0]["event_id"] == "26JUL18NYYBOS"
    assert written["source"] == "cycle_artifact"
    assert "NFL" in written["sports_leagues"]
    assert written["sports_league_roster_kind"] == (
        "year_round_navigation_not_current_listings"
    )

    served = assemble_bet_board(
        db_path=str(tmp_path / "no.db"), artifact_path=path)
    assert served["rows"] == 2 and served["source"] == "cycle_artifact"
    assert served["age_seconds"] >= 0
    assert "h1_total" in served["groups"]["wnba"]


def test_cycle_board_pick_is_quote_value_side_not_forecast_lean(tmp_path):
    from autonomy.bet_board import write_board_artifact

    # The model leans YES, but the quoted YES price is expensive while NO is
    # cheap enough to clear A after the modeled taker fee.
    written = write_board_artifact(
        [(
            _Mkt(
                "KXMLBGAME-26JUL18NYYBOS-NYY",
                "Yankees vs Red Sox Winner?",
                yes_ask=70,
                no_ask=30,
            ),
            _Fc(0.60, 0.70),
        )],
        path=tmp_path / "bet_board.json",
    )

    row = written["top"][0]
    assert row["forecast_lean"] == "yes"
    assert row["pick"] == row["value_side"] == "no"
    assert row["tier"] == "A"
    # The server-derived display field is intentionally outside the signed
    # assessment namespace; adding it must not invalidate a genuine snapshot.
    assert row["tier_display_bucket"] == "A"
    assert row["entry_price_cents"] == 30
    assert row["modeled_fee_cents"] == 2
    assert row["after_fee_edge"] == 0.08


def test_default_board_path_is_pytest_isolated(tmp_path):
    from autonomy import bet_board

    assert bet_board.BOARD_PATH == (
        tmp_path / "runtime" / "autonomy" / "bet_board.json"
    )


def test_cycle_artifact_keeps_prop_player_name(tmp_path):
    from autonomy.bet_board import write_board_artifact

    written = write_board_artifact(
        [(_Mkt(
            "KXMLBHIT-26JUL211910BALBOS-BALPALONSO25-1",
            "Pete Alonso: 1+ hits?",
        ), _Fc(0.64, 0.51))],
        path=tmp_path / "bet_board.json",
    )
    row = written["top"][0]
    assert row["subject"] == "Pete Alonso"
    assert row["subject_team"] == "BAL"
    assert row["market"] == "Pete Alonso · 1+ hits"
    assert row["label"].endswith("Pete Alonso · 1+ hits")


def test_board_drops_weather_and_commodity_targets(tmp_path):
    from autonomy.bet_board import write_board_artifact

    written = write_board_artifact(
        [
            (_Mkt("KXMLBGAME-26JUL21NYYBOS-NYY", "MLB"), _Fc(0.65, 0.50)),
            (_Mkt("KXWTI-26JUL21-T80", "Oil"), _Fc(0.70, 0.50)),
            (_Mkt("KXRAINNYC-26JUL21", "Rain"), _Fc(0.80, 0.50)),
        ],
        path=tmp_path / "bet_board.json",
    )

    assert written["rows"] == 1
    assert written["top"][0]["ticker"].startswith("KXMLB")


def test_stale_artifact_falls_back_to_ledger(tmp_path):
    from autonomy.bet_board import write_board_artifact

    path = tmp_path / "bet_board.json"
    write_board_artifact(
        [(_Mkt("KXMLBGAME-26JUL18NYYBOS-NYY", "t"), _Fc(0.7, 0.5))],
        path=path, now_iso="2026-07-01T00:00:00+00:00")   # ancient
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _emit(ledger, "KXMLBGAME-26JUL18CCCDDD-CCC", 0.61, market_p=0.5)
    board = assemble_bet_board(
        db_path=str(tmp_path / "ledger.db"), artifact_path=path)
    assert board["source"] == "ledger_fallback"
    assert board["rows"] == 1
    assert board["generated_at"] == board["top"][0]["as_of"]


def test_public_artifact_reader_labels_fresh_stale_and_missing(tmp_path):
    import json
    from datetime import datetime, timezone

    from autonomy.bet_board import read_board_artifact

    path = tmp_path / "bet_board.json"
    path.write_text(json.dumps({
        "generated_at": "2026-07-22T12:00:00+00:00",
        "rows": 0,
        "groups": {},
        "top": [],
    }), encoding="utf-8")

    fresh = read_board_artifact(
        path, now=datetime(2026, 7, 22, 12, 1, tzinfo=timezone.utc)
    )
    assert fresh["artifact_status"] == "FRESH"
    assert fresh["age_seconds"] == 60.0
    assert fresh["stale"] is False

    stale = read_board_artifact(
        path, now=datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc)
    )
    assert stale["artifact_status"] == "STALE"
    assert stale["age_seconds"] == 10800.0
    assert stale["stale"] is True

    missing = read_board_artifact(tmp_path / "missing.json")
    assert missing["artifact_status"] == "MISSING"
    assert missing["generated_at"] is None
    assert missing["age_seconds"] is None
    assert missing["stale"] is True
    assert "NFL" in missing["sports_leagues"]


def test_public_artifact_reader_rejects_future_time_and_forged_a_tier(tmp_path):
    import json
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone

    from autonomy.bet_board import read_board_artifact
    from autonomy.tier_policy import assess_market_tier

    path = tmp_path / "bet_board.json"
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    market = _Mkt("KXMLBGAME-26JUL22AAABBB-AAA", "A vs B")
    market.fetched_at = (now - timedelta(seconds=30)).isoformat()
    market.close_time = (now + timedelta(hours=2)).isoformat()
    assessment = assess_market_tier(market, _Fc(0.56, 0.50), now=now)
    forged = replace(
        assessment,
        gross_executable_edge=-0.48,
        after_fee_edge=-0.50,
        uncertainty=0.50,
        reason="meets_a_edge_and_uncertainty",
    ).feature_fields()
    row = {
        "ticker": market.ticker,
        "league": "mlb",
        "bet_type": "winner",
        **forged,
    }
    path.write_text(json.dumps({
        "generated_at": now.isoformat(),
        "rows": 1,
        "groups": {"mlb": {"winner": [row]}},
        "top": [row],
    }), encoding="utf-8")

    loaded = read_board_artifact(path, now=now)

    assert loaded["artifact_status"] == "FRESH"
    assert loaded["groups"]["mlb"]["winner"][0]["tier_display_bucket"] == "UNATTRIBUTED"
    assert loaded["tier_distribution"]["counts"]["A"] == 0
    assert loaded["tier_distribution"]["counts"]["UNATTRIBUTED"] == 1

    future_path = tmp_path / "future.json"
    future_path.write_text(json.dumps({
        "generated_at": (now + timedelta(minutes=6)).isoformat(),
        "rows": 0,
        "groups": {},
        "top": [],
    }), encoding="utf-8")

    future = read_board_artifact(future_path, now=now)

    assert future["artifact_status"] == "INVALID"
    assert future["stale"] is True


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("ticker", "KXMLBGAME-26JUL22CCCDDD-CCC"),
        ("probability", 0.61),
        ("uncertainty", 0.20),
        ("no_ask", 31),
        ("pick", "yes"),
        ("value_side", "yes"),
        ("entry_price_cents", 31),
        ("modeled_fee_cents", 99),
        ("gross_executable_edge", 0.09),
        ("after_fee_edge", 0.07),
        ("edge", 0.99),
    ],
)
def test_public_reader_binds_snapshot_to_every_visible_value(
    tmp_path,
    field,
    forged_value,
):
    import json
    from datetime import datetime, timedelta

    from autonomy.bet_board import read_board_artifact, write_board_artifact

    path = tmp_path / "bet_board.json"
    write_board_artifact(
        [(
            _Mkt(
                "KXMLBGAME-26JUL22AAABBB-AAA",
                "A vs B",
                yes_ask=70,
                no_ask=30,
            ),
            _Fc(0.60, 0.70),
        )],
        path=path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = payload["groups"]["mlb"]["winner"][0]
    row[field] = forged_value
    path.write_text(json.dumps(payload), encoding="utf-8")
    board_time = datetime.fromisoformat(payload["generated_at"])

    loaded = read_board_artifact(path, now=board_time + timedelta(seconds=1))

    visible = loaded["groups"]["mlb"]["winner"][0]
    assert loaded["artifact_status"] == "FRESH"
    assert visible["tier_display_bucket"] == "UNATTRIBUTED"
    assert visible["tier_display_reason"] == "snapshot_not_bound_to_visible_row"
    assert loaded["tier_distribution"]["counts"]["A"] == 0
    # Top is derived from the complete grouped row, not the separately stored
    # (and now divergent) top copy.
    assert loaded["top"][0] == visible


@pytest.mark.parametrize(
    (
        "assessment_offset",
        "generation_offset",
        "close_offset",
        "read_offset",
        "reason",
    ),
    [
        (60, 0, 7200, 0, "assessment_after_board_generation"),
        (1, 2, 7200, 0, "assessment_after_read_time"),
        (-600, 0, -60, 0, "market_expired_for_board"),
        (-600, 0, 300, 360, "market_expired_for_board"),
    ],
)
def test_public_reader_unattributes_future_or_expired_assessments(
    tmp_path,
    assessment_offset,
    generation_offset,
    close_offset,
    read_offset,
    reason,
):
    from datetime import datetime, timedelta, timezone

    from autonomy.bet_board import read_board_artifact, write_board_artifact
    from autonomy.tier_policy import assess_market_tier

    board_time = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    assessed_at = board_time + timedelta(seconds=assessment_offset)
    market = _Mkt("KXMLBGAME-26JUL22AAABBB-AAA", "A vs B")
    market.fetched_at = (assessed_at - timedelta(seconds=30)).isoformat()
    market.close_time = (board_time + timedelta(seconds=close_offset)).isoformat()
    forecast = _Fc(0.70, 0.50)
    assessment = assess_market_tier(market, forecast, now=assessed_at)
    assert assessment.tier == "A"
    path = tmp_path / "bet_board.json"
    write_board_artifact(
        [(market, forecast)],
        path=path,
        now_iso=(board_time + timedelta(seconds=generation_offset)).isoformat(),
        tier_assignments={market.ticker: assessment},
    )

    loaded = read_board_artifact(
        path,
        now=board_time + timedelta(seconds=read_offset),
    )

    row = loaded["groups"]["mlb"]["winner"][0]
    assert loaded["artifact_status"] == "FRESH"
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert row["tier_display_reason"] == reason


@pytest.mark.parametrize(
    (
        "assessment_offset",
        "quote_offset",
        "generation_offset",
        "read_offset",
        "reason",
    ),
    [
        (-360, -390, 0, 1, "assessment_too_old_for_board_generation"),
        (-120, -960, 0, 1, "quote_stale_at_board_generation"),
        (0, -30, 1, 901, "quote_stale_at_read_time"),
    ],
)
def test_public_reader_does_not_refresh_old_assessments_or_quotes(
    tmp_path,
    assessment_offset,
    quote_offset,
    generation_offset,
    read_offset,
    reason,
):
    from datetime import datetime, timedelta, timezone

    from autonomy.bet_board import read_board_artifact, write_board_artifact
    from autonomy.tier_policy import assess_market_tier

    board_time = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    assessed_at = board_time + timedelta(seconds=assessment_offset)
    market = _Mkt("KXMLBGAME-26JUL22AAABBB-AAA", "A vs B")
    market.fetched_at = (board_time + timedelta(seconds=quote_offset)).isoformat()
    market.close_time = (board_time + timedelta(hours=2)).isoformat()
    forecast = _Fc(0.70, 0.50)
    assessment = assess_market_tier(market, forecast, now=assessed_at)
    assert assessment.tier == "A"
    path = tmp_path / "bet_board.json"
    write_board_artifact(
        [(market, forecast)],
        path=path,
        now_iso=(board_time + timedelta(seconds=generation_offset)).isoformat(),
        tier_assignments={market.ticker: assessment},
    )

    loaded = read_board_artifact(
        path,
        now=board_time + timedelta(seconds=read_offset),
    )

    row = loaded["groups"]["mlb"]["winner"][0]
    assert loaded["artifact_status"] == "FRESH"
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert row["tier_display_reason"] == reason
    assert loaded["tier_distribution"]["counts"]["A"] == 0


def test_public_reader_re_excludes_data_only_targets_before_ranking(tmp_path):
    import json
    from datetime import datetime, timedelta, timezone

    from autonomy.bet_board import read_board_artifact

    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    forged_weather_row = {
        "ticker": "KXHIGHNY-26JUL22-T90",
        "league": "weather",
        "bet_type": "market",
        "tier": "A",
        "probability": 0.99,
    }
    path = tmp_path / "bet_board.json"
    path.write_text(
        json.dumps({
            "generated_at": now.isoformat(),
            "rows": 1,
            "groups": {"weather": {"market": [forged_weather_row]}},
            "top": [forged_weather_row],
        }),
        encoding="utf-8",
    )

    loaded = read_board_artifact(path, now=now + timedelta(seconds=1))

    assert loaded["artifact_status"] == "FRESH"
    assert loaded["excluded_data_only_rows"] == 1
    assert loaded["rows"] == 0
    assert loaded["groups"] == {}
    assert loaded["top"] == []
    assert loaded["tier_distribution"]["counts"] == {
        "A": 0,
        "B": 0,
        "C": 0,
        "WATCH": 0,
        "UNATTRIBUTED": 0,
    }


@pytest.mark.parametrize(
    "equity_row",
    [
        {
            "ticker": "KXBAA-28JANDELIV-700",
            "category": "Companies",
        },
        {
            "ticker": "OPAQUE-COMPANY-KPI",
            "category": "Financials",
            "series_tags": ["KPIs"],
        },
    ],
)
def test_public_reader_re_excludes_copied_company_targets_before_ranking(
    tmp_path,
    equity_row,
):
    import json
    from datetime import datetime, timedelta, timezone

    from autonomy.bet_board import read_board_artifact

    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    equity_row = {
        **equity_row,
        "league": "companies",
        "bet_type": "market",
        "tier": "A",
        "probability": 0.99,
    }
    sports_row = {
        "ticker": "KXMLBGAME-26JUL22AAABBB-AAA",
        "category": "Sports",
        "league": "mlb",
        "bet_type": "winner",
        "tier": "B",
        "probability": 0.61,
    }
    path = tmp_path / "bet_board.json"
    path.write_text(
        json.dumps({
            "generated_at": now.isoformat(),
            "rows": 2,
            "groups": {
                "companies": {"market": [equity_row]},
                "mlb": {"winner": [sports_row]},
            },
            "top": [equity_row, sports_row],
        }),
        encoding="utf-8",
    )

    loaded = read_board_artifact(path, now=now + timedelta(seconds=1))

    assert loaded["artifact_status"] == "FRESH"
    assert loaded["excluded_equity_index_rows"] == 1
    assert loaded["rows"] == 1
    assert set(loaded["groups"]) == {"mlb"}
    assert [row["ticker"] for row in loaded["top"]] == [sports_row["ticker"]]


def test_public_reader_reapplies_a_scarcity_caps_across_forged_cycle(tmp_path):
    from datetime import datetime, timedelta, timezone

    from autonomy.bet_board import read_board_artifact, write_board_artifact
    from autonomy.tier_policy import assess_market_tier

    board_time = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    tickers = [
        "KXMLBGAME-26JUL22AAABBB-AAA",
        "KXMLBGAME-26JUL22AAABBB-BBB",
        "KXMLBGAME-26JUL22CCCDDD-CCC",
        "KXMLBGAME-26JUL22EEEFFF-EEE",
        "KXMLBGAME-26JUL22GGGHHH-GGG",
        "KXMLBGAME-26JUL22IIIJJJ-III",
        "KXMLBGAME-26JUL22KKKLLL-KKK",
        "KXMLBGAME-26JUL22MMMNNN-MMM",
    ]
    forecast = _Fc(0.70, 0.50)
    scored = []
    assignments = {}
    for ticker in tickers:
        market = _Mkt(ticker, ticker)
        market.fetched_at = (board_time - timedelta(seconds=30)).isoformat()
        market.close_time = (board_time + timedelta(hours=2)).isoformat()
        scored.append((market, forecast))
        assessment = assess_market_tier(market, forecast, now=board_time)
        assert assessment.tier == "A"
        assignments[ticker] = assessment
    path = tmp_path / "bet_board.json"
    # Supplying independently assessed rows simulates an artifact that omitted
    # assign_cycle_tiers' cross-row scarcity pass while retaining valid hashes.
    write_board_artifact(
        scored,
        path=path,
        now_iso=(board_time + timedelta(seconds=1)).isoformat(),
        tier_assignments=assignments,
    )

    loaded = read_board_artifact(
        path,
        now=board_time + timedelta(seconds=2),
    )

    rows = loaded["groups"]["mlb"]["winner"]
    displayed_a = [row for row in rows if row["tier_display_bucket"] == "A"]
    displayed_b = [row for row in rows if row["tier_display_bucket"] == "B"]
    assert len(displayed_a) == 5
    assert len(displayed_b) == 3
    assert len({row["tier_event_key"] for row in displayed_a}) == len(displayed_a)
    assert all(
        row["tier_display_reason"] == "a_scarcity_cap_enforced_at_read"
        and row["tier_display_scarcity_demoted"] is True
        for row in displayed_b
    )
    assert loaded["tier_distribution"]["counts"]["A"] == 5
    assert loaded["tier_distribution"]["counts"]["B"] == 3


def test_public_reader_derives_top_exactly_from_ranked_group_rows(tmp_path):
    import json
    from datetime import datetime, timedelta

    from autonomy.bet_board import read_board_artifact, write_board_artifact

    path = tmp_path / "bet_board.json"
    write_board_artifact(
        [
            (_Mkt("KXMLBGAME-26JUL22AAABBB-AAA", "A vs B"), _Fc(0.70, 0.50)),
            (_Mkt("KXMLBGAME-26JUL22CCCDDD-CCC", "C vs D"), _Fc(0.60, 0.50)),
        ],
        path=path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["top"] = [{
        **payload["top"][0],
        "ticker": "FORGED-TOP-ONLY",
        "probability": 0.9999,
        "rank": 1,
    }]
    path.write_text(json.dumps(payload), encoding="utf-8")
    board_time = datetime.fromisoformat(payload["generated_at"])

    loaded = read_board_artifact(path, now=board_time + timedelta(seconds=1))

    grouped = [
        row
        for markets in loaded["groups"].values()
        for rows in markets.values()
        for row in rows
    ]
    ranked = sorted(grouped, key=lambda row: row["rank"])
    assert loaded["top"] == ranked[:25]
    assert all(row["ticker"] != "FORGED-TOP-ONLY" for row in loaded["top"])


def test_dashboard_board_routes_never_fall_back_when_artifact_missing(
    tmp_path, monkeypatch,
):
    from fastapi.testclient import TestClient

    from autonomy import bet_board, dashboard

    monkeypatch.setattr(dashboard, "RUNTIME_DIR", tmp_path)

    def _forbidden(*args, **kwargs):
        raise AssertionError("request handler attempted the ledger fallback")

    monkeypatch.setattr(bet_board, "assemble_bet_board", _forbidden)
    client = TestClient(dashboard.build_app())

    board_response = client.get("/api/bet_board")
    assert board_response.status_code == 503
    assert board_response.json()["artifact_status"] == "MISSING"

    tier_response = client.get("/api/tier-performance")
    assert tier_response.status_code == 503
    assert tier_response.json()["status"] == "UNAVAILABLE"
    assert tier_response.json()["board_artifact_status"] == "MISSING"


def test_dashboard_serves_stale_board_with_explicit_warning(tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from autonomy import dashboard

    (tmp_path / "bet_board.json").write_text(json.dumps({
        "generated_at": "2026-07-01T00:00:00+00:00",
        "rows": 0,
        "groups": {},
        "top": [],
    }), encoding="utf-8")
    monkeypatch.setattr(dashboard, "RUNTIME_DIR", tmp_path)

    response = TestClient(dashboard.build_app()).get("/api/bet_board")
    assert response.status_code == 200
    assert response.json()["artifact_status"] == "STALE"
    assert response.json()["stale"] is True
