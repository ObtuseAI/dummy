"""Wave-43: faststats must match the stdlib statistics it replaces.

The crypto TA sources alias ``from autonomy import faststats as statistics`` to
avoid the Fraction-based hot path. These tests pin that the float results agree
with the stdlib within float precision and honor the same StatisticsError
contract, so the alias is a pure speedup with no behavior change.
"""
from __future__ import annotations

import statistics as std

import pytest

from autonomy import faststats


DATASETS = [
    [1.0, 2.0, 3.0, 4.0, 5.0],
    [0.1, 0.1, 0.1],
    [-3.0, 7.5, 2.25, 9.0, -1.5, 4.0],
    [100000.0, 100001.0, 99999.5, 100000.25],
    [0.0001 * i for i in range(1, 51)],
]


@pytest.mark.parametrize("data", DATASETS)
def test_matches_stdlib(data):
    assert faststats.fmean(data) == pytest.approx(std.fmean(data), rel=1e-12, abs=1e-9)
    assert faststats.mean(data) == pytest.approx(float(std.mean(data)), rel=1e-12, abs=1e-9)
    assert faststats.median(data) == pytest.approx(std.median(data), rel=1e-12, abs=1e-9)
    assert faststats.pstdev(data) == pytest.approx(std.pstdev(data), rel=1e-9, abs=1e-9)
    assert faststats.pvariance(data) == pytest.approx(std.pvariance(data), rel=1e-9, abs=1e-9)
    if len(data) >= 2:
        assert faststats.stdev(data) == pytest.approx(std.stdev(data), rel=1e-9, abs=1e-9)
        assert faststats.variance(data) == pytest.approx(std.variance(data), rel=1e-9, abs=1e-9)


def test_error_contract():
    with pytest.raises(std.StatisticsError):
        faststats.fmean([])
    with pytest.raises(std.StatisticsError):
        faststats.median([])
    with pytest.raises(std.StatisticsError):
        faststats.stdev([1.0])   # needs >= 2
    with pytest.raises(std.StatisticsError):
        faststats.variance([1.0])


def test_accepts_generators_and_ints():
    assert faststats.fmean(x for x in [2, 4, 6]) == pytest.approx(4.0)
    assert faststats.median([3, 1, 2]) == pytest.approx(2.0)
