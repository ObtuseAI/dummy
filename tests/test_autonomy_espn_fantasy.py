"""ESPN fantasy baseball (flb) intake (fantasy leg #3) invariants.

Parsing tests read a committed, trimmed REAL ESPN kona_player_info capture
(tests/fixtures/espn_flb_players_sample.json, fetched 2026-07-16: NYY + LAD
top-owned players, one on the DL). No test touches the network: every fetch is
an injected callable.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from autonomy.ingest.fantasy.espn_fantasy import (
    AVAIL_AVAILABLE,
    AVAIL_DAY_TO_DAY,
    AVAIL_OUT,
    FantasyBook,
    ScratchEvent,
    aggregate_team_fantasy,
    availability_class,
    detect_scratch_events,
    parse_player,
    parse_players,
    proteam_to_canonical,
)
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Vertical
from autonomy.signals.espn_fantasy_crowd import EspnFantasyCrowdSignal

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _fixture_fetch():
    return _load("espn_flb_players_sample.json")


def _market(ticker: str, title: str, **raw) -> MarketView:
    payload = {"event_ticker": ticker.rsplit("-", 1)[0], **raw}
    return MarketView(
        ticker=ticker, title=title, vertical=Vertical.SPORTS, status="open",
        close_time=(NOW + timedelta(days=2)).isoformat(),
        yes_bid=44, yes_ask=46, no_bid=54, no_ask=56,
        volume=500, liquidity=1_000, raw=payload,
    )


def _book() -> FantasyBook:
    book = FantasyBook(fetch_fn=_fixture_fetch)
    book.refresh()
    return book


# ---------------------------------------------------------------- team mapping

def test_proteam_id_maps_to_canonical_mlb():
    assert proteam_to_canonical(10) == "NYY"
    assert proteam_to_canonical(19) == "LAD"
    assert proteam_to_canonical(23) == "PIT"
    # ESPN abbrev folds route through canonical_mlb_team: Ath->ATH, ChW->CHW,
    # Wsh->WSH, StL->STL.
    assert proteam_to_canonical(11) == "ATH"
    assert proteam_to_canonical(4) == "CHW"
    assert proteam_to_canonical(20) == "WSH"
    assert proteam_to_canonical(24) == "STL"


def test_proteam_id_unknown_fails_closed():
    assert proteam_to_canonical(0) is None        # free agent
    assert proteam_to_canonical(999) is None       # out-of-range id
    assert proteam_to_canonical(None) is None
    assert proteam_to_canonical("bad") is None


def test_availability_class_buckets():
    assert availability_class("ACTIVE") == AVAIL_AVAILABLE
    assert availability_class("") == AVAIL_AVAILABLE
    assert availability_class(None) == AVAIL_AVAILABLE
    assert availability_class("SOMETHING_NEW") == AVAIL_AVAILABLE  # unknown -> available
    assert availability_class("TEN_DAY_DL") == AVAIL_OUT
    assert availability_class("FIFTEEN_DAY_DL") == AVAIL_OUT
    assert availability_class("SIXTY_DAY_DL") == AVAIL_OUT
    assert availability_class("OUT") == AVAIL_OUT
    assert availability_class("SUSPENSION") == AVAIL_OUT
    assert availability_class("DAY_TO_DAY") == AVAIL_DAY_TO_DAY


# --------------------------------------------------------------------- parsing

def test_parse_fixture_players():
    players = parse_players(_fixture_fetch())
    assert len(players) == 8
    by_name = {p.name: p for p in players}
    judge = by_name["Aaron Judge"]
    assert judge.team == "NYY"
    assert judge.player_id and judge.player_id.isdigit()
    assert judge.injury_status == "TEN_DAY_DL"
    assert judge.availability == AVAIL_OUT
    assert judge.percent_owned == pytest.approx(99.29)
    assert judge.average_draft_position == pytest.approx(83.24)
    assert judge.draft_rank == 110
    ohtani = by_name["Shohei Ohtani"]
    assert ohtani.team == "LAD"
    assert ohtani.availability == AVAIL_AVAILABLE
    assert ohtani.projected_applied_total == pytest.approx(911.0)
    assert ohtani.projected_stats  # non-empty projected season line
    assert ohtani.is_pitcher is False  # defaultPositionId 10 (DH/util)


def test_parse_player_edge_cases():
    good = {"id": 1, "fullName": "X", "proTeamId": 10,
            "ownership": {"percentOwned": 50.0}}
    assert parse_player(good) is not None
    # missing identity
    assert parse_player({"fullName": "No Id", "proTeamId": 10,
                         "ownership": {"percentOwned": 1.0}}) is None
    assert parse_player({"id": 1, "proTeamId": 10,
                         "ownership": {"percentOwned": 1.0}}) is None
    # free agent (proTeamId 0) -> unknown-team fail-closed
    assert parse_player({"id": 1, "fullName": "FA Guy", "proTeamId": 0,
                         "ownership": {"percentOwned": 1.0}}) is None
    # LIGHT-ONLY row (no ownership block) -> dropped, fail-closed
    assert parse_player({"id": 1, "fullName": "Light", "proTeamId": 10}) is None
    assert parse_player({"id": 1, "fullName": "Light", "proTeamId": 10,
                         "ownership": None}) is None
    assert parse_player("not-a-dict") is None


def test_parse_players_tolerates_malformed_payloads():
    assert parse_players(None) == []
    assert parse_players("garbage") == []
    assert parse_players({"unexpected": True}) == []
    assert parse_players([None, 42, "x"]) == []
    # a dict wrapper around the array still parses
    wrapped = {"players": _fixture_fetch()}
    assert len(parse_players(wrapped)) == 8


def test_light_only_universe_parses_to_empty():
    """A response where the filter did not take (every row light/un-enriched)
    yields an empty parse -> the book fail-closes."""
    light = [{"id": i, "fullName": f"P{i}", "proTeamId": 10} for i in range(50)]
    assert parse_players(light) == []


# ----------------------------------------------------------------- aggregation

def test_aggregate_team_fantasy_over_fixture():
    teams = aggregate_team_fantasy(parse_players(_fixture_fetch()))
    assert set(teams) == {"NYY", "LAD"}
    nyy, lad = teams["NYY"], teams["LAD"]
    assert nyy.owned_player_count == 4 and lad.owned_player_count == 4
    # Aaron Judge (TEN_DAY_DL) is the one OUT among NYY's owned core.
    assert nyy.out_count == 1 and lad.out_count == 0
    assert nyy.public_backing == pytest.approx((99.77 + 99.29 + 99.21 + 98.71) / 100.0)
    # Ohtani's 911-pt projection dominates LAD's projected strength.
    assert lad.projected_strength > nyy.projected_strength
    assert "Aaron Judge" in nyy.top_owned


def test_aggregate_excludes_barely_owned_players():
    rows = [
        {"id": 1, "fullName": "Owned", "proTeamId": 10,
         "ownership": {"percentOwned": 40.0}},
        {"id": 2, "fullName": "Bench", "proTeamId": 10,
         "ownership": {"percentOwned": 0.4}},  # below MIN_OWNERSHIP_FOR_AGGREGATE
    ]
    teams = aggregate_team_fantasy(parse_players(rows))
    assert teams["NYY"].owned_player_count == 1  # only the 40%-owned player


# ------------------------------------------------------------- scratch feed

def test_detect_scratch_events_no_previous_is_empty():
    current = {"1": {"name": "X", "team": "NYY", "injury_status": "OUT",
                     "availability": AVAIL_OUT, "percent_owned": 90.0}}
    assert detect_scratch_events(None, current) == []
    assert detect_scratch_events({}, current) == []


def test_detect_scratch_availability_flip_and_ownership_swing():
    prev = {
        "1": {"name": "Flip", "team": "NYY", "injury_status": "ACTIVE",
              "availability": AVAIL_AVAILABLE, "percent_owned": 90.0},
        "2": {"name": "Swing", "team": "LAD", "injury_status": "ACTIVE",
              "availability": AVAIL_AVAILABLE, "percent_owned": 50.0},
        "3": {"name": "Steady", "team": "LAD", "injury_status": "ACTIVE",
              "availability": AVAIL_AVAILABLE, "percent_owned": 80.0},
    }
    cur = {
        "1": {"name": "Flip", "team": "NYY", "injury_status": "OUT",
              "availability": AVAIL_OUT, "percent_owned": 90.0},
        "2": {"name": "Swing", "team": "LAD", "injury_status": "ACTIVE",
              "availability": AVAIL_AVAILABLE, "percent_owned": 58.0},  # +8 swing
        "3": {"name": "Steady", "team": "LAD", "injury_status": "ACTIVE",
              "availability": AVAIL_AVAILABLE, "percent_owned": 81.0},  # tiny move
    }
    events = {e.player_id: e for e in detect_scratch_events(prev, cur)}
    assert set(events) == {"1", "2"}  # Steady (+1) is below the swing threshold
    assert events["1"].kind == "availability_change"
    assert events["1"].previous == AVAIL_AVAILABLE and events["1"].current == AVAIL_OUT
    assert events["2"].kind == "ownership_swing"


def test_detect_scratch_ignores_new_players():
    prev = {"1": {"availability": AVAIL_AVAILABLE, "percent_owned": 50.0,
                  "name": "A", "team": "NYY", "injury_status": "ACTIVE"}}
    cur = {
        "1": {"availability": AVAIL_AVAILABLE, "percent_owned": 50.0,
              "name": "A", "team": "NYY", "injury_status": "ACTIVE"},
        "2": {"availability": AVAIL_OUT, "percent_owned": 50.0,
              "name": "New", "team": "NYY", "injury_status": "OUT"},
    }
    # A newly-enriched player has no prior state -> no phantom scratch.
    assert detect_scratch_events(prev, cur) == []


# ------------------------------------------------------------------------ book

def test_book_refresh_and_lookup_through_any_namespace():
    book = _book()
    assert not book.is_empty()
    assert book.team("NYY") is not None
    assert book.team("nyy") is book.team("NYY")  # canonicalized lookup
    assert book.team("zzz") is None
    assert book.team(None) is None
    assert len(book.players()) == 8


def test_book_fails_closed_on_fetch_error():
    def broken():
        raise RuntimeError("feed down")

    book = FantasyBook(fetch_fn=broken)
    book.refresh()
    assert book.is_empty()
    assert book.teams() == {}
    assert book.players() == []
    assert book.team("NYY") is None
    assert book.scratch_events() == ()


def test_book_light_only_response_fails_closed():
    book = FantasyBook(
        fetch_fn=lambda: [{"id": i, "fullName": f"P{i}", "proTeamId": 10}
                          for i in range(20)])
    book.refresh()
    assert book.is_empty()  # un-enriched universe -> empty book


def test_unrefreshed_book_is_empty():
    book = FantasyBook(fetch_fn=_fixture_fetch)
    assert book.is_empty()
    assert book.team("NYY") is None


def test_book_reset_empties_a_loaded_book():
    book = _book()
    book.reset()
    assert book.is_empty()
    assert book.scratch_events() == ()


def test_book_emits_scratch_events_across_cycles():
    fixture = _fixture_fetch()

    def mutated():
        # Flip Aaron Judge back to ACTIVE on the second read.
        rows = json.loads(json.dumps(fixture))
        for row in rows:
            if row["fullName"] == "Aaron Judge":
                row["injuryStatus"] = "ACTIVE"
        return rows

    reads = [fixture, mutated()]
    book = FantasyBook(fetch_fn=lambda: reads.pop(0))
    book.refresh()
    assert book.scratch_events() == ()  # first cycle: no prior snapshot
    book.refresh()
    events = book.scratch_events()
    assert len(events) == 1
    assert events[0].kind == "availability_change"
    assert events[0].name == "Aaron Judge"
    assert events[0].previous == AVAIL_OUT and events[0].current == AVAIL_AVAILABLE


def test_book_empty_refresh_does_not_manufacture_scratches():
    """A failed/empty refresh must not wipe the prior snapshot, or the next
    good cycle would report every player as a change."""
    fixture = _fixture_fetch()
    reads = [fixture, [], fixture]
    book = FantasyBook(fetch_fn=lambda: reads.pop(0))
    book.refresh()          # baseline
    book.refresh()          # empty -> fail-closed, snapshot preserved
    assert book.is_empty()
    book.refresh()          # same fixture again -> no changes vs baseline
    assert book.scratch_events() == ()


# ---------------------------------------------------------------------- ledger

def test_refresh_records_external_observations(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    book = FantasyBook(fetch_fn=_fixture_fetch, ledger=ledger)
    book.refresh()
    summary = ledger.external_observation_summary()
    assert summary["sources"]["espn_flb"]["observations"] == 8
    rows = ledger._conn.execute(
        "SELECT series_id, value, unit, features FROM external_observations"
        " WHERE source='espn_flb' ORDER BY series_id"
    ).fetchall()
    by_series = {row[0]: row for row in rows}
    judge = next(r for sid, r in by_series.items() if sid.startswith("NYY:") and
                 json.loads(r[3])["name"] == "Aaron Judge")
    assert judge[1] == pytest.approx(99.29)  # value = percentOwned
    assert judge[2] == "percent_owned"
    features = json.loads(judge[3])
    assert features["availability"] == AVAIL_OUT
    assert features["injury_status"] == "TEN_DAY_DL"
    assert features["average_draft_position"] == pytest.approx(83.24)


def test_refresh_records_scratch_events(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    fixture = _fixture_fetch()

    def mutated():
        rows = json.loads(json.dumps(fixture))
        for row in rows:
            if row["fullName"] == "Aaron Judge":
                row["injuryStatus"] = "ACTIVE"
        return rows

    reads = [fixture, mutated()]
    book = FantasyBook(fetch_fn=lambda: reads.pop(0), ledger=ledger)
    book.refresh()
    book.refresh()
    scratch = ledger._conn.execute(
        "SELECT series_id, features FROM external_observations"
        " WHERE source='espn_flb_scratch'"
    ).fetchall()
    assert len(scratch) == 1
    assert json.loads(scratch[0][1])["name"] == "Aaron Judge"


def test_ledger_errors_never_disturb_the_book():
    class ExplodingLedger:
        def record_external_observation(self, **kwargs):
            raise RuntimeError("disk full")

    book = FantasyBook(fetch_fn=_fixture_fetch, ledger=ExplodingLedger())
    book.refresh()
    assert not book.is_empty()  # persistence is best-effort, never load-bearing


# ---------------------------------------------------------------------- signal

def _signal(**kwargs) -> EspnFantasyCrowdSignal:
    return EspnFantasyCrowdSignal(book=_book(), **kwargs)


def test_applicable_only_for_mlb_winner_markets():
    signal = _signal()
    assert signal.applicable(
        _market("KXMLBGAME-26JUL16NYYLAD-NYY", "New York vs Los Angeles Winner?"))
    # totals / RFI / other leagues are out of scope
    assert not signal.applicable(_market(
        "KXMLBTOTAL-26JUL16NYYLAD-9", "Total Runs?", floor_strike=8.5))
    assert not signal.applicable(
        _market("KXMLBRFI-26JUL16NYYLAD", "Run First Inning?"))
    assert not signal.applicable(
        _market("KXNBAGAME-26JUL16LALBOS-LAL", "Lakers vs Celtics Winner?"))


def test_winner_emission_shape_and_consistency():
    signal = _signal()
    nyy = signal.generate(
        _market("KXMLBGAME-26JUL16NYYLAD-NYY", "New York vs Los Angeles Winner?"))
    lad = signal.generate(
        _market("KXMLBGAME-26JUL16NYYLAD-LAD", "New York vs Los Angeles Winner?"))
    assert nyy is not None and lad is not None
    assert nyy.source == "espn_fantasy_crowd"
    assert 0.0 < nyy.probability_yes < 1.0
    # the two sides price complementarily
    assert nyy.probability_yes + lad.probability_yes == pytest.approx(1.0, abs=0.01)
    assert nyy.features["challenger_only"] is True
    # promotion_eligible is evidence-driven, never stamped by this signal
    assert "promotion_eligible" not in nyy.features
    assert nyy.features["market_type"] == "winner"
    assert nyy.features["subject"] == "NYY"
    assert nyy.features["public_lean"] is True
    assert nyy.features["subject_out_count"] == 1  # Aaron Judge on the DL
    assert 0.0 < nyy.uncertainty <= 0.5
    # one side (NYY) carries an OUT player -> uncertainty widened once
    assert nyy.uncertainty == pytest.approx(0.20 + 0.02)
    assert "challenger-only" in nyy.rationale


def test_abstains_when_team_missing_from_book():
    signal = _signal()
    # HOU/TEX are absent from the fixture book -> abstain, fail-closed.
    assert signal.generate(
        _market("KXMLBGAME-26JUL16HOUTEX-HOU", "Houston vs Texas Winner?")) is None


def test_abstains_on_empty_book():
    book = FantasyBook(fetch_fn=_fixture_fetch)  # never refreshed -> empty
    signal = EspnFantasyCrowdSignal(book=book)
    assert signal.generate(
        _market("KXMLBGAME-26JUL16NYYLAD-NYY", "Winner?")) is None


def test_abstains_when_too_few_owned_players():
    # NYY has only 2 owned players here -> below the min-owned floor -> abstain.
    rows = [
        {"id": 1, "fullName": "A", "proTeamId": 10,
         "ownership": {"percentOwned": 90.0}},
        {"id": 2, "fullName": "B", "proTeamId": 10,
         "ownership": {"percentOwned": 80.0}},
        {"id": 3, "fullName": "C", "proTeamId": 19,
         "ownership": {"percentOwned": 90.0}},
        {"id": 4, "fullName": "D", "proTeamId": 19,
         "ownership": {"percentOwned": 80.0}},
        {"id": 5, "fullName": "E", "proTeamId": 19,
         "ownership": {"percentOwned": 70.0}},
    ]
    book = FantasyBook(fetch_fn=lambda: rows)
    book.refresh()
    signal = EspnFantasyCrowdSignal(book=book)
    assert signal.generate(
        _market("KXMLBGAME-26JUL16NYYLAD-NYY", "Winner?")) is None


# --------------------------------------------------------------- season gating

class _FakeSeasons:
    def __init__(self, active: bool):
        self._active = active

    def active(self, league: str) -> bool:
        assert league == "mlb"
        return self._active


def test_cycle_start_fetches_once_when_in_season():
    calls = []

    def counting_fetch():
        calls.append(1)
        return _fixture_fetch()

    signal = EspnFantasyCrowdSignal(
        book=FantasyBook(fetch_fn=counting_fetch), seasons=_FakeSeasons(True))
    signal.on_cycle_start()
    assert len(calls) == 1
    assert not signal.book.is_empty()


def test_cycle_start_skips_fetch_when_mlb_dormant():
    calls = []

    def counting_fetch():
        calls.append(1)
        return _fixture_fetch()

    book = FantasyBook(fetch_fn=counting_fetch)
    signal = EspnFantasyCrowdSignal(book=book, seasons=_FakeSeasons(False))
    book.refresh()
    calls.clear()
    signal.on_cycle_start()
    assert calls == []
    assert book.is_empty()


def test_cycle_start_survives_a_flaky_season_gate():
    class ExplodingSeasons:
        def active(self, league: str) -> bool:
            raise RuntimeError("gate down")

    signal = EspnFantasyCrowdSignal(
        book=FantasyBook(fetch_fn=_fixture_fetch), seasons=ExplodingSeasons())
    signal.on_cycle_start()
    assert not signal.book.is_empty()


def test_scratch_event_is_frozen():
    event = ScratchEvent(
        kind="availability_change", player_id="1", name="X", team="NYY",
        injury_status="OUT", previous=AVAIL_AVAILABLE, current=AVAIL_OUT)
    with pytest.raises((AttributeError, Exception)):
        event.kind = "other"  # type: ignore[misc]
