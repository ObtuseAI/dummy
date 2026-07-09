from __future__ import annotations

from predator_mesh.v10.validation import SlowTestWatch


def test_slow_test_watch_ranks_slowest_tests() -> None:
    watch = SlowTestWatch()
    watch.record("test_a", 1.0)
    watch.record("test_b", 3.0)
    report = watch.to_report(limit=1)
    assert report["verdict"] == "PASS"
    assert report["slowest_tests"][0]["nodeid"] == "test_b"
    assert report["slowest_tests"][0]["duration_s"] == 3.0
