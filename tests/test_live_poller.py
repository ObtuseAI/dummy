"""Wave-3 event-driven live-game poller: pure-core diffing + gated I/O shell."""
from __future__ import annotations

import json
from pathlib import Path

from autonomy.live_odds import EspnSummaryBook
from autonomy.live_poller import (
    BASE_OUT,
    LEAD_CHANGE,
    PERIOD,
    SCORE,
    STATUS_IN,
    STATUS_POST,
    ChangeEvent,
    GameState,
    LiveGamePoller,
    change_record,
    diff_states,
    parse_game_state,
)
from autonomy.sports.baseball import base_state_key

_FIXTURE = Path(__file__).parent / "fixtures" / "mlb_summary_401816130_baseout.json"


def _play(home, away, outs, period=1, first=False, second=False, third=False):
    play = {"homeScore": home, "awayScore": away, "outs": outs, "period": {"number": period}}
    if first:
        play["onFirst"] = {"athlete": {"id": "1"}}
    if second:
        play["onSecond"] = {"athlete": {"id": "2"}}
    if third:
        play["onThird"] = {"athlete": {"id": "3"}}
    return play


def _summary(plays, status=None):
    payload: dict = {"plays": list(plays)}
    if status is not None:
        payload["header"] = {"competitions": [{"status": {"type": {"state": status}}}]}
    return payload


# ---- parse_game_state --------------------------------------------------------

def test_parse_reads_base_out_and_score_from_last_play():
    summary = _summary([_play(1, 0, 2, period=3, first=True, third=True)], status="in")
    state = parse_game_state(summary, event_id="e1", league="mlb")
    assert state.status == "in"
    assert (state.home_score, state.away_score) == (1, 0)
    assert state.period == 3
    assert state.outs == 2
    assert state.base_state == base_state_key(True, False, True)
    assert state.lead == 1


def test_parse_real_fixture_last_play():
    summary = json.loads(_FIXTURE.read_text())
    state = parse_game_state(summary, event_id="401816130", league="mlb", status="post")
    # Fixture's trimmed plays carry score/outs/period; parse must not crash and
    # must surface the last recorded state.
    assert state.status == "post"
    assert state.outs is not None
    assert state.base_state is not None


def test_parse_failclosed_on_empty_summary():
    state = parse_game_state(None, event_id="e1", league="mlb")
    assert state.status == "unknown"
    assert state.home_score is None and state.base_state is None and state.outs is None


def test_parse_header_score_fallback_when_no_plays():
    summary = {
        "header": {"competitions": [{
            "status": {"type": {"state": "in"}},
            "competitors": [
                {"homeAway": "home", "score": "4"},
                {"homeAway": "away", "score": "2"},
            ],
        }]},
    }
    state = parse_game_state(summary, event_id="e1", league="nba")
    assert (state.home_score, state.away_score) == (4, 2)
    assert state.status == "in"


# ---- diff_states (pure core) -------------------------------------------------

def test_first_sight_live_emits_status_in():
    curr = GameState("e1", "mlb", "in", 0, 0, 1)
    events = diff_states(None, curr)
    assert [e.kind for e in events] == [STATUS_IN]


def test_first_sight_pregame_emits_nothing():
    curr = GameState("e1", "mlb", "pre")
    assert diff_states(None, curr) == []


def test_identical_states_emit_nothing():
    s = GameState("e1", "mlb", "in", 2, 1, 4, base_state_key(True, False, False), 1)
    assert diff_states(s, s) == []


def test_score_change_emits_score_event_with_lead():
    prev = GameState("e1", "mlb", "in", 1, 1, 5)
    curr = GameState("e1", "mlb", "in", 3, 1, 5)
    events = {e.kind: e for e in diff_states(prev, curr)}
    assert SCORE in events
    assert events[SCORE].detail["lead"] == 2
    assert events[SCORE].detail["home_score"] == 3


def test_lead_flip_emits_lead_change():
    prev = GameState("e1", "mlb", "in", 1, 2, 7)  # away ahead
    curr = GameState("e1", "mlb", "in", 3, 2, 7)  # home ahead
    kinds = {e.kind for e in diff_states(prev, curr)}
    assert SCORE in kinds and LEAD_CHANGE in kinds


def test_tie_break_counts_as_lead_change():
    prev = GameState("e1", "mlb", "in", 2, 2, 6)
    curr = GameState("e1", "mlb", "in", 3, 2, 6)
    assert LEAD_CHANGE in {e.kind for e in diff_states(prev, curr)}


def test_period_change_emits_period_event():
    prev = GameState("e1", "mlb", "in", 0, 0, 4)
    curr = GameState("e1", "mlb", "in", 0, 0, 5)
    events = {e.kind: e for e in diff_states(prev, curr)}
    assert events[PERIOD].detail == {"from": 4, "to": 5}


def test_base_out_change_emits_base_out_event():
    empty = base_state_key(False, False, False)
    loaded = base_state_key(True, True, True)
    prev = GameState("e1", "mlb", "in", 0, 0, 1, empty, 0)
    curr = GameState("e1", "mlb", "in", 0, 0, 1, loaded, 0)
    events = {e.kind: e for e in diff_states(prev, curr)}
    assert events[BASE_OUT].detail["base_state"] == loaded
    assert events[BASE_OUT].detail["prev_base_state"] == empty


def test_status_transitions():
    pre_to_in = diff_states(GameState("e1", "mlb", "pre"), GameState("e1", "mlb", "in"))
    assert STATUS_IN in {e.kind for e in pre_to_in}
    in_to_post = diff_states(GameState("e1", "mlb", "in", 3, 2, 9), GameState("e1", "mlb", "post", 3, 2, 9))
    assert STATUS_POST in {e.kind for e in in_to_post}


def test_change_record_shape():
    state = GameState("e1", "mlb", "in", 3, 1, 5, base_state_key(True, False, False), 1)
    rec = change_record(ChangeEvent("e1", "mlb", SCORE, {"lead": 2}), state)
    assert rec["event_type"] == "live_game_change"
    assert rec["source"] == "espn_live_poller"
    assert rec["kind"] == SCORE and rec["event_id"] == "e1"
    assert rec["home_score"] == 3 and rec["outs"] == 1


# ---- LiveGamePoller (gated I/O shell) ---------------------------------------

def _scoreboard(live_event_ids):
    return {"events": [
        {
            "id": eid,
            "date": "2026-07-16T00:00Z",
            "competitions": [{
                "status": {"type": {"state": "in"}},
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "AAA"}, "score": "0"},
                    {"homeAway": "away", "team": {"abbreviation": "BBB"}, "score": "0"},
                ],
            }],
        }
        for eid in live_event_ids
    ]}


def test_disabled_by_default_is_inert(monkeypatch):
    monkeypatch.setenv("DUMMY_LIVE_POLLER", "1")

    def _boom(*a, **k):
        raise AssertionError("must not fetch when disabled")

    poller = LiveGamePoller(fetch_scoreboard=_boom, enabled=False)
    result = poller.poll_once()
    assert result.events == () and result.live_event_ids == ()


def test_env_flag_required_even_when_enabled(monkeypatch):
    monkeypatch.delenv("DUMMY_LIVE_POLLER", raising=False)

    def _boom(*a, **k):
        raise AssertionError("must not fetch without env flag")

    poller = LiveGamePoller(fetch_scoreboard=_boom, enabled=True)
    assert poller.enabled is False
    assert poller.poll_once().events == ()


def test_enabled_emits_changes_and_invokes_hook_and_sink(monkeypatch):
    monkeypatch.setenv("DUMMY_LIVE_POLLER", "1")
    # Two cycles of the same live event: first sight, then a run scores.
    summaries = iter([
        _summary([_play(0, 0, 0, period=1)], status="in"),
        _summary([_play(1, 0, 1, period=1, first=True)], status="in"),
    ])
    book = EspnSummaryBook(league="mlb", fetch_summary=lambda lg, ev: next(summaries))
    hook_calls: list[tuple[str, str]] = []
    sink: list[dict] = []
    poller = LiveGamePoller(
        book=book,
        fetch_scoreboard=lambda lg, dates: _scoreboard(["e1"]),
        on_change=lambda ev, st: hook_calls.append((ev.kind, st.status)),
        record_event=sink.append,
        enabled=True,
    )

    first = poller.poll_once()
    assert STATUS_IN in {e.kind for e in first.events}
    assert first.next_interval == poller.fast_interval  # live -> fast cadence
    assert first.live_event_ids == ("e1",)

    second = poller.poll_once()
    kinds = {e.kind for e in second.events}
    assert SCORE in kinds and BASE_OUT in kinds
    assert ("score", "in") in hook_calls
    assert any(r["kind"] == "score" for r in sink)


def test_backoff_grows_when_nothing_live(monkeypatch):
    monkeypatch.setenv("DUMMY_LIVE_POLLER", "1")
    poller = LiveGamePoller(
        fetch_scoreboard=lambda lg, dates: {"events": []},
        enabled=True,
        idle_interval=60.0,
        max_idle_interval=480.0,
    )
    i1 = poller.poll_once().next_interval
    i2 = poller.poll_once().next_interval
    i3 = poller.poll_once().next_interval
    assert i1 == 60.0 and i2 == 120.0 and i3 == 240.0
    for _ in range(10):
        last = poller.poll_once().next_interval
    assert last == 480.0  # capped


def test_hook_exception_does_not_break_cycle(monkeypatch):
    monkeypatch.setenv("DUMMY_LIVE_POLLER", "1")
    book = EspnSummaryBook(league="mlb", fetch_summary=lambda lg, ev: _summary([_play(0, 0, 0)], status="in"))

    def _raise(ev, st):
        raise RuntimeError("bad hook")

    poller = LiveGamePoller(
        book=book,
        fetch_scoreboard=lambda lg, dates: _scoreboard(["e1"]),
        on_change=_raise,
        enabled=True,
    )
    result = poller.poll_once()  # must not raise
    assert STATUS_IN in {e.kind for e in result.events}


def test_failclosed_on_summary_fetch_error(monkeypatch):
    monkeypatch.setenv("DUMMY_LIVE_POLLER", "1")

    def _raise_fetch(lg, ev):
        raise RuntimeError("network down")

    book = EspnSummaryBook(league="mlb", fetch_summary=_raise_fetch)
    poller = LiveGamePoller(
        book=book,
        fetch_scoreboard=lambda lg, dates: _scoreboard(["e1"]),
        enabled=True,
    )
    result = poller.poll_once()  # unknown state, no crash, no phantom change
    assert result.events == ()


def test_discover_live_failclosed_on_scoreboard_error(monkeypatch):
    monkeypatch.setenv("DUMMY_LIVE_POLLER", "1")

    def _raise(lg, dates):
        raise RuntimeError("scoreboard down")

    poller = LiveGamePoller(fetch_scoreboard=_raise, enabled=True)
    assert poller.discover_live("mlb") == []
    assert poller.poll_once().events == ()
