"""Wave-32: scraped betting splits -- weighted fusion, provider parsing, the
governed service, and splits-aware synthesis."""
from __future__ import annotations

from autonomy.market_pressure.splits.model import SplitsRead, combine_splits
from autonomy.market_pressure.splits.providers import (
    ActionNetworkProvider,
    CoversProvider,
    VsinProvider,
    normalize_team,
)
from autonomy.market_pressure.splits.service import SplitsService
from autonomy.market_pressure.pressure import synthesize_pressure
from autonomy.market_pressure.public_lean import PublicLeanRead
from autonomy.market_pressure.dispersion import DispersionRead
from autonomy.market_pressure.steam import SteamRead

NOW = 1_000_000.0


# ---- fusion ----------------------------------------------------------------

def test_weighted_fusion_prefers_money_sources_and_computes_the_gap():
    reads = [
        SplitsRead("action_network", "Home", "Away", 0.62, 0.38, 0.41, 0.59, NOW),
        SplitsRead("covers", "Home", "Away", 0.58, 0.42, None, None, NOW),
    ]
    fused = combine_splits(reads, now=NOW)
    assert fused.has_read
    assert 0.60 < fused.home_ticket_pct < 0.62          # AN (1.0) outweighs covers (.55)
    assert fused.home_money_pct == 0.41                 # only AN carries money
    assert fused.home_money_ticket_gap < -0.15          # money on the away side
    assert fused.sharp_side("Home", "Away") == "Away"   # money leads tickets on away
    assert fused.public_side("Home", "Away") == "Home"  # tickets on home
    assert "action_network" in fused.sources and "covers" in fused.sources


def test_fusion_normalizes_percent_or_fraction_and_drops_stale():
    fresh = SplitsRead("vsin", "H", "A", 55, 45, 48, 52, NOW)          # percents
    stale = SplitsRead("covers", "H", "A", 0.9, 0.1, None, None, NOW - 5 * 3600)
    fused = combine_splits([fresh, stale], now=NOW)
    assert abs(fused.home_ticket_pct - 0.55) < 1e-6     # normalized; stale dropped
    assert fused.sources == ("vsin",)


def test_fusion_empty_without_tickets():
    assert not combine_splits([], now=NOW).has_read
    only_money = SplitsRead("x", "H", "A", None, None, 0.6, 0.4, NOW)
    assert not combine_splits([only_money], now=NOW).has_read


# ---- providers -------------------------------------------------------------

def test_action_network_parse():
    # Confirmed live shape (2026-07-23): per-book markets.event.moneyline is a
    # two-entry list tagged side/team_id with bet_info.tickets/money.percent;
    # teams resolve through home_team_id/away_team_id.
    payload = {"games": [{
        "home_team_id": 1, "away_team_id": 2,
        "teams": [
            {"id": 1, "full_name": "Boston Red Sox"},
            {"id": 2, "full_name": "Tampa Bay Rays"},
        ],
        "markets": {"15": {"event": {"moneyline": [
            {"side": "home", "team_id": 1,
             "bet_info": {"tickets": {"percent": 62}, "money": {"percent": 41}}},
            {"side": "away", "team_id": 2,
             "bet_info": {"tickets": {"percent": 38}, "money": {"percent": 59}}},
        ]}}},
    }]}
    reads = ActionNetworkProvider().parse(payload, now=NOW)
    assert len(reads) == 1
    r = reads[0]
    assert r.home_team == "Boston Red Sox" and r.home_ticket_pct == 0.62
    assert r.home_money_pct == 0.41 and r.has_money()


def test_vsin_parse_and_covers_html_parse():
    v = VsinProvider().parse({"data": [{"home_team": "Yankees", "away_team": "Dodgers",
        "home_bets_pct": 55, "away_bets_pct": 45,
        "home_handle_pct": 48, "away_handle_pct": 52}]}, now=NOW)
    assert v[0].home_money_pct == 0.48
    # Confirmed live shape (2026-07-23): Covers serves a legacy HTML consensus
    # grid (league | away | home | date | time | away% | home% | ...).
    html = (
        "<table><tr><th>Matchup</th></tr>"
        "<tr><td><div>MLB</div><div>Min</div><div>Cle</div></td>"
        "<td>Thu. Jul 23<span>6:40 pm ET</span></td>"
        "<td>42%<span>58%</span></td><td>+120 -140</td></tr></table>"
    )
    c = CoversProvider()._parse_html(html, now=NOW)
    assert len(c) == 1
    assert c[0].away_team == "Min" and c[0].home_team == "Cle"
    assert c[0].home_ticket_pct == 0.58 and c[0].away_ticket_pct == 0.42
    assert not c[0].has_money()


def test_provider_parse_is_fail_closed_on_junk():
    assert ActionNetworkProvider().parse({"nope": 1}, now=NOW) == []
    assert VsinProvider().parse("garbage", now=NOW) == []


def test_normalize_disambiguates_sox():
    assert normalize_team("Boston Red Sox") == "redsox"
    assert normalize_team("Chicago White Sox") == "whitesox"
    assert normalize_team("New York Yankees") == "yankees"


# ---- service ---------------------------------------------------------------

class _StubProvider:
    def __init__(self, name, reads):
        self.name = name
        self._reads = reads

    def fetch(self, league, fetcher, *, now):
        return self._reads


def test_service_inert_until_armed(tmp_path):
    prov = _StubProvider("action_network",
                         [SplitsRead("action_network", "H", "A", 0.6, 0.4, 0.5, 0.5, NOW)])
    svc = SplitsService(providers=[prov], enabled=False, now_fn=lambda: NOW,
                        cache_dir=tmp_path / "c", archive_dir=tmp_path / "a")
    assert svc.refresh(["mlb"]) == 0
    assert not svc.splits_for("H", "A").has_read


def test_service_armed_indexes_and_orients(tmp_path):
    # One source lists the game home/away the OTHER way round; the service flips
    # it to the caller's orientation before fusing.
    # Source lists Rays as home; the caller's home is the Red Sox.
    prov = _StubProvider("action_network", [
        SplitsRead("action_network", "Tampa Bay Rays", "Boston Red Sox",
                   0.35, 0.65, 0.30, 0.70, NOW)])
    svc = SplitsService(providers=[prov], enabled=True, now_fn=lambda: NOW,
                        cache_dir=tmp_path / "c", archive_dir=tmp_path / "a")
    assert svc.refresh(["mlb"]) == 1
    fused = svc.splits_for("Boston Red Sox", "Tampa Bay Rays")
    assert fused.has_read
    assert abs(fused.home_ticket_pct - 0.65) < 1e-6     # flipped to caller's home (Red Sox)


# ---- splits-aware synthesis ------------------------------------------------

def _lean(v):
    return PublicLeanRead(lean=v, drivers=())


def _flat_disp():
    return DispersionRead(True, 0.55, 0.02, 8, None, None, False)


def _no_steam():
    return SteamRead(False, 0, 0.0, 0, 8, None)


def test_splits_measured_public_and_money_divergence_flags_sharp_and_trap():
    # Measured: public heavily on home (ticket 63), money on the away dog.
    fused = combine_splits(
        [SplitsRead("action_network", "Home", "Away", 0.63, 0.37, 0.42, 0.58, NOW)], now=NOW)
    read = synthesize_pressure(
        subject_side="Home", opponent_side="Away", subject_devig=0.58,
        subject_lean=_lean(0.5), opponent_lean=_lean(0.5),  # estimate ignored when measured
        steam=_no_steam(), dispersion=_flat_disp(),
        splits=fused, subject_is_home=True)
    assert read.public_is_measured and read.public_side == "Home"
    assert read.money_sharp_side == "Away" and read.sharp_side == "Away"
    assert read.trap_flag                                    # flat line + heavy real public = trap
    assert read.dog_value_flag                               # sharp side is the dog
    assert read.prob_adjustment < 0                          # nudge P(Home) down


def test_line_and_money_agreement_boosts_confidence():
    fused = combine_splits(
        [SplitsRead("action_network", "Home", "Away", 0.63, 0.37, 0.42, 0.58, NOW)], now=NOW)
    steam_to_away = SteamRead(True, -1, -0.05, 5, 8, "pinnacle")
    agree = synthesize_pressure(
        subject_side="Home", opponent_side="Away", subject_devig=0.58,
        subject_lean=_lean(0.5), opponent_lean=_lean(0.5),
        steam=steam_to_away, dispersion=_flat_disp(), splits=fused, subject_is_home=True)
    money_only = synthesize_pressure(
        subject_side="Home", opponent_side="Away", subject_devig=0.58,
        subject_lean=_lean(0.5), opponent_lean=_lean(0.5),
        steam=_no_steam(), dispersion=_flat_disp(), splits=fused, subject_is_home=True)
    assert agree.signals_agree is True
    assert agree.confidence > money_only.confidence         # both tells agree -> more conviction
