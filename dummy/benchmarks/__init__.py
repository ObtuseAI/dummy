"""DUMMY vNext canonical benchmark program."""

from dummy.benchmarks.catalog import (
    BenchmarkDomain,
    BenchmarkMetric,
    benchmark_catalog,
    benchmark_catalog_manifest,
)

__all__ = [
    "BenchmarkDomain",
    "BenchmarkMetric",
    "benchmark_catalog",
    "benchmark_catalog_manifest",
]
