"""Wave-29: movement featurizer + cross-book steam + dispersion over the
Wave-12 odds archive. Pure analysis, no scraping, no probability influence."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone

from autonomy.market_pressure import (
    Quote,
    SideSeries,
    detect_dispersion,
    detect_steam,
    movement_series,
    read_archive_window,
)
from autonomy.market_pressure.line_movement import read_archive_window as _read

HOUR = 3600.0


def _event(event_id, commence_ts, books):
    """books: {book_key: {"h2h": (home_price, away_price), ...}} -> Odds API event."""
    commence = datetime.fromtimestamp(commence_ts, timezone.utc).isoformat().replace("+00:00", "Z")
    bookmakers = []
    for book_key, markets in books.items():
        market_list = []
        for mkey, spec in markets.items():
            if mkey == "h2h":
                hp, ap = spec
                outcomes = [{"name": "HOME", "price": hp}, {"name": "AWAY", "price": ap}]
            elif mkey == "totals":
                over_p, under_p, point = spec
                outcomes = [{"name": "Over", "price": over_p, "point": point},
                            {"name": "Under", "price": under_p, "point": point}]
            else:  # spreads
                hp, ap, point = spec
                outcomes = [{"name": "HOME", "price": hp, "point": point},
                            {"name": "AWAY", "price": ap, "point": -point}]
            market_list.append({"key": mkey, "outcomes": outcomes})
        bookmakers.append({"key": book_key, "markets": market_list})
    return {"id": event_id, "home_team": "HOME", "away_team": "AWAY",
            "commence_time": commence, "sport_key": "baseball_mlb",
            "bookmakers": bookmakers}


def test_movement_series_devigs_and_orders_moneyline():
    now = 1_000_000.0
    commence = now + HOUR
    snaps = [
        (now - 3 * HOUR, _event("g1", commence, {"dk": {"h2h": (-110, -110)}})),
        (now - 1 * HOUR, _event("g1", commence, {"dk": {"h2h": (-140, +120)}})),
    ]
    series = movement_series(snaps)
    home = series[("g1", "dk", "h2h", "HOME")]
    assert home.quantity == "devig_prob"
    assert abs(home.opener() - 0.5) < 1e-6              # -110/-110 de-vigs to 0.5
    assert home.current() > 0.55                        # -140/+120 favours HOME
    assert home.total_move() > 0.05
    assert home.velocity(now, 6.0) is not None


def test_read_archive_window_filters_props_and_started_games(tmp_path):
    now = datetime.now(timezone.utc).timestamp()
    commence_future = now + HOUR
    commence_past = now - 2 * HOUR
    # Integer seconds round-trip through ISO without sub-microsecond drift.
    at_commence = float(int(now - HOUR))
    missing_commence = _event(
        "missing", commence_future, {"dk": {"h2h": (-110, -110)}},
    )
    missing_commence.pop("commence_time")
    shard = tmp_path / "odds_2026-07.jsonl.gz"
    rows = [
        {"ts": now - HOUR, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [_event("live", commence_past, {"dk": {"h2h": (-110, -110)}})]},
        {"ts": at_commence, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [_event("at-commence", at_commence, {"dk": {"h2h": (-110, -110)}})]},
        {"ts": now - HOUR, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [missing_commence]},
        {"ts": now + 1.0, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [_event("future", commence_future, {"dk": {"h2h": (-110, -110)}})]},
        {"ts": now - HOUR, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [_event("pre", commence_future, {"dk": {"h2h": (-110, -110)}})]},
        {"ts": now - HOUR, "key": "props|baseball_mlb|abc|batter_hits",
         "payload": {"id": "prop", "bookmakers": []}},          # dict, must skip
    ]
    with gzip.open(shard, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    got = read_archive_window(tmp_path, now=now, lookback_hours=48.0)
    ids = {ev["id"] for _ts, ev in got}
    assert ids == {"pre"}                                # live game + props filtered out
    assert _read is read_archive_window                  # re-exported symbol


def test_movement_series_rechecks_pregame_timestamp_boundaries():
    now = 1_000_000.0
    valid = _event("valid", now + HOUR, {"dk": {"h2h": (-110, -110)}})
    missing = _event("missing", now + HOUR, {"dk": {"h2h": (-110, -110)}})
    missing.pop("commence_time")
    snapshots = [
        (now - HOUR, valid),
        (now - HOUR, missing),
        (now, _event("at-commence", now, {"dk": {"h2h": (-110, -110)}})),
        (now + 1.0, _event("future", now + HOUR, {"dk": {"h2h": (-110, -110)}})),
    ]

    series = movement_series(snapshots, now=now)

    assert {identity[0] for identity in series} == {"valid"}


def test_velocity_uses_actual_elapsed_time_not_requested_lookback():
    now = 1_000_000.0
    series = SideSeries(
        event_id="game",
        book="book",
        market="h2h",
        side="HOME",
        commence=now + HOUR,
        quotes=[
            Quote(ts=now - 600.0, price=None, point=None, devig_prob=0.40),
            Quote(ts=now, price=None, point=None, devig_prob=0.50),
        ],
    )

    assert abs(series.velocity(now, 6.0) - 0.6) < 1e-12


def test_steam_fires_on_synchronized_move_with_originator():
    now = 1_000_000.0
    commence = now + HOUR
    base = {"h2h": (-110, -110)}
    up = {"h2h": (-160, +135)}                            # HOME devig ~0.60
    # t0 all flat; t1 only book A moved; t2 all moved.
    snaps = [
        (now - 4 * HOUR, _event("g", commence, {b: base for b in "ABCD"})),
        (now - 3 * HOUR, _event("g", commence, {"A": up, "B": base, "C": base, "D": base})),
        (now - 1 * HOUR, _event("g", commence, {b: up for b in "ABCD"})),
    ]
    series = movement_series(snaps)
    home = [series[("g", b, "h2h", "HOME")] for b in "ABCD"]
    steam = detect_steam(home, now=now, window_hours=6.0, min_books=3)
    assert steam.is_steam and steam.direction == 1
    assert steam.n_books_moved == 4
    assert steam.originator == "A"                        # A crossed first
    assert steam.synchrony_seconds and steam.synchrony_seconds > 0
    assert steam.magnitude > 0.05


def test_steam_fails_closed_below_min_books():
    now = 1_000_000.0
    commence = now + HOUR
    snaps = [
        (now - 4 * HOUR, _event("g", commence, {b: {"h2h": (-110, -110)} for b in "ABCD"})),
        (now - 1 * HOUR, _event("g", commence,
                                 {"A": {"h2h": (-160, 135)}, "B": {"h2h": (-160, 135)},
                                  "C": {"h2h": (-110, -110)}, "D": {"h2h": (-110, -110)}})),
    ]
    series = movement_series(snaps)
    home = [series[("g", b, "h2h", "HOME")] for b in "ABCD"]
    steam = detect_steam(home, now=now, window_hours=6.0, min_books=3)
    assert not steam.is_steam                             # only 2 books moved, need 3


def test_dispersion_names_the_soft_outlier():
    now = 1_000_000.0
    commence = now + HOUR
    # Three books tight near -130, one book soft at -105 (cheaper HOME).
    snaps = [(now - HOUR, _event("g", commence, {
        "A": {"h2h": (-130, 110)}, "B": {"h2h": (-132, 112)},
        "C": {"h2h": (-128, 108)}, "soft": {"h2h": (-105, -105)}}))]
    series = movement_series(snaps)
    home = [series[("g", b, "h2h", "HOME")] for b in ("A", "B", "C", "soft")]
    disp = detect_dispersion(home, min_books=3)
    assert disp.has_read and disp.outlier_book == "soft"
    assert disp.outlier_offset < 0                        # soft book below consensus
    assert disp.is_soft_outlier


def test_dispersion_fails_closed_below_min_books():
    now = 1_000_000.0
    commence = now + HOUR
    snaps = [(now - HOUR, _event("g", commence,
                                 {"A": {"h2h": (-130, 110)}, "B": {"h2h": (-132, 112)}}))]
    series = movement_series(snaps)
    home = [series[("g", b, "h2h", "HOME")] for b in ("A", "B")]
    assert not detect_dispersion(home, min_books=3).has_read


def test_totals_movement_tracks_the_point_not_price():
    now = 1_000_000.0
    commence = now + HOUR
    snaps = [
        (now - 3 * HOUR, _event("g", commence, {"dk": {"totals": (-110, -110, 9.0)}})),
        (now - 1 * HOUR, _event("g", commence, {"dk": {"totals": (-110, -110, 8.5)}})),
    ]
    series = movement_series(snaps)
    over = series[("g", "dk", "totals", "Over")]
    assert over.quantity == "point"
    assert over.opener() == 9.0 and over.current() == 8.5
    assert over.total_move() == -0.5                     # line dropped half a run
