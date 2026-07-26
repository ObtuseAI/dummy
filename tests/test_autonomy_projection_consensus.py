"""FanGraphs projection-consensus intake (fantasy leg #1) invariants.

Parsing tests read committed, trimmed REAL FanGraphs API rows captured
2026-07-16 (tests/fixtures/fangraphs_steamer_{bat,pit}_sample.json). No test
touches the network: every fetch is an injected callable.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import autonomy.ingest.fantasy.fangraphs as fangraphs_module
from autonomy.ingest.fantasy.fangraphs import (
    DEFAULT_SYSTEM,
    LEAGUE_AVG_RUNS_PER_GAME,
    MAX_RUNS_PER_GAME,
    MIN_RUNS_PER_GAME,
    PROJECTION_SYSTEMS,
    ProjectionBook,
    aggregate_team_projections,
    canonical_mlb_team,
    parse_projection_row,
    parse_projections,
)
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.projection_consensus import ProjectionConsensusSignal

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _fixture_fetch(system: str, stat_group: str):
    assert system in PROJECTION_SYSTEMS
    return _load(f"fangraphs_steamer_{stat_group}_sample.json")


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(days=2)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _book() -> ProjectionBook:
    book = ProjectionBook(fetch_fn=_fixture_fetch)
    book.refresh()
    return book


# ---------------------------------------------------------------- team mapping

def test_canonical_team_mapping_covers_fangraphs_namespace():
    # FanGraphs 3-letter forms -> repo-canonical abbreviations.
    assert canonical_mlb_team("KCR") == "KC"
    assert canonical_mlb_team("SDP") == "SD"
    assert canonical_mlb_team("SFG") == "SF"
    assert canonical_mlb_team("TBR") == "TB"
    assert canonical_mlb_team("WSN") == "WSH"
    assert canonical_mlb_team("OAK") == "ATH"
    # ESPN/Kalshi aliases the contract parser also honors.
    assert canonical_mlb_team("AZ") == "ARI"
    assert canonical_mlb_team("CWS") == "CHW"
    # Already-canonical forms pass through (case-insensitively).
    assert canonical_mlb_team("nyy") == "NYY"
    assert canonical_mlb_team("DET") == "DET"


def test_canonical_team_unknown_fails_closed():
    assert canonical_mlb_team("") is None
    assert canonical_mlb_team(None) is None
    assert canonical_mlb_team("ZZZ") is None
    assert canonical_mlb_team("MONTREAL") is None


# --------------------------------------------------------------------- parsing

def test_parse_batter_fixture_rows():
    players = parse_projections(_load("fangraphs_steamer_bat_sample.json"),
                                "steamer", "bat")
    by_name = {p.name: p for p in players}
    # The blank-team free agent row is dropped (unknown-team fail-closed).
    assert "Free Agent Placeholder" not in by_name
    assert len(players) == 4
    judge = by_name["Aaron Judge"]
    assert judge.team == "NYY"
    assert judge.player_id == "15640"
    assert judge.stat_group == "bat"
    assert judge.home_runs == pytest.approx(42.2973)
    assert judge.woba == pytest.approx(0.412247)
    assert judge.wrc_plus == pytest.approx(169.653)
    assert judge.adp == pytest.approx(1.85, abs=1e-3)
    # Full q10..q90 wOBA band survives.
    assert judge.percentiles["q10"] == pytest.approx(0.378)
    assert judge.percentiles["q90"] == pytest.approx(0.449)
    assert len(judge.percentiles) == 9
    # FanGraphs "SFG" is canonicalized on the way in.
    assert by_name["Rafael Devers"].team == "SF"


def test_parse_pitcher_fixture_rows():
    players = parse_projections(_load("fangraphs_steamer_pit_sample.json"),
                                "steamer", "pit")
    assert len(players) == 5
    skubal = next(p for p in players if p.name == "Tarik Skubal")
    assert skubal.team == "DET"
    assert skubal.era == pytest.approx(2.79447)
    assert skubal.fip == pytest.approx(2.78176)
    assert skubal.innings_pitched == pytest.approx(199.765)
    # Pitcher percentile band is ERA-space (q10 worse than q90).
    assert skubal.percentiles["q10"] > skubal.percentiles["q90"]


def test_parse_row_requires_identity_and_team():
    assert parse_projection_row({}, "steamer", "bat") is None
    assert parse_projection_row(
        {"PlayerName": "No Id", "Team": "NYY"}, "steamer", "bat") is None
    assert parse_projection_row(
        {"PlayerName": "Bad Team", "playerid": "1", "Team": "XX"},
        "steamer", "bat") is None
    assert parse_projection_row("not-a-dict", "steamer", "bat") is None


def test_parse_projections_tolerates_malformed_payloads():
    assert parse_projections(None, "steamer", "bat") == []
    assert parse_projections("garbage", "steamer", "bat") == []
    assert parse_projections({"unexpected": True}, "steamer", "bat") == []
    assert parse_projections([None, 42, "x"], "steamer", "bat") == []
    # A dict wrapper around the array still parses.
    wrapped = {"data": _load("fangraphs_steamer_bat_sample.json")}
    assert len(parse_projections(wrapped, "steamer", "bat")) == 4


# ----------------------------------------------------------------- aggregation

def test_aggregate_team_projections_rates():
    batters = parse_projections(_load("fangraphs_steamer_bat_sample.json"),
                                "steamer", "bat")
    pitchers = parse_projections(_load("fangraphs_steamer_pit_sample.json"),
                                 "steamer", "pit")
    teams = aggregate_team_projections(batters, pitchers)
    assert set(teams) == {"NYY", "DET", "SF"}  # offense rate required
    det = teams["DET"]
    assert det.batter_count == 2 and det.pitcher_count == 2
    # IP-weighted ERA lands between the two starters' ERAs, nearer Skubal's.
    assert 2.79447 < det.team_era < 3.89128
    assert det.team_era == pytest.approx(
        (2.79447 * 199.765 + 3.89128 * 163.146) / (199.765 + 163.146))
    assert det.defense_is_projected
    # All rates live inside the sanity clamps.
    for team in teams.values():
        assert MIN_RUNS_PER_GAME <= team.runs_per_game <= MAX_RUNS_PER_GAME
        assert MIN_RUNS_PER_GAME <= team.runs_allowed_per_game <= MAX_RUNS_PER_GAME
    # SF has batters (Devers) but no pitchers in the fixture: defense falls
    # back to league average and is flagged.
    assert not teams["SF"].defense_is_projected
    assert teams["SF"].runs_allowed_per_game == LEAGUE_AVG_RUNS_PER_GAME


def test_aggregate_realistic_magnitudes_unclamped():
    """Realistic full-roster sums land in MLB-sane ranges WITHOUT clamping.

    (Phenon lesson: sanity-check magnitudes when mixing differently-scaled
    sources -- season counting stats vs per-9 rates here.)
    """
    bat = [{"PlayerName": f"B{i}", "playerid": str(i), "Team": "KCR",
            "R": 57.0, "wOBA": 0.32} for i in range(13)]  # ~741 team runs
    pit = [{"PlayerName": f"P{i}", "playerid": str(100 + i), "Team": "KCR",
            "ERA": 4.0, "IP": 118.0} for i in range(12)]  # ~1416 IP
    teams = aggregate_team_projections(
        parse_projections(bat, "steamer", "bat"),
        parse_projections(pit, "steamer", "pit"))
    kc = teams["KC"]  # KCR canonicalized on the way in
    assert kc.runs_per_game == pytest.approx(741.0 / 162.0)  # ~4.57, no clamp
    assert kc.runs_allowed_per_game == pytest.approx(4.0 * 1.08)  # ~4.32
    assert kc.defense_is_projected
    assert kc.batter_count == 13 and kc.pitcher_count == 12


# ------------------------------------------------------------------------ book

def test_book_refresh_and_lookup_through_any_namespace():
    book = _book()
    assert not book.is_empty()
    assert book.team("DET") is not None
    # Lookup canonicalizes: FanGraphs and ESPN alias forms hit the same team.
    assert book.team("SFG") is book.team("SF")
    assert book.team("zzz") is None
    assert book.team(None) is None
    assert len(book.players()) == 9


def test_book_fails_closed_on_fetch_error():
    def broken(system: str, stat_group: str):
        raise RuntimeError("feed down")

    book = ProjectionBook(fetch_fn=broken)
    book.refresh()
    assert book.is_empty()
    assert book.teams() == {}
    assert book.players() == []
    assert book.team("NYY") is None


def test_unrefreshed_book_is_empty():
    book = ProjectionBook(fetch_fn=_fixture_fetch)
    assert book.is_empty()  # no implicit fetch: refresh() is the only trigger
    assert book.team("NYY") is None


def test_book_reset_empties_a_loaded_book():
    book = _book()
    book.reset()
    assert book.is_empty()


def test_unknown_projection_system_falls_back_to_default():
    book = ProjectionBook(system="not-a-system", fetch_fn=_fixture_fetch)
    assert book.system == DEFAULT_SYSTEM
    assert book.source_name == "fangraphs_steamer"


# ---------------------------------------------------------------------- ledger

def test_refresh_records_external_observations(tmp_path, monkeypatch):
    observed_times = iter(
        (
            NOW.isoformat(),
            (NOW + timedelta(seconds=1)).isoformat(),
        )
    )
    monkeypatch.setattr(fangraphs_module, "_now_iso", lambda: next(observed_times))
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    book = ProjectionBook(fetch_fn=_fixture_fetch, ledger=ledger)
    book.refresh()
    summary = ledger.external_observation_summary()
    # 4 mapped batters (wOBA) + 5 pitchers (ERA); the free agent never lands.
    assert summary["sources"]["fangraphs_steamer"]["observations"] == 9
    rows = ledger._conn.execute(
        "SELECT series_id, value, unit, features FROM external_observations"
        " WHERE source='fangraphs_steamer' ORDER BY series_id"
    ).fetchall()
    by_series = {row[0]: row for row in rows}
    judge = by_series["NYY:15640:steamer"]
    assert judge[1] == pytest.approx(0.412247)
    assert judge[2] == "woba"
    features = json.loads(judge[3])
    assert features["percentiles"]["q50"] == pytest.approx(0.412)
    assert features["stat_group"] == "bat"
    assert features["adp"] == pytest.approx(1.85, abs=1e-3)
    skubal = by_series["DET:22267:steamer"]
    assert skubal[1] == pytest.approx(2.79447)
    assert skubal[2] == "era"
    # Each refresh is a NEW point-in-time vintage (observed_at is part of the
    # content-addressed key), so a second snapshot doubles the rows; re-running
    # with the SAME observed_at would dedup instead.
    book.refresh()
    summary = ledger.external_observation_summary()
    assert summary["sources"]["fangraphs_steamer"]["observations"] == 18


def test_ledger_errors_never_disturb_the_book(tmp_path):
    class ExplodingLedger:
        def record_external_observation(self, **kwargs):
            raise RuntimeError("disk full")

    book = ProjectionBook(fetch_fn=_fixture_fetch, ledger=ExplodingLedger())
    book.refresh()
    assert not book.is_empty()  # persistence is best-effort, never load-bearing


# ---------------------------------------------------------------------- signal

def _signal(**kwargs) -> ProjectionConsensusSignal:
    return ProjectionConsensusSignal(book=_book(), **kwargs)


def test_applicable_only_for_supported_mlb_markets():
    signal = _signal()
    assert signal.applicable(
        _market("KXMLBGAME-26JUL16DETNYY-DET", "Detroit vs New York Winner?"))
    assert signal.applicable(_market(
        "KXMLBTOTAL-26JUL16DETNYY-9", "Total Runs?", floor_strike=8.5))
    # RFI/spread are out of scope for v1; non-MLB and non-sports never apply.
    assert not signal.applicable(_market("KXMLBRFI-26JUL16DETNYY", "Run First Inning?"))
    assert not signal.applicable(
        _market("KXNBAGAME-26JUL16LALBOS-LAL", "Lakers vs Celtics Winner?"))


def test_winner_emission_shape_and_consistency():
    signal = _signal()
    det = signal.generate(
        _market("KXMLBGAME-26JUL16DETNYY-DET", "Detroit vs New York Winner?"))
    nyy = signal.generate(
        _market("KXMLBGAME-26JUL16DETNYY-NYY", "Detroit vs New York Winner?"))
    assert det is not None and nyy is not None
    assert det.source == "fangraphs_projection_consensus"
    assert 0.0 < det.probability_yes < 1.0
    # The two sides of the same game price complementarily.
    assert det.probability_yes + nyy.probability_yes == pytest.approx(1.0, abs=0.01)
    assert det.features["challenger_only"] is True
    # promotion_eligible is evidence-driven, never hardcoded by this signal.
    assert "promotion_eligible" not in det.features
    assert det.features["market_type"] == "winner"
    assert det.features["subject"] == "DET"
    assert det.features["lineup_agnostic"] is True
    assert 0.0 < det.uncertainty <= 0.5
    assert "challenger-only" in det.rationale


def test_total_emission_monotone_in_threshold():
    signal = _signal()
    low = signal.generate(_market(
        "KXMLBTOTAL-26JUL16DETNYY-6", "Total Runs?", floor_strike=5.5))
    high = signal.generate(_market(
        "KXMLBTOTAL-26JUL16DETNYY-11", "Total Runs?", floor_strike=10.5))
    assert low is not None and high is not None
    assert low.probability_yes > high.probability_yes  # P(over) falls with the line
    assert low.features["challenger_only"] is True
    assert low.features["market_type"] == "total_runs"
    assert low.features["threshold"] == pytest.approx(5.5)
    assert low.features["expected_total_runs"] == pytest.approx(
        low.features["expected_first_runs"] + low.features["expected_second_runs"])


def test_total_without_strike_abstains():
    signal = _signal()
    assert signal.generate(
        _market("KXMLBTOTAL-26JUL16DETNYY-9", "Total Runs?")) is None


def test_abstains_when_team_missing_from_book():
    signal = _signal()
    # HOU/TEX have no projections in the fixture book -> abstain, fail-closed.
    assert signal.generate(
        _market("KXMLBGAME-26JUL16HOUTEX-HOU", "Houston vs Texas Winner?")) is None


def test_abstains_on_empty_book():
    book = ProjectionBook(fetch_fn=_fixture_fetch)  # never refreshed -> empty
    signal = ProjectionConsensusSignal(book=book)
    assert signal.generate(
        _market("KXMLBGAME-26JUL16DETNYY-DET", "Winner?")) is None


def test_defense_fallback_widens_uncertainty():
    signal = _signal()
    # SF's defense fell back to league average -> the emission widens.
    fallback = signal.generate(
        _market("KXMLBGAME-26JUL16SFDET-DET", "Giants vs Tigers Winner?"))
    clean = signal.generate(
        _market("KXMLBGAME-26JUL16DETNYY-DET", "Detroit vs New York Winner?"))
    assert fallback is not None and clean is not None
    assert fallback.uncertainty > clean.uncertainty
    assert fallback.features["first_defense_projected"] is False


# --------------------------------------------------------------- season gating

class _FakeSeasons:
    def __init__(self, active: bool):
        self._active = active
        self.calls = 0

    def active(self, league: str) -> bool:
        assert league == "mlb"
        self.calls += 1
        return self._active


def test_cycle_start_fetches_once_when_in_season():
    calls = []

    def counting_fetch(system: str, stat_group: str):
        calls.append((system, stat_group))
        return _fixture_fetch(system, stat_group)

    signal = ProjectionConsensusSignal(
        book=ProjectionBook(fetch_fn=counting_fetch), seasons=_FakeSeasons(True))
    signal.on_cycle_start()
    assert calls == [("steamer", "bat"), ("steamer", "pit")]  # one polite read
    assert not signal.book.is_empty()


def test_cycle_start_skips_fetch_when_mlb_dormant():
    calls = []

    def counting_fetch(system: str, stat_group: str):
        calls.append((system, stat_group))
        return _fixture_fetch(system, stat_group)

    book = ProjectionBook(fetch_fn=counting_fetch)
    signal = ProjectionConsensusSignal(book=book, seasons=_FakeSeasons(False))
    # Pre-load, then confirm a dormant cycle drops the book and never fetches.
    book.refresh()
    calls.clear()
    signal.on_cycle_start()
    assert calls == []
    assert book.is_empty()
    assert signal.generate(
        _market("KXMLBGAME-26JUL16DETNYY-DET", "Winner?")) is None


def test_cycle_start_survives_a_flaky_season_gate():
    class ExplodingSeasons:
        def active(self, league: str) -> bool:
            raise RuntimeError("gate down")

    signal = ProjectionConsensusSignal(
        book=ProjectionBook(fetch_fn=_fixture_fetch), seasons=ExplodingSeasons())
    signal.on_cycle_start()  # falls through to the book's fail-closed refresh
    assert not signal.book.is_empty()
