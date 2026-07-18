"""Wave-17: live tape reader, monitor burst gating, calibrated fused shadow."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from autonomy.live_tape import fresh_events, fresh_live_games
from autonomy.ontology import Forecast
from autonomy.picks import FUSED_SOURCE, build_calibrated_fused_signal

NOW = datetime(2026, 7, 18, 4, 30, tzinfo=timezone.utc)


def _tape(tmp_path, records):
    path = tmp_path / "live_events.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return path


def _record(age_seconds, league="mlb", event_id="g1", kind="score"):
    observed = (NOW - timedelta(seconds=age_seconds)).isoformat()
    return {"kind": kind, "league": league, "event_id": event_id,
            "observed_at": observed, "home_score": 1, "away_score": 0}


# ------------------------------------------------------------------ tape


def test_fresh_events_filters_by_age(tmp_path):
    path = _tape(tmp_path, [_record(300), _record(60), _record(10)])
    fresh = fresh_events(120.0, path=path, now_fn=lambda: NOW)
    assert len(fresh) == 2


def test_fresh_live_games_dedupes_by_game(tmp_path):
    path = _tape(tmp_path, [
        _record(10, event_id="g1"), _record(20, event_id="g1"),
        _record(30, event_id="g2", league="wnba"),
    ])
    games = fresh_live_games(120.0, path=path, now_fn=lambda: NOW)
    assert games == {("mlb", "g1"), ("wnba", "g2")}


def test_tape_reader_fail_closed(tmp_path):
    assert fresh_events(120.0, path=tmp_path / "absent.jsonl",
                        now_fn=lambda: NOW) == []
    path = _tape(tmp_path, [])
    path.write_text("not json\n{\"broken\": \n", encoding="utf-8")
    assert fresh_events(120.0, path=path, now_fn=lambda: NOW) == []


def test_quiet_tape_means_no_fresh_games(tmp_path):
    path = _tape(tmp_path, [_record(500), _record(900)])
    assert fresh_live_games(120.0, path=path, now_fn=lambda: NOW) == set()


# --------------------------------------------------- calibrated fused shadow


def _forecast(p=0.70, ticker="KXMLBGAME-26JUL18NYYBOS-NYY"):
    return Forecast(
        market_ticker=ticker, probability_yes=p, uncertainty=0.12,
        sources_used={"mlb_intelligence": 1.2},
        market_implied_yes=0.55, edge_yes=p - 0.55, rationale="test")


def _scope_for(ticker="KXMLBGAME-26JUL18NYYBOS-NYY"):
    from autonomy.picks import build_fused_signal
    from autonomy.taxonomy import grading_scope

    raw = build_fused_signal(ticker, _forecast())
    return grading_scope(FUSED_SOURCE, ticker, raw.features)


def test_calibrated_shadow_applies_the_scope_map():
    scope = _scope_for()
    maps = {scope: [[0.0, 0.05], [0.5, 0.45], [1.0, 0.9]]}
    shadow = build_calibrated_fused_signal(
        "KXMLBGAME-26JUL18NYYBOS-NYY", _forecast(0.70), maps)
    assert shadow is not None
    assert shadow.source == f"{FUSED_SOURCE}::cal"
    # 0.70 interpolates between (0.5, 0.45) and (1.0, 0.9) -> 0.63.
    assert abs(shadow.probability_yes - 0.63) < 1e-9
    assert shadow.features["raw_probability"] == 0.70
    assert shadow.features["calibration_scope"] == scope


def test_no_map_for_scope_means_no_shadow():
    assert build_calibrated_fused_signal(
        "KXMLBGAME-26JUL18NYYBOS-NYY", _forecast(), {}) is None
    other = {"fused_forecast|SOMETHING|winner|pre": [[0.0, 0.0], [1.0, 1.0]]}
    assert build_calibrated_fused_signal(
        "KXWNBATOTAL-26JUL18LVANYL-T164", _forecast(), other) is None


def test_cal_suffix_resolves_to_the_parent_specialist():
    from autonomy.reliability import CALIBRATED_SOURCES
    from autonomy.taxonomy import specialist_for

    assert "fused_forecast" in CALIBRATED_SOURCES     # maps get fit nightly
    assert specialist_for("fused_forecast::cal") == "fused"
    assert specialist_for("mlb_total_runs::cal") == "mlb"


# -------------------------------------------------------- monitor burst lane


def test_monitor_exposes_sports_micro_pass():
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "run_dummy_mispricing_monitor_w17",
        root / "scripts" / "run_dummy_mispricing_monitor.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_dummy_mispricing_monitor_w17"] = module
    spec.loader.exec_module(module)
    assert callable(module.sports_live_micro_pass)
    assert callable(module._sports_scanner)
