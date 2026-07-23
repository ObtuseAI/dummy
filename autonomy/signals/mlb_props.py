"""MLB player-prop challenger signal (Wave-79).

Fills the one genuine model gap the board exposed: every MLB player prop
(home runs, hits, total bases, pitcher strikeouts) was a 100% market echo
because no model priced it. This signal hydrates the same StatsAPI matchup
context the game simulator uses, matches the prop's player to the confirmed
lineup (batter) or the announced probable starter (pitcher), and prices the
over/under analytically via ``autonomy.sports.mlb_props``.

Fail-closed and challenger-only:
  * Batter props require the confirmed lineup (for the real plate-appearance
    slot) -- they abstain until lineups post, a few hours before first pitch.
  * Pitcher strikeouts price off the probable starter and, when known, the
    opposing lineup; they can price a day ahead.
  * Manager-/context-dependent stats (outs, RBIs, H+R+RBI, stolen bases) are
    not modeled and abstain -- the board honestly shows "no model" for them.

The number never moves the traded price on its own: like every challenger it
surfaces as the independent model view (Wave-78) and must earn promotion on
settled contested evidence before it can trade.
"""
from __future__ import annotations

import re
from typing import Any

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.sports.espn import canonical_team
from autonomy.sports.mlb_props import (
    BATTER_STATS,
    PA_BY_SLOT,
    PITCHER_STATS,
    SUPPORTED_STATS,
    batter_prop_over_probability,
    pitcher_prop_over_probability,
)
from autonomy.sports.statsapi import StatsApiClient
from autonomy.sports_markets import classify, spec_for


def _player_token_identity(ticker: str) -> tuple[str, str, str] | None:
    """(team, first_initial, SURNAME) from a prop token ``TEAM+INITIAL+SURNAME+num``.

    e.g. ``KXMLBHR-26JUL242010COLMIL-MILCYELICH44-2`` -> ("MIL", "C", "YELICH").
    """
    parts = str(ticker).upper().split("-")
    if len(parts) < 3:
        return None
    token = parts[2]
    # Longest team prefix that leaves a parseable initial+surname+number tail.
    from autonomy.signals.sports_intelligence import _MLB_TEAMS

    for team in sorted(_MLB_TEAMS, key=len, reverse=True):
        if not token.startswith(team):
            continue
        tail = token[len(team):]
        m = re.fullmatch(r"([A-Z])([A-Z]{2,})(\d+)?", tail)
        if m:
            return canonical_team("mlb", team), m.group(1), m.group(2)
    return None


def _name_matches(name: str | None, first_initial: str, surname: str) -> bool:
    if not name:
        return False
    parts = str(name).upper().replace("-", " ").split()
    if not parts:
        return False
    # Surname can be multi-word ("DE LA CRUZ"); match the token as a suffix.
    joined = "".join(parts)
    return parts[0][:1] == first_initial and joined.endswith(surname)


class MlbPlayerPropSignal:
    name = "mlb_player_prop"

    def __init__(self, statsapi: StatsApiClient | None = None) -> None:
        self.statsapi = statsapi or StatsApiClient()
        self._ctx_cache: dict[tuple[str, str, str], Any] = {}

    def on_cycle_start(self, as_of: str | None = None) -> None:
        try:
            self.statsapi.clear_schedule_cache()
        except Exception:  # noqa: BLE001
            pass
        self._ctx_cache.clear()

    def _spec(self, market: MarketView):
        try:
            spec = spec_for(market.ticker)
        except Exception:  # noqa: BLE001
            return None
        if not (spec and spec.is_prop and spec.stat):
            return None
        return spec if spec.league == "mlb" and str(spec.stat) in SUPPORTED_STATS else None

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and self._spec(market) is not None

    def _teams(self, ticker: str) -> tuple[str, str] | None:
        from autonomy.signals.sports_intelligence import (
            _date_and_remainder,
            _split_mlb_teams,
            _strip_start_time,
        )

        parts = str(ticker).upper().split("-")
        if len(parts) < 2:
            return None
        dated = _date_and_remainder(parts[1])
        if dated is None:
            return None
        yyyymmdd = dated[0]
        # StatsAPI's schedule endpoint wants an ISO calendar date (YYYY-MM-DD).
        date_iso = f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
        return _split_mlb_teams(_strip_start_time(dated[1])), date_iso  # type: ignore[return-value]

    def _context(self, date_iso: str, a: str, b: str):
        key = (date_iso, a, b)
        if key in self._ctx_cache:
            return self._ctx_cache[key]
        from datetime import datetime, timezone

        captured_at = datetime.now(timezone.utc).isoformat()
        ctx = None
        try:
            # We do not know home/away order from the ticker; try both.
            for home, away in ((a, b), (b, a)):
                ctx = self.statsapi.projected_context_for_matchup(
                    date_iso, home=home, away=away, captured_at=captured_at)
                if ctx is not None:
                    break
            if ctx is not None:
                ctx = self.statsapi.confirm_lineups(ctx, captured_at=captured_at)
                ctx = self.statsapi.hydrate_batter_rates(ctx)
        except Exception:  # noqa: BLE001
            ctx = None
        self._ctx_cache[key] = ctx
        return ctx

    def generate(self, market: MarketView) -> Signal | None:
        spec = self._spec(market)
        if spec is None:
            return None
        stat = str(spec.stat)
        parsed = classify(market)
        line = getattr(parsed, "threshold", None) if parsed is not None else None
        if line is None:
            return None
        identity = _player_token_identity(market.ticker)
        teams = self._teams(market.ticker)
        if identity is None or teams is None:
            return None
        (team_pair, date_iso) = teams
        if team_pair is None:
            return None
        player_team, first_initial, surname = identity
        ctx = self._context(date_iso, team_pair[0], team_pair[1])
        if ctx is None:
            return None
        home = canonical_team("mlb", ctx.home)
        away = canonical_team("mlb", ctx.away)
        if player_team not in (home, away):
            return None
        park_hr = ctx.park_hr_factor if ctx.park_hr_factor is not None else 1.0
        player_is_home = player_team == home

        probability: float | None = None
        detail = ""
        if stat in BATTER_STATS:
            lineup = ctx.home_lineup if player_is_home else ctx.away_lineup
            opposing_pitcher = ctx.away_pitcher if player_is_home else ctx.home_pitcher
            slot = next(
                (s for s in lineup if _name_matches(s.name, first_initial, surname)), None)
            if slot is None:
                return None  # lineup not posted / no match -> fail-closed
            batter = ctx.batter_rates.get(slot.player_id)
            if batter is None:
                return None
            projected_pa = PA_BY_SLOT.get(slot.batting_order, 4.2)
            probability = batter_prop_over_probability(
                stat, float(line), batter, opposing_pitcher,
                park_hr_factor=park_hr, projected_pa=projected_pa)
            detail = f"{surname.title()} {stat} over {line:g} (slot {slot.batting_order})"
        elif stat in PITCHER_STATS:
            pitcher = ctx.home_pitcher if player_is_home else ctx.away_pitcher
            if pitcher is None or not _name_matches(pitcher.name, first_initial, surname):
                return None
            opp_lineup = ctx.away_lineup if player_is_home else ctx.home_lineup
            opp_batters = [
                ctx.batter_rates[s.player_id]
                for s in opp_lineup if s.player_id in ctx.batter_rates
            ] or None
            probability = pitcher_prop_over_probability(
                stat, float(line), pitcher, opp_batters)
            detail = f"{surname.title()} {stat} over {line:g}"

        if probability is None:
            return None
        p_yes = min(0.97, max(0.03, probability))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            # Player props are high-variance and the projected PA/BF counts are
            # approximations; keep the error bar wide until settlement earns it.
            uncertainty=min(0.5, max(0.16, 0.30 - 0.16 * abs(p_yes - 0.5))),
            rationale=f"MLB prop {detail}: {ctx.away}@{ctx.home}",
            features={
                "challenger_only": True,
                "promotion_eligible": True,
                "point_in_time": True,
                "public_read_only": True,
                "sport": "mlb",
                "market_type": "prop",
                "stat": stat,
                "line": float(line),
                "player_team": player_team,
            },
        )
