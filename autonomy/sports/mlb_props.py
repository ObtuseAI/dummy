"""MLB player-prop distributions (Wave-79).

Every MLB player-prop market (home runs, hits, total bases, strikeouts, ...) was
a 100% market echo: no independent model priced it, so the fused forecast fell
back to the market prior and the board showed nothing to compare against. This
module supplies the missing model. It reuses the plate-appearance engine that
already powers the game simulator (``plate_appearance_distribution``) and rolls
a single PA up into a full-game stat distribution analytically -- no simulation
loop -- then reads off ``P(stat >= line)`` for both sides of the contract.

Design notes / honesty:
  * BATTER props (home_runs, hits, total_bases) need the confirmed lineup so the
    batter's projected plate-appearance count is real. Lineups post a few hours
    before first pitch, so these price day-of and abstain earlier -- fail-closed.
  * PITCHER strikeouts price off the announced probable pitcher and (when known)
    the opposing lineup, so they can price a day ahead.
  * Manager-/context-dependent stats (outs recorded, RBIs, hits+runs+RBIs,
    stolen bases) are DELIBERATELY not modeled here: outs hinge on the hook
    decision, RBIs on lineup sequencing/baserunners. Pretending otherwise would
    be a worse-than-market guess. They return ``None`` (abstain) and the board
    honestly shows "no model" until a purpose-built model exists.

Pure, deterministic, dependency-free. Challenger-only upstream: these numbers
surface as the independent "model view" (Wave-78) and never move the traded
number until the promotion ladder earns it on settlements.
"""
from __future__ import annotations

import math
from typing import Any

from autonomy.sports.mlb_pa_sim import plate_appearance_distribution

# Plate appearances per game by batting-order slot (leadoff bats most). League
# averages; a real confirmed slot is required before any batter prop prices, so
# this only interpolates the count, never invents the identity.
PA_BY_SLOT: dict[int, float] = {
    1: 4.65, 2: 4.55, 3: 4.45, 4: 4.35, 5: 4.25,
    6: 4.15, 7: 4.05, 8: 3.95, 9: 3.85,
}
DEFAULT_PA = 4.2
# A modern starter faces roughly this many batters before the hook; used only
# for the pitcher strikeout line when a start length is not otherwise known.
DEFAULT_STARTER_BF = 22.0

# Stats this module can price. Everything else abstains (see module docstring).
BATTER_STATS = frozenset({"home_runs", "hits", "total_bases"})
PITCHER_STATS = frozenset({"strikeouts"})
SUPPORTED_STATS = BATTER_STATS | PITCHER_STATS


def _over_threshold(line: float) -> int:
    """The integer count that clears an over line. A 1.5 line needs 2; a whole
    number 2.0 line ("over 2") needs 3."""
    if abs(line - round(line)) < 1e-9:
        return int(round(line)) + 1
    return math.floor(line) + 1


def _binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), exact, clamped to [0, 1]."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    p = min(1.0, max(0.0, p))
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
    return min(1.0, max(0.0, total))


def _binomial_sf_fractional(k: int, n: float, p: float) -> float:
    """P(X >= k) when the trial count is fractional: mix floor(n) and ceil(n) by
    the fractional part, so a 4.35-PA projection is 0.65*4-PA + 0.35*5-PA."""
    lo = int(math.floor(n))
    frac = n - lo
    if frac < 1e-9:
        return _binomial_sf(k, lo, p)
    return (1.0 - frac) * _binomial_sf(k, lo, p) + frac * _binomial_sf(k, lo + 1, p)


def _tb_per_pa(dist: dict[str, float]) -> dict[int, float]:
    """Total-bases outcome for one PA: 0 (K/BB/HBP/out), 1, 2, 3, or 4."""
    zero = dist.get("k", 0.0) + dist.get("bb", 0.0) + dist.get("hbp", 0.0) + dist.get("out", 0.0)
    return {
        0: zero,
        1: dist.get("single", 0.0),
        2: dist.get("double", 0.0),
        3: dist.get("triple", 0.0),
        4: dist.get("hr", 0.0),
    }


def _convolve(a: dict[int, float], b: dict[int, float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for i, pi in a.items():
        if pi <= 0.0:
            continue
        for j, pj in b.items():
            if pj <= 0.0:
                continue
            out[i + j] = out.get(i + j, 0.0) + pi * pj
    return out


def _sum_distribution(per_pa: dict[int, float], n: int) -> dict[int, float]:
    """Distribution of the sum of ``n`` i.i.d. per-PA outcomes (exact convolution)."""
    total: dict[int, float] = {0: 1.0}
    for _ in range(n):
        total = _convolve(total, per_pa)
    return total


def _sf_from_distribution(dist: dict[int, float], k: int) -> float:
    return min(1.0, max(0.0, sum(p for value, p in dist.items() if value >= k)))


def _hit_prob_per_pa(dist: dict[str, float]) -> float:
    return (dist.get("single", 0.0) + dist.get("double", 0.0)
            + dist.get("triple", 0.0) + dist.get("hr", 0.0))


def batter_prop_over_probability(
    stat: str,
    line: float,
    batter: Any,
    opposing_pitcher: Any,
    *,
    park_hr_factor: float = 1.0,
    projected_pa: float = DEFAULT_PA,
) -> float | None:
    """``P(batter's full-game <stat> > line)``. ``None`` for an unpriceable stat."""
    if stat not in BATTER_STATS or batter is None:
        return None
    dist = plate_appearance_distribution(
        batter, opposing_pitcher, park_hr_factor=park_hr_factor)
    need = _over_threshold(line)
    if stat == "home_runs":
        return _binomial_sf_fractional(need, projected_pa, dist.get("hr", 0.0))
    if stat == "hits":
        return _binomial_sf_fractional(need, projected_pa, _hit_prob_per_pa(dist))
    if stat == "total_bases":
        per_pa = _tb_per_pa(dist)
        lo = int(math.floor(projected_pa))
        frac = projected_pa - lo
        sf_lo = _sf_from_distribution(_sum_distribution(per_pa, lo), need)
        if frac < 1e-9:
            return sf_lo
        sf_hi = _sf_from_distribution(_sum_distribution(per_pa, lo + 1), need)
        return (1.0 - frac) * sf_lo + frac * sf_hi
    return None


def pitcher_prop_over_probability(
    stat: str,
    line: float,
    pitcher: Any,
    opposing_batters: list[Any] | None = None,
    *,
    projected_bf: float = DEFAULT_STARTER_BF,
) -> float | None:
    """``P(pitcher's <stat> > line)``. Only strikeouts are modeled; the per-batter
    K probability is averaged over the opposing lineup when known, else taken
    against a league-average batter."""
    if stat not in PITCHER_STATS or pitcher is None:
        return None
    if stat == "strikeouts":
        if opposing_batters:
            ks = [
                plate_appearance_distribution(b, pitcher).get("k", 0.0)
                for b in opposing_batters
            ]
            k_per_batter = sum(ks) / len(ks) if ks else None
        else:
            k_per_batter = plate_appearance_distribution(None, pitcher).get("k", 0.0)
        if k_per_batter is None:
            return None
        return _binomial_sf_fractional(_over_threshold(line), projected_bf, k_per_batter)
    return None
