"""Wave-30: public-lean model + reverse-line-movement synthesis + the
market_pressure challenger signal."""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone

from autonomy.market_pressure.public_lean import estimate_public_lean, is_popular
from autonomy.market_pressure.pressure import synthesize_pressure
from autonomy.ontology import MarketView, Vertical

HOUR = 3600.0


# ---- public-lean model -----------------------------------------------------

def test_public_leans_to_favorites_overs_and_brands():
    fav = estimate_public_lean(league="mlb", devig_prob=0.68).lean
    dog = estimate_public_lean(league="mlb", devig_prob=0.32).lean
    assert fav > 0.5 > dog                                   # public on the chalk
    over = estimate_public_lean(league="mlb", devig_prob=0.5, is_over=True).lean
    under = estimate_public_lean(league="mlb", devig_prob=0.5, is_over=False).lean
    assert over > under                                      # public loves the over
    brand = estimate_public_lean(league="mlb", devig_prob=0.5, team_name="New York Yankees").lean
    plain = estimate_public_lean(league="mlb", devig_prob=0.5, team_name="Miami Marlins").lean
    assert brand > plain and is_popular("mlb", "New York Yankees")


# ---- synthesis -------------------------------------------------------------

def _pub(lean):
    from autonomy.market_pressure.public_lean import PublicLeanRead
    return PublicLeanRead(lean=lean, drivers=())


def _steam(direction, magnitude, is_steam=True):
    from autonomy.market_pressure.steam import SteamRead
    return SteamRead(is_steam=is_steam, direction=direction, magnitude=magnitude,
                     n_books_moved=5, n_books_total=8, originator="pinnacle")


def _disp():
    from autonomy.market_pressure.dispersion import DispersionRead
    return DispersionRead(True, 0.6, 0.02, 8, None, None, False)


def test_reverse_line_movement_flags_sharp_dog_and_trap():
    # Public on the FAVORITE subject (lean .66 vs .40); line moved to the dog
    # opponent (steam -1). That is RLM -> sharp on the dog, trap on the public.
    read = synthesize_pressure(
        subject_side="FAV", opponent_side="DOG", subject_devig=0.62,
        subject_lean=_pub(0.66), opponent_lean=_pub(0.40),
        steam=_steam(-1, -0.05), dispersion=_disp())
    assert read.reverse_line_movement
    assert read.sharp_side == "DOG" and read.public_side == "FAV"
    assert read.trap_flag and read.dog_value_flag
    assert read.prob_adjustment < 0                          # nudge P(FAV) down, toward the dog


def test_public_steam_is_not_reverse_line_movement():
    # Line moved TOWARD the public favorite -> just public steam, no RLM, no trap.
    read = synthesize_pressure(
        subject_side="FAV", opponent_side="DOG", subject_devig=0.62,
        subject_lean=_pub(0.66), opponent_lean=_pub(0.40),
        steam=_steam(+1, +0.05), dispersion=_disp())
    assert not read.reverse_line_movement
    assert not read.trap_flag


def test_no_steam_and_coinflip_crowd_reads_nothing():
    read = synthesize_pressure(
        subject_side="A", opponent_side="B", subject_devig=0.5,
        subject_lean=_pub(0.50), opponent_lean=_pub(0.50),
        steam=_steam(0, 0.0, is_steam=False), dispersion=_disp())
    assert not read.has_read


# ---- signal integration ----------------------------------------------------

class _StubGame:
    def __init__(self):
        self.home, self.away = "HOME", "AWAY"
        self.home_name, self.away_name = "Home Team", "Away Team"
        self.status = "pre"


class _StubEspn:
    def clear_cache(self):
        pass

    def find_matchup(self, league, subject, opponent, dates=None):
        return _StubGame()


def _event(event_id, commence_ts, home_ml_by_book):
    """home_ml_by_book: {book: (home_price, away_price)} -> Odds API event."""
    commence = datetime.fromtimestamp(commence_ts, timezone.utc).isoformat().replace("+00:00", "Z")
    books = [{"key": bk, "markets": [{"key": "h2h", "outcomes": [
        {"name": "Home Team", "price": hp}, {"name": "Away Team", "price": ap}]}]}
        for bk, (hp, ap) in home_ml_by_book.items()]
    return {"id": event_id, "home_team": "Home Team", "away_team": "Away Team",
            "commence_time": commence, "sport_key": "baseball_mlb", "bookmakers": books}


def test_market_pressure_signal_nudges_toward_the_sharp_dog(tmp_path, monkeypatch):
    import autonomy.signals.market_pressure as mp
    import autonomy.odds_providers as op

    now = datetime.now(timezone.utc).timestamp()
    commence = now + 2 * HOUR
    # Home is a strong favorite (~-200 -> devig ~0.64) and STAYS one, but across
    # four books the home line drops (money to the away dog): the public is on
    # the favorite while sharp money buys the dog = reverse line movement.
    fav = {b: (-200, 170) for b in ("dk", "fd", "mgm", "pin")}
    moved = {b: (-170, 150) for b in ("dk", "fd", "mgm", "pin")}
    shard = tmp_path / "odds_2026-07.jsonl.gz"
    rows = [
        {"ts": now - 6 * HOUR, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [_event("g1", commence, fav)]},
        {"ts": now - 1 * HOUR, "key": "odds|baseball_mlb|h2h,totals,spreads|us",
         "payload": [_event("g1", commence, moved)]},
    ]
    with gzip.open(shard, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    monkeypatch.setattr(mp, "parse_game_ticker", lambda t: {
        "league": "mlb", "subject": "HOME", "opponent": "AWAY",
        "date_yyyymmdd": "20260718"})
    monkeypatch.setattr(op, "_match_event", lambda events, home, away: events[0] if events else None)

    signal = mp.MarketPressureSignal(espn=_StubEspn(), archive_dir=str(tmp_path))
    signal.on_cycle_start()
    market = MarketView(
        ticker="KXMLBGAME-26JUL18HOMEAWAY-HOME", title="Home to win?",
        vertical=Vertical.SPORTS, status="active", close_time="2026-07-18T22:00:00Z",
        yes_bid=55, yes_ask=57, no_bid=43, no_ask=45, volume=10, liquidity=100)
    sig = signal.generate(market)
    assert sig is not None
    assert sig.features["challenger_only"] is True
    assert sig.features["reverse_line_movement"] is True
    assert sig.features["sharp_side"] == "Away Team"
    assert sig.probability_yes < sig.features["baseline_consensus"]   # nudged toward the dog


def test_signal_abstains_without_archive(tmp_path, monkeypatch):
    import autonomy.signals.market_pressure as mp
    monkeypatch.setattr(mp, "parse_game_ticker", lambda t: {
        "league": "mlb", "subject": "HOME", "opponent": "AWAY", "date_yyyymmdd": "20260718"})
    signal = mp.MarketPressureSignal(espn=_StubEspn(), archive_dir=str(tmp_path))
    signal.on_cycle_start()
    market = MarketView(
        ticker="KXMLBGAME-26JUL18HOMEAWAY-HOME", title="Home to win?",
        vertical=Vertical.SPORTS, status="active", close_time="2026-07-18T22:00:00Z",
        yes_bid=55, yes_ask=57, no_bid=43, no_ask=45, volume=10, liquidity=100)
    assert signal.generate(market) is None
