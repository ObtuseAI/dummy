from __future__ import annotations


def test_report_chain_runtime_profiler_keeps_chain_finite() -> None:
    from predator_mesh.v19.runtime import ReportChainRuntimeProfiler

    report = ReportChainRuntimeProfiler().to_report()
    assert report["verdict"] == "PASS"
    assert report["report_chain_finite"] is True
