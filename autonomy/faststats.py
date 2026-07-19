"""Fast float statistics — drop-in for the hot per-cycle paths.

Python's ``statistics`` module computes ``mean``/``variance``/``stdev`` with exact
``fractions.Fraction`` arithmetic. That is correct and type-preserving, but on a
list of floats it is 10-100x slower than a plain float pass — and the crypto TA
sources call it hundreds of times per market, thousands of markets per cycle
(profiled: ``statistics._ss`` + ``fractions.*`` dominated the per-market self
time). These helpers give the same results within float precision and honor the
same contract (``StatisticsError`` on too-few points) so a module can switch by
aliasing ``from autonomy import faststats as statistics``.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from statistics import StatisticsError

__all__ = ["fmean", "mean", "median", "pstdev", "stdev", "pvariance", "variance"]


def _floats(data: Iterable[float]) -> list[float]:
    return [x if type(x) is float else float(x) for x in data]


def fmean(data: Iterable[float]) -> float:
    xs = _floats(data)
    n = len(xs)
    if n < 1:
        raise StatisticsError("fmean requires at least one data point")
    return math.fsum(xs) / n


# statistics.mean is exact/type-preserving; on the float hot paths fmean matches.
mean = fmean


def median(data: Iterable[float]) -> float:
    xs = sorted(_floats(data))
    n = len(xs)
    if n < 1:
        raise StatisticsError("no median for empty data")
    mid = n // 2
    if n % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2.0


def pvariance(data: Iterable[float], mu: float | None = None) -> float:
    xs = _floats(data)
    n = len(xs)
    if n < 1:
        raise StatisticsError("pvariance requires at least one data point")
    m = fmean(xs) if mu is None else float(mu)
    return math.fsum((x - m) ** 2 for x in xs) / n


def variance(data: Iterable[float], xbar: float | None = None) -> float:
    xs = _floats(data)
    n = len(xs)
    if n < 2:
        raise StatisticsError("variance requires at least two data points")
    m = fmean(xs) if xbar is None else float(xbar)
    return math.fsum((x - m) ** 2 for x in xs) / (n - 1)


def pstdev(data: Iterable[float], mu: float | None = None) -> float:
    return math.sqrt(pvariance(data, mu))


def stdev(data: Iterable[float], xbar: float | None = None) -> float:
    return math.sqrt(variance(data, xbar))
