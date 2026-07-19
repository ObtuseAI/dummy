"""Phase 2 analytic: Glicko-2 team ratings, point-in-time from the history lake.

Glicko-2 (Glickman 2013) improves on Elo by tracking, per team, not just a
rating but a rating *deviation* (RD, how sure we are) and a *volatility* (how
erratic recent form is). A team idle for weeks has its RD inflate, so an
opponent-strength estimate degrades gracefully rather than pretending stale
certainty -- exactly the discipline this codebase wants.

Pure Python (no numpy), house style. The engine is a faithful implementation of
the paper (verified against Glickman's worked example in the tests).
:class:`LakeGlickoRatings` warms ratings from :class:`SportsHistoryStore`
strictly point-in-time (only games that finished before the as-of instant) and
answers a matchup win probability -- the seed for a challenger rating source.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.sports.history_store import SportsHistoryStore

_SCALE = 173.7178          # Glicko-2 <-> Glicko rating-scale factor
_BASE_R = 1500.0
_BASE_RD = 350.0
_BASE_VOL = 0.06


class Glicko2:
    """The rating-period update engine (stateless; operate on plain numbers)."""

    def __init__(self, tau: float = 0.5, epsilon: float = 1e-6) -> None:
        self.tau = tau            # system constant: constrains volatility change
        self.epsilon = epsilon

    @staticmethod
    def _g(phi: float) -> float:
        return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))

    @staticmethod
    def _e(mu: float, mu_j: float, phi_j: float) -> float:
        return 1.0 / (1.0 + math.exp(-Glicko2._g(phi_j) * (mu - mu_j)))

    def expected_score(self, r: float, rd: float, r_opp: float, rd_opp: float) -> float:
        """Win probability of ``r`` over ``r_opp`` given both deviations."""
        mu, mu_o = (r - _BASE_R) / _SCALE, (r_opp - _BASE_R) / _SCALE
        phi_o = rd_opp / _SCALE
        return self._e(mu, mu_o, phi_o)

    def update(
        self, r: float, rd: float, vol: float,
        opponents: list[tuple[float, float, float]],
    ) -> tuple[float, float, float]:
        """One rating period. ``opponents`` = [(r_j, rd_j, score)], score in 0..1.

        With no games the rating holds and only RD inflates by the volatility.
        """
        mu, phi = (r - _BASE_R) / _SCALE, rd / _SCALE
        if not opponents:
            phi_star = math.sqrt(phi * phi + vol * vol)
            return r, min(_BASE_RD, phi_star * _SCALE), vol

        v_inv = 0.0
        delta_sum = 0.0
        for r_j, rd_j, score in opponents:
            mu_j, phi_j = (r_j - _BASE_R) / _SCALE, rd_j / _SCALE
            g_j = self._g(phi_j)
            e_j = 1.0 / (1.0 + math.exp(-g_j * (mu - mu_j)))
            v_inv += g_j * g_j * e_j * (1.0 - e_j)
            delta_sum += g_j * (score - e_j)
        v = 1.0 / v_inv
        delta = v * delta_sum

        new_vol = self._new_volatility(phi, v, delta, vol)
        phi_star = math.sqrt(phi * phi + new_vol * new_vol)
        new_phi = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
        new_mu = mu + new_phi * new_phi * delta_sum

        return new_mu * _SCALE + _BASE_R, new_phi * _SCALE, new_vol

    def _new_volatility(self, phi: float, v: float, delta: float, vol: float) -> float:
        # Illinois algorithm for the volatility equation (paper step 5).
        a = math.log(vol * vol)
        tau2 = self.tau * self.tau
        delta2, phi2 = delta * delta, phi * phi

        def f(x: float) -> float:
            ex = math.exp(x)
            num = ex * (delta2 - phi2 - v - ex)
            den = 2.0 * (phi2 + v + ex) ** 2
            return num / den - (x - a) / tau2

        aa = a
        if delta2 > phi2 + v:
            bb = math.log(delta2 - phi2 - v)
        else:
            k = 1
            while f(a - k * self.tau) < 0:
                k += 1
            bb = a - k * self.tau
        fa, fb = f(aa), f(bb)
        while abs(bb - aa) > self.epsilon:
            cc = aa + (aa - bb) * fa / (fb - fa)
            fc = f(cc)
            if fc * fb <= 0:
                aa, fa = bb, fb
            else:
                fa /= 2.0
            bb, fb = cc, fc
        return math.exp(aa / 2.0)


class LakeGlickoRatings:
    """Point-in-time Glicko-2 team ratings warmed from the history lake."""

    def __init__(self, store: SportsHistoryStore, league: str, *, tau: float = 0.5) -> None:
        self.store = store
        self.league = league
        self.engine = Glicko2(tau=tau)
        self._r: dict[str, float] = {}
        self._rd: dict[str, float] = {}
        self._vol: dict[str, float] = {}

    def _state(self, team: str) -> tuple[float, float, float]:
        return (self._r.get(team, _BASE_R), self._rd.get(team, _BASE_RD),
                self._vol.get(team, _BASE_VOL))

    def warm(self, as_of: str, *, period_key: str = "day") -> "LakeGlickoRatings":
        """Replay all completed games before ``as_of`` in chronological rating
        periods (default: one period per calendar day)."""
        games = self.store.games_before(as_of, league=self.league)
        for period in self.group_periods(games, period_key):
            self.apply_period(period)
        return self

    def apply_period(self, period: list[dict[str, Any]]) -> None:
        """Update every team that played this rating period, using each team's
        opponents' ratings *frozen at the start of the period* (so intra-period
        games don't leak into one another)."""
        pending: dict[str, list[tuple[float, float, float]]] = {}
        for game in period:
            home, away = game.get("home"), game.get("away")
            hs, as_ = game.get("home_score"), game.get("away_score")
            if not home or not away or hs is None or as_ is None:
                continue
            home_score = 1.0 if hs > as_ else 0.0 if hs < as_ else 0.5
            r_h, rd_h, _ = self._state(home)
            r_a, rd_a, _ = self._state(away)
            pending.setdefault(home, []).append((r_a, rd_a, home_score))
            pending.setdefault(away, []).append((r_h, rd_h, 1.0 - home_score))
        for team, opps in pending.items():
            r, rd, vol = self._state(team)
            self._r[team], self._rd[team], self._vol[team] = self.engine.update(r, rd, vol, opps)

    @staticmethod
    def group_periods(games: list[dict[str, Any]], period_key: str = "day") -> list[list[dict[str, Any]]]:
        """Chronological rating periods (default one per calendar day)."""
        games = sorted(games, key=lambda g: g["start_time"])
        periods: list[list[dict[str, Any]]] = []
        current_key = None
        for game in games:
            key = game["start_time"][:10] if period_key == "day" else game["start_time"][:7]
            if key != current_key:
                periods.append([])
                current_key = key
            periods[-1].append(game)
        return periods

    def rating(self, team: str) -> float:
        return self._r.get(team, _BASE_R)

    def deviation(self, team: str) -> float:
        return self._rd.get(team, _BASE_RD)

    def matchup_prob(self, home: str, away: str, *, home_advantage: float = 40.0) -> float:
        """Home win probability. ``home_advantage`` is a rating-point bump on the
        home side (leagues differ; the seam lets the tuner set it later)."""
        r_h, rd_h, _ = self._state(home)
        r_a, rd_a, _ = self._state(away)
        return self.engine.expected_score(r_h + home_advantage, rd_h, r_a, rd_a)
