from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from autonomy.bet_board import (
    read_board_artifact,
    read_current_board_artifact,
    write_board_artifact,
)
from autonomy.ontology import Forecast, MarketView, Vertical
from autonomy.sports_board_refresh import publish_fresh_sports_display_board


NOW = datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc)


def _market(
    ticker: str,
    *,
    title: str,
    occurrence: datetime | None = None,
    fetched_at: datetime = NOW,
    yes_ask: int = 50,
) -> MarketView:
    event_start = occurrence or NOW + timedelta(hours=5)
    return MarketView(
        ticker=ticker,
        title=title,
        vertical=Vertical.SPORTS,
        status="active",
        close_time=(event_start + timedelta(hours=4)).isoformat(),
        yes_bid=max(1, yes_ask - 2),
        yes_ask=yes_ask,
        no_bid=max(1, 98 - yes_ask),
        no_ask=100 - yes_ask,
        volume=100,
        liquidity=500,
        raw={
            "occurrence_datetime": event_start.isoformat(),
            "category": "Sports",
        },
        fetched_at=fetched_at.isoformat(),
    )


def _forecast(ticker: str, probability: float, uncertainty: float) -> Forecast:
    return Forecast(
        market_ticker=ticker,
        probability_yes=probability,
        uncertainty=uncertainty,
        sources_used={"market_prior": 0.2, "licensed_consensus": 0.8},
        market_implied_yes=0.5,
        edge_yes=probability - 0.5,
        rationale="market_prior:0.50+/-0.10; licensed_consensus:0.57+/-0.09",
    )


def _base(path: Path, pairs: list[tuple[MarketView, Forecast]]) -> None:
    write_board_artifact(pairs, path=path, now_iso=NOW.isoformat())


def _all_rows(board: dict) -> list[dict]:
    return [
        row
        for markets in (board.get("groups") or {}).values()
        for rows in markets.values()
        for row in rows
    ]


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "GET",
        "https://public.example/markets?api_key=must-not-persist",
    )
    response = httpx.Response(
        status_code,
        request=request,
        text="upstream body must not persist",
    )
    return httpx.HTTPStatusError(
        "public request failed with private diagnostic text",
        request=request,
        response=response,
    )


def test_fresh_governed_monitor_forecasts_publish_a_b_c_and_watch(tmp_path: Path) -> None:
    markets = [
        _market(
            "KXMLBGAME-26JUL221500NYYBOS-NYY",
            title="New York vs Boston Winner?",
        ),
        _market(
            "KXMLBGAME-26JUL221600CHCCIN-CHC",
            title="Chicago vs Cincinnati Winner?",
        ),
        _market(
            "KXWNBAGAME-26JUL221700NYLSEA-NYL",
            title="New York vs Seattle Winner?",
        ),
        _market(
            "KXWNBAGAME-26JUL221800LVAATL-LVA",
            title="Las Vegas vs Atlanta Winner?",
        ),
    ]
    forecasts = {
        markets[0].ticker: _forecast(markets[0].ticker, 0.56, 0.10),
        markets[1].ticker: _forecast(markets[1].ticker, 0.54, 0.15),
        markets[2].ticker: _forecast(markets[2].ticker, 0.53, 0.20),
        markets[3].ticker: _forecast(markets[3].ticker, 0.52, 0.10),
    }
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, list(zip(markets, forecasts.values())))

    publish_fresh_sports_display_board(
        markets,
        {ticker: (forecast, NOW.isoformat()) for ticker, forecast in forecasts.items()},
        base_path=base_path,
        output_path=display_path,
        now=NOW,
    )
    board = read_board_artifact(display_path, now=NOW + timedelta(seconds=1))

    assert board["artifact_status"] == "FRESH"
    assert board["tier_distribution"]["counts"] == {
        "A": 1,
        "B": 1,
        "C": 1,
        "WATCH": 1,
        "UNATTRIBUTED": 0,
    }
    assert all(row["display_only"] is True for row in _all_rows(board))
    assert all(row["execution_authority"] is False for row in _all_rows(board))


def test_fresh_quote_cannot_resurrect_a_forecast_older_than_15_minutes(
    tmp_path: Path,
) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    forecast = _forecast(market.ticker, 0.60, 0.08)
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, [(market, forecast)])

    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, (NOW - timedelta(seconds=901)).isoformat())},
        base_path=base_path,
        output_path=display_path,
        now=NOW,
    )
    board = read_board_artifact(display_path, now=NOW + timedelta(seconds=1))
    row = _all_rows(board)[0]

    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert row["model_status"] == "STALE"
    assert board["tier_distribution"]["counts"]["A"] == 0


def test_quote_and_forecast_expire_at_public_read_boundary(tmp_path: Path) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
        occurrence=NOW + timedelta(hours=5),
    )
    forecast = _forecast(market.ticker, 0.60, 0.08)
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, [(market, forecast)])
    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        base_path=base_path,
        output_path=display_path,
        now=NOW,
    )

    board = read_board_artifact(display_path, now=NOW + timedelta(seconds=901))
    row = _all_rows(board)[0]
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert row["tier_display_reason"] in {
        "display_model_stale_at_read_time",
        "quote_stale_at_read_time",
    }


def test_in_play_or_unknown_start_forecast_is_never_reissued(tmp_path: Path) -> None:
    in_play = _market(
        "KXMLBGAME-26JUL221000NYYBOS-NYY",
        title="New York vs Boston Winner?",
        occurrence=NOW - timedelta(minutes=1),
    )
    missing_start = _market(
        "KXWNBAGAME-26JUL221700NYLSEA-NYL",
        title="New York vs Seattle Winner?",
    )
    missing_start = MarketView(
        **{**missing_start.__dict__, "raw": {"category": "Sports"}}
    )
    forecasts = {
        in_play.ticker: _forecast(in_play.ticker, 0.70, 0.05),
        missing_start.ticker: _forecast(missing_start.ticker, 0.70, 0.05),
    }
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, list(zip([in_play, missing_start], forecasts.values())))

    publish_fresh_sports_display_board(
        [in_play, missing_start],
        {ticker: (forecast, NOW.isoformat()) for ticker, forecast in forecasts.items()},
        base_path=base_path,
        output_path=display_path,
        now=NOW,
    )
    rows = {row["ticker"]: row for row in _all_rows(
        read_board_artifact(display_path, now=NOW + timedelta(seconds=1))
    )}
    assert rows[in_play.ticker]["model_status"] == "IN_PLAY"
    assert rows[missing_start.ticker]["model_status"] == "UNKNOWN_EVENT_START"
    assert all(row["tier_display_bucket"] == "UNATTRIBUTED" for row in rows.values())


def test_current_day_only_and_prop_label_keeps_exact_player(tmp_path: Path) -> None:
    player = _market(
        "KXMLBHIT-26JUL221700NYYBOS-NYYAJUDGE1-2",
        title="Aaron Judge: 2+ hits?",
    )
    tomorrow = _market(
        "KXMLBGAME-26JUL231500NYYBOS-NYY",
        title="New York vs Boston Winner?",
        occurrence=NOW + timedelta(days=1, hours=5),
    )
    forecasts = {
        player.ticker: _forecast(player.ticker, 0.56, 0.10),
        tomorrow.ticker: _forecast(tomorrow.ticker, 0.56, 0.10),
    }
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, list(zip([player, tomorrow], forecasts.values())))
    publish_fresh_sports_display_board(
        [player, tomorrow],
        {ticker: (forecast, NOW.isoformat()) for ticker, forecast in forecasts.items()},
        base_path=base_path,
        output_path=display_path,
        now=NOW,
    )
    board = read_board_artifact(display_path, now=NOW + timedelta(seconds=1))
    rows = _all_rows(board)
    refreshed = [row for row in rows if row.get("display_refresh_kind")]

    assert [row["ticker"] for row in refreshed] == [player.ticker]
    assert refreshed[0]["subject"] == "Aaron Judge"
    assert "Aaron Judge" in refreshed[0]["market"]


def test_tampered_forecast_provenance_is_unattributed(tmp_path: Path) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    forecast = _forecast(market.ticker, 0.60, 0.08)
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, [(market, forecast)])
    payload = publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        base_path=base_path,
        output_path=display_path,
        now=NOW,
    )
    payload["groups"]["mlb"]["winner"][0][
        "forecast_generated_at"
    ] = (NOW - timedelta(minutes=2)).isoformat()
    display_path.write_text(__import__("json").dumps(payload), encoding="utf-8")

    board = read_board_artifact(display_path, now=NOW + timedelta(seconds=1))
    row = _all_rows(board)[0]
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert row["tier_display_reason"] == "invalid_display_model_provenance_hash"


def test_public_selector_is_file_only_and_chooses_newest_valid_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    forecast = _forecast(market.ticker, 0.60, 0.08)
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    _base(base_path, [(market, forecast)])
    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        base_path=base_path,
        output_path=display_path,
        now=NOW + timedelta(seconds=5),
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("request path attempted network/ledger work")

    monkeypatch.setattr("sqlite3.connect", forbidden)
    try:
        import httpx

        monkeypatch.setattr(httpx, "get", forbidden)
    except ImportError:
        pass
    board = read_current_board_artifact(
        base_path,
        display_path=display_path,
        now=NOW + timedelta(seconds=6),
    )
    assert board["selected_artifact"] == "sports_display_overlay"
    assert board["no_request_time_ledger_or_network"] is True


def test_overlay_is_usable_standalone_when_cycle_artifact_is_missing(
    tmp_path: Path,
) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    forecast = _forecast(market.ticker, 0.60, 0.08)
    missing_base = tmp_path / "missing-bet-board.json"
    display_path = tmp_path / "bet_board_display.json"

    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        base_path=missing_base,
        output_path=display_path,
        now=NOW,
    )
    board = read_current_board_artifact(
        missing_base,
        display_path=display_path,
        now=NOW + timedelta(seconds=1),
    )

    assert missing_base.exists() is False
    assert board["selected_artifact"] == "sports_display_overlay"
    assert board["cycle_artifact_status"] == "MISSING"
    assert board["overlay_only"] is True
    assert [row["ticker"] for row in _all_rows(board)] == [market.ticker]
    assert board["tier_distribution"]["counts"]["A"] == 1


def test_newer_cycle_quote_wins_despite_later_display_completion_clock(
    tmp_path: Path,
) -> None:
    overlay_mlb = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
        fetched_at=NOW,
    )
    overlay_wnba = _market(
        "KXWNBAGAME-26JUL221700NYLSEA-NYL",
        title="New York vs Seattle Winner?",
        fetched_at=NOW,
    )
    newer_base_mlb = _market(
        "KXMLBGAME-26JUL221600CHCCIN-CHC",
        title="Chicago vs Cincinnati Winner?",
        fetched_at=NOW + timedelta(seconds=10),
    )
    overlay_forecasts = {
        overlay_mlb.ticker: _forecast(overlay_mlb.ticker, 0.60, 0.08),
        overlay_wnba.ticker: _forecast(overlay_wnba.ticker, 0.60, 0.08),
    }
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    write_board_artifact(
        [(newer_base_mlb, _forecast(newer_base_mlb.ticker, 0.60, 0.08))],
        path=base_path,
        now_iso=(NOW + timedelta(seconds=10)).isoformat(),
    )
    publish_fresh_sports_display_board(
        [overlay_mlb, overlay_wnba],
        {
            ticker: (forecast, NOW.isoformat())
            for ticker, forecast in overlay_forecasts.items()
        },
        base_path=base_path,
        output_path=display_path,
        now=NOW + timedelta(seconds=20),
    )

    board = read_current_board_artifact(
        base_path,
        display_path=display_path,
        now=NOW + timedelta(seconds=21),
    )
    tickers = {row["ticker"] for row in _all_rows(board)}

    assert board["selected_artifact"] == "sports_display_overlay"
    assert tickers == {newer_base_mlb.ticker, overlay_wnba.ticker}
    assert overlay_mlb.ticker not in tickers
    assert board["cycle_artifact_generated_at"] < board[
        "display_artifact_generated_at"
    ]


def test_series_missing_from_overlay_scan_cannot_carry_a_cycle_letter_grade(
    tmp_path: Path,
) -> None:
    observed_mlb = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    failed_wnba = _market(
        "KXWNBAGAME-26JUL221700NYLSEA-NYL",
        title="New York vs Seattle Winner?",
    )
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    failed_forecast = _forecast(failed_wnba.ticker, 0.60, 0.08)
    from autonomy.tier_policy import assign_cycle_tiers

    failed_pair = (failed_wnba, failed_forecast)
    write_board_artifact(
        [failed_pair],
        path=base_path,
        now_iso=NOW.isoformat(),
        tier_assignments=assign_cycle_tiers([failed_pair], now=NOW),
    )
    publish_fresh_sports_display_board(
        [observed_mlb],
        {
            observed_mlb.ticker: (
                _forecast(observed_mlb.ticker, 0.60, 0.08),
                NOW.isoformat(),
            )
        },
        base_path=base_path,
        output_path=display_path,
        now=NOW + timedelta(seconds=1),
    )

    board = read_current_board_artifact(
        base_path,
        display_path=display_path,
        now=NOW + timedelta(seconds=2),
    )
    rows = {row["ticker"]: row for row in _all_rows(board)}
    failed_row = rows[failed_wnba.ticker]

    assert failed_row["tier"] is None
    assert failed_row["tier_display_bucket"] == "UNATTRIBUTED"
    assert failed_row["tier_display_reason"] == "series_refresh_failed_or_unknown"
    assert failed_row["pick"] is None
    assert failed_row["value_side"] is None
    assert failed_row["after_fee_edge"] is None
    assert failed_row["last_issued_tier"] == "A"
    assert board["tier_distribution"]["counts"]["UNATTRIBUTED"] == 1


def test_forecast_dictionary_key_cannot_override_forecast_ticker_identity(
    tmp_path: Path,
) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    forecast_for_another_market = _forecast(
        "KXMLBGAME-26JUL221600CHCCIN-CHC",
        0.70,
        0.05,
    )
    display_path = tmp_path / "bet_board_display.json"

    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast_for_another_market, NOW.isoformat())},
        base_path=tmp_path / "missing-bet-board.json",
        output_path=display_path,
        now=NOW,
    )
    board = read_board_artifact(display_path, now=NOW + timedelta(seconds=1))
    row = _all_rows(board)[0]

    assert row["model_status"] == "IDENTITY_MISMATCH"
    assert row["tier"] is None
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert board["refreshed_tier_count"] == 0
    assert board["tier_distribution"]["counts"]["A"] == 0


@pytest.mark.parametrize(
    "invalid_limit",
    [0, -1, 900.000001, float("nan"), float("inf"), True],
)
def test_invalid_model_age_limit_is_rejected_before_base_or_public_reads(
    tmp_path: Path,
    invalid_limit: object,
) -> None:
    from autonomy.sports_board_refresh import refresh_sports_display_board

    fetch_calls: list[str] = []

    def forbidden_fetch(series: str) -> dict:
        fetch_calls.append(series)
        raise AssertionError("invalid config reached public fetch")

    with pytest.raises((TypeError, ValueError), match="model_max_age_seconds"):
        refresh_sports_display_board(
            base_path=tmp_path / "missing-bet-board.json",
            output_path=tmp_path / "bet_board_display.json",
            fetch_series=forbidden_fetch,
            series=["KXMLBGAME"],
            now=NOW,
            model_max_age_seconds=invalid_limit,
        )

    assert fetch_calls == []
    assert (tmp_path / "bet_board_display.json").exists() is False


def test_covered_empty_series_removes_old_roster_while_failed_series_is_context(
    tmp_path: Path,
) -> None:
    from autonomy.sports_board_refresh import refresh_sports_display_board
    from autonomy.tier_policy import assign_cycle_tiers

    old_mlb = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
        fetched_at=NOW - timedelta(seconds=5),
    )
    failed_wnba = _market(
        "KXWNBAGAME-26JUL221700NYLSEA-NYL",
        title="New York vs Seattle Winner?",
        fetched_at=NOW - timedelta(seconds=5),
    )
    pairs = [
        (old_mlb, _forecast(old_mlb.ticker, 0.60, 0.08)),
        (failed_wnba, _forecast(failed_wnba.ticker, 0.60, 0.08)),
    ]
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    write_board_artifact(
        pairs,
        path=base_path,
        now_iso=(NOW - timedelta(seconds=4)).isoformat(),
        tier_assignments=assign_cycle_tiers(
            pairs,
            now=NOW - timedelta(seconds=4),
        ),
    )

    def fetch(series: str) -> dict:
        if series == "KXMLBGAME":
            # A successful empty page is authoritative evidence that the old
            # current-day roster disappeared from this series.
            return {"markets": []}
        raise TimeoutError("WNBA series did not refresh")

    refreshed = refresh_sports_display_board(
        base_path=base_path,
        output_path=display_path,
        fetch_series=fetch,
        series=["KXMLBGAME", "KXWNBAGAME"],
        now=NOW,
    )
    board = read_current_board_artifact(
        base_path,
        display_path=display_path,
        now=NOW + timedelta(seconds=1),
    )
    rows = {row["ticker"]: row for row in _all_rows(board)}

    assert refreshed["covered_series"] == ["KXMLBGAME"]
    assert set(refreshed["failed_series"]) == {"KXWNBAGAME"}
    assert refreshed["series_refreshed_at"]["KXMLBGAME"]
    assert old_mlb.ticker not in rows
    assert set(rows) == {failed_wnba.ticker}
    assert rows[failed_wnba.ticker]["tier"] is None
    assert rows[failed_wnba.ticker]["tier_display_bucket"] == "UNATTRIBUTED"
    assert rows[failed_wnba.ticker]["last_issued_tier"] == "A"


@pytest.mark.parametrize(
    ("status_code", "reason"),
    [(429, "http_429"), (503, "http_5xx")],
)
def test_production_public_fetch_retries_transient_http_at_most_twice(
    status_code: int,
    reason: str,
) -> None:
    from autonomy import sports_board_refresh as refresh

    calls: list[tuple[str, float]] = []
    sleeps: list[float] = []

    def fetch(series: str, *, timeout_seconds: float) -> dict:
        calls.append((series, timeout_seconds))
        if len(calls) <= 2:
            raise _http_status_error(status_code)
        return {"markets": []}

    page = refresh._fetch_public_series_with_retry(
        "KXWNBA1QTOTAL",
        timeout_seconds=1.25,
        fetch_markets=fetch,
        sleep=sleeps.append,
    )

    assert page == {"markets": []}
    assert calls == [("KXWNBA1QTOTAL", 1.25)] * 3
    assert sleeps == list(refresh.PUBLIC_FETCH_RETRY_DELAYS_SECONDS)
    assert refresh._sanitized_public_failure(
        _http_status_error(status_code)
    ) == reason


@pytest.mark.parametrize("failure_kind", ["timeout", "transport"])
def test_production_public_fetch_retries_timeout_and_transport(
    failure_kind: str,
) -> None:
    from autonomy import sports_board_refresh as refresh

    calls: list[str] = []
    sleeps: list[float] = []

    def fetch(series: str, *, timeout_seconds: float) -> dict:
        del timeout_seconds
        calls.append(series)
        if len(calls) == 1:
            request = httpx.Request("GET", "https://public.example/markets")
            if failure_kind == "timeout":
                raise httpx.ReadTimeout("timed out", request=request)
            raise httpx.ConnectError("connection failed", request=request)
        return {"markets": []}

    assert refresh._fetch_public_series_with_retry(
        "KXWNBA2QTOTAL",
        timeout_seconds=1.0,
        fetch_markets=fetch,
        sleep=sleeps.append,
    ) == {"markets": []}
    assert calls == ["KXWNBA2QTOTAL", "KXWNBA2QTOTAL"]
    assert sleeps == [refresh.PUBLIC_FETCH_RETRY_DELAYS_SECONDS[0]]


@pytest.mark.parametrize("status_code", [400, 404])
def test_production_public_fetch_never_retries_nonretryable_4xx(
    status_code: int,
) -> None:
    from autonomy import sports_board_refresh as refresh

    calls: list[str] = []
    sleeps: list[float] = []

    def fetch(series: str, *, timeout_seconds: float) -> dict:
        del timeout_seconds
        calls.append(series)
        raise _http_status_error(status_code)

    with pytest.raises(refresh._PublicSeriesFetchFailure) as caught:
        refresh._fetch_public_series_with_retry(
            "KXWNBA4QTOTAL",
            timeout_seconds=1.0,
            fetch_markets=fetch,
            sleep=sleeps.append,
        )

    assert calls == ["KXWNBA4QTOTAL"]
    assert sleeps == []
    assert caught.value.reason == "http_4xx"
    assert str(caught.value) == "http_4xx"
    assert "api_key" not in str(caught.value)
    assert "upstream" not in str(caught.value)


def test_injected_series_fetcher_is_not_retried_implicitly() -> None:
    from autonomy import sports_board_refresh as refresh

    calls: list[str] = []

    def fetch(series: str) -> dict:
        calls.append(series)
        raise _http_status_error(503)

    pages, failures = refresh._fetch_series_bounded(
        ("KXWNBA3QSPREAD",),
        fetch_series=fetch,
        max_workers=1,
        overall_timeout_seconds=1.0,
    )

    assert pages == {}
    assert failures == {"KXWNBA3QSPREAD": "http_5xx"}
    assert calls == ["KXWNBA3QSPREAD"]


def test_retry_exhaustion_is_sanitized_while_empty_series_is_covered(
    tmp_path: Path,
) -> None:
    from autonomy import sports_board_refresh as refresh
    from autonomy.tier_policy import assign_cycle_tiers

    failed_wnba = _market(
        "KXWNBAGAME-26JUL221700NYLSEA-NYL",
        title="New York vs Seattle Winner?",
        fetched_at=NOW - timedelta(seconds=5),
    )
    pairs = [(failed_wnba, _forecast(failed_wnba.ticker, 0.60, 0.08))]
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    write_board_artifact(
        pairs,
        path=base_path,
        now_iso=(NOW - timedelta(seconds=4)).isoformat(),
        tier_assignments=assign_cycle_tiers(
            pairs,
            now=NOW - timedelta(seconds=4),
        ),
    )

    calls: list[str] = []
    sleeps: list[float] = []

    def low_level_fetch(series: str, *, timeout_seconds: float) -> dict:
        del timeout_seconds
        calls.append(series)
        if series == "KXMLBGAME":
            return {"markets": []}
        raise _http_status_error(503)

    def explicitly_wrapped_fetch(series: str) -> dict:
        return refresh._fetch_public_series_with_retry(
            series,
            timeout_seconds=1.0,
            fetch_markets=low_level_fetch,
            sleep=sleeps.append,
        )

    refreshed = refresh.refresh_sports_display_board(
        base_path=base_path,
        output_path=display_path,
        fetch_series=explicitly_wrapped_fetch,
        series=["KXMLBGAME", "KXWNBAGAME"],
        now=NOW,
        max_workers=1,
    )
    rows = {row["ticker"]: row for row in _all_rows(refreshed)}

    assert refreshed["covered_series"] == ["KXMLBGAME"]
    assert refreshed["failed_series"] == {"KXWNBAGAME": "http_5xx"}
    assert refreshed["coverage_complete"] is False
    assert calls.count("KXMLBGAME") == 1
    assert calls.count("KXWNBAGAME") == 3
    assert sleeps == list(refresh.PUBLIC_FETCH_RETRY_DELAYS_SECONDS)
    assert rows[failed_wnba.ticker]["tier"] is None
    assert rows[failed_wnba.ticker]["tier_display_bucket"] == "UNATTRIBUTED"
    assert rows[failed_wnba.ticker]["tier_reason"] == (
        "series_refresh_failed_or_unknown"
    )


def test_cycle_without_exact_row_forecast_time_cannot_be_reused(
    tmp_path: Path,
) -> None:
    from autonomy.sports_board_refresh import select_sports_model_source_path
    from autonomy.tier_policy import assign_cycle_tiers

    base_market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
        fetched_at=NOW,
    )
    base_forecast = _forecast(base_market.ticker, 0.60, 0.08)
    base_pair = (base_market, base_forecast)
    base_path = tmp_path / "bet_board.json"
    display_path = tmp_path / "bet_board_display.json"
    write_board_artifact(
        [base_pair],
        path=base_path,
        now_iso=NOW.isoformat(),
        tier_assignments=assign_cycle_tiers([base_pair], now=NOW),
    )

    stale_time = NOW - timedelta(minutes=16)
    stale_market = _market(
        "KXWNBAGAME-26JUL221700NYLSEA-NYL",
        title="New York vs Seattle Winner?",
        fetched_at=stale_time,
    )
    stale_forecast = _forecast(stale_market.ticker, 0.60, 0.08)
    publish_fresh_sports_display_board(
        [stale_market],
        {stale_market.ticker: (stale_forecast, stale_time.isoformat())},
        base_path=tmp_path / "unused.json",
        output_path=display_path,
        now=stale_time,
    )

    with pytest.raises(Exception, match="no current-day sports forecast"):
        select_sports_model_source_path(
            board_path=base_path,
            display_path=display_path,
            seed_path=tmp_path / "missing-seed.json",
            now=NOW,
        )


def _public_raw(market: MarketView, *, yes_ask: int | None = None) -> dict:
    return {
        "ticker": market.ticker,
        "title": market.title,
        "status": market.status,
        "close_time": market.close_time,
        "yes_bid": max(1, (yes_ask or market.yes_ask) - 2),
        "yes_ask": yes_ask or market.yes_ask,
        "no_bid": max(1, 98 - (yes_ask or market.yes_ask)),
        "no_ask": 100 - (yes_ask or market.yes_ask),
        "liquidity": 500,
        "volume": 100,
        "occurrence_datetime": market.raw["occurrence_datetime"],
        "category": "Sports",
    }


def test_cached_refresh_preserves_and_binds_governed_source_lineage(
    tmp_path: Path,
) -> None:
    from autonomy.sports_board_refresh import (
        MODEL_SEED_ARTIFACT_SOURCE,
        refresh_sports_display_board,
    )

    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    forecast = _forecast(market.ticker, 0.60, 0.08)
    seed_path = tmp_path / "sports_model_seed.json"
    display_path = tmp_path / "bet_board_display.json"
    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        output_path=seed_path,
        now=NOW,
        artifact_source=MODEL_SEED_ARTIFACT_SOURCE,
    )
    refreshed = refresh_sports_display_board(
        base_path=seed_path,
        output_path=display_path,
        fetch_series=lambda _series: {"markets": [_public_raw(market)]},
        series=["KXMLBGAME"],
        now=NOW + timedelta(seconds=1),
    )
    row = _all_rows(refreshed)[0]

    assert row["forecast_sources_used"] == forecast.sources_used
    assert row["forecast_sources_provenance_status"] == (
        "GOVERNED_NON_MARKET_SOURCE_PRESENT"
    )
    row["forecast_sources_used"] = {"market_prior": 1.0}
    display_path.write_text(__import__("json").dumps(refreshed), encoding="utf-8")
    read = read_board_artifact(display_path, now=NOW + timedelta(seconds=2))
    assert _all_rows(read)[0]["tier_display_bucket"] == "UNATTRIBUTED"


def test_market_prior_only_quote_drift_cannot_mint_a_tier(
    tmp_path: Path,
) -> None:
    from autonomy.sports_board_refresh import (
        MODEL_SEED_ARTIFACT_SOURCE,
        refresh_sports_display_board,
    )

    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    prior_only = Forecast(
        **{
            **_forecast(market.ticker, 0.60, 0.08).__dict__,
            "sources_used": {"market_prior": 1.0},
        }
    )
    seed_path = tmp_path / "sports_model_seed.json"
    display_path = tmp_path / "bet_board_display.json"
    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (prior_only, NOW.isoformat())},
        output_path=seed_path,
        now=NOW,
        artifact_source=MODEL_SEED_ARTIFACT_SOURCE,
    )
    refreshed = refresh_sports_display_board(
        base_path=seed_path,
        output_path=display_path,
        fetch_series=lambda _series: {
            "markets": [_public_raw(market, yes_ask=20)]
        },
        series=["KXMLBGAME"],
        now=NOW + timedelta(seconds=1),
    )
    row = _all_rows(refreshed)[0]

    assert row["model_status"] == "MARKET_PRIOR_ONLY"
    assert row["tier"] is None
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert refreshed["refreshed_tier_count"] == 0
    public_row = _all_rows(
        read_board_artifact(display_path, now=NOW + timedelta(seconds=2))
    )[0]
    assert public_row["tier_display_reason"] == (
        "cached_model_market_prior_only"
    )


def test_zero_liquidity_display_row_is_explicitly_unattributed(
    tmp_path: Path,
) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    market = MarketView(**{**market.__dict__, "liquidity": 0})
    forecast = _forecast(market.ticker, 0.90, 0.05)
    display_path = tmp_path / "bet_board_display.json"
    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        output_path=display_path,
        now=NOW,
    )
    row = _all_rows(
        read_board_artifact(display_path, now=NOW + timedelta(seconds=1))
    )[0]

    assert row["tier"] is None
    assert row["tier_display_bucket"] == "UNATTRIBUTED"
    assert row["tier_display_reason"] == "no_executable_depth"


def test_current_quote_sizes_grade_zero_legacy_liquidity_and_bind_display_row(
    tmp_path: Path,
) -> None:
    market = _market(
        "KXMLBGAME-26JUL221500NYYBOS-NYY",
        title="New York vs Boston Winner?",
    )
    market = MarketView(**{
        **market.__dict__,
        "liquidity": 0,
        "raw": {
            **market.raw,
            "yes_bid_size_fp": "145999.74",
            "yes_ask_size_fp": "471822.17",
            "liquidity_dollars": "0.0000",
        },
    })
    forecast = _forecast(market.ticker, 0.90, 0.05)
    display_path = tmp_path / "bet_board_display.json"
    publish_fresh_sports_display_board(
        [market],
        {market.ticker: (forecast, NOW.isoformat())},
        output_path=display_path,
        now=NOW,
    )
    first = read_board_artifact(
        display_path, now=NOW + timedelta(seconds=1)
    )
    row = _all_rows(first)[0]

    assert row["tier_policy_version"] == "executable_value_v5"
    assert row["tier"] == "A"
    assert row["tier_display_bucket"] == "A"
    assert row["depth_source"] == "quote_sizes_fp"
    assert row["effective_depth"] == pytest.approx(145999.74)
    assert row["selected_bid_size_fp"] == pytest.approx(145999.74)
    assert row["selected_ask_size_fp"] == pytest.approx(471822.17)
    assert row["tier_effective_depth"] == pytest.approx(145999.74)

    # The public reader binds the frozen selected size back to the visible
    # normalized quote-size field instead of trusting a self-hash alone.
    stored = __import__("json").loads(display_path.read_text(encoding="utf-8"))
    stored_row = _all_rows(stored)[0]
    stored_row["yes_bid_size_fp"] = 1.0
    display_path.write_text(__import__("json").dumps(stored), encoding="utf-8")
    tampered = read_board_artifact(
        display_path, now=NOW + timedelta(seconds=2)
    )
    tampered_row = _all_rows(tampered)[0]
    assert tampered_row["tier_display_bucket"] == "UNATTRIBUTED"
    assert tampered_row["tier_display_reason"] == (
        "snapshot_not_bound_to_visible_row"
    )


def test_atomic_replace_retries_transient_windows_permission_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autonomy.sports_board_refresh as refresh

    source = tmp_path / "candidate.json"
    destination = tmp_path / "board.json"
    source.write_text("new", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")
    real_replace = refresh.os.replace
    calls = 0

    def flaky_replace(src, dst):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError("brief reader lock")
        real_replace(src, dst)

    monkeypatch.setattr(refresh.os, "replace", flaky_replace)
    monkeypatch.setattr(refresh.time, "sleep", lambda _seconds: None)

    refresh._replace_with_retry(source, destination, attempts=4)

    assert calls == 3
    assert destination.read_text(encoding="utf-8") == "new"
    assert not source.exists()


def test_atomic_replace_fails_boundedly_and_preserves_prior_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import autonomy.sports_board_refresh as refresh

    source = tmp_path / "candidate.json"
    destination = tmp_path / "board.json"
    source.write_text("new", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")
    calls = 0

    def locked_replace(_src, _dst):
        nonlocal calls
        calls += 1
        raise PermissionError("persistent reader lock")

    monkeypatch.setattr(refresh.os, "replace", locked_replace)
    monkeypatch.setattr(refresh.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError):
        refresh._replace_with_retry(source, destination, attempts=3)

    assert calls == 3
    assert destination.read_text(encoding="utf-8") == "old"
    assert source.read_text(encoding="utf-8") == "new"
