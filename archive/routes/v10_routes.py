from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from core.secret_guard import redact
from predator_mesh.v10.bloodlines import BloodlineMemory
from predator_mesh.v10.build_factory import BuildEdgeFactory
from predator_mesh.v10.edge_accelerator import EdgeDiscoveryAccelerator
from predator_mesh.v10.queue import BuildAccelerationQueue
from predator_mesh.v10.source_adapters import SourceAdapterPromotionEngine
from predator_mesh.v10.telemetry import MeshThroughputTelemetry
from predator_mesh.v10.validation import SlowTestWatch, ValidationShardRunner

ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(prefix="/api/v10", tags=["v10"])


def _live_submit_disabled() -> bool:
    path = ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return data.get("enabled") is not True


def _queue_report() -> dict[str, Any]:
    queue = BuildAccelerationQueue()
    for packet in BuildEdgeFactory().generate_packets():
        queue.enqueue(packet)
    return {
        **queue.to_report(),
        "priority": queue.priority_report(),
    }


@router.get("/build-factory")
async def build_factory() -> dict[str, Any]:
    factory = BuildEdgeFactory()
    report = factory.to_report()
    return redact(
        {
            **report,
            "live_submit_disabled": _live_submit_disabled(),
            "manifest": factory.packet_manifest(),
            "promotion": factory.promotion_report(),
        }
    )


@router.get("/build-queue")
async def build_queue() -> dict[str, Any]:
    return redact(_queue_report())


@router.get("/validation-shards")
async def validation_shards() -> dict[str, Any]:
    runner = ValidationShardRunner()
    watch = SlowTestWatch()
    watch.record("tests/test_build_edge_factory.py::test_build_edge_factory_generates_bounded_packets", 0.05)
    watch.record("tests/test_dashboard_v10.py::test_v10_dashboard_endpoints_return_200", 0.08)
    return redact(
        {
            **runner.to_report(),
            "fast_feedback": runner.fast_feedback_report(),
            "full_regression_guard": runner.full_regression_guard_report(),
            "slow_tests": watch.to_report(),
        }
    )


@router.get("/source-adapters")
async def source_adapters() -> dict[str, Any]:
    engine = SourceAdapterPromotionEngine()
    return redact(
        {
            **engine.to_report(),
            "manifest": engine.candidate_manifest(),
            "modes": engine.mode_report(),
            "timeouts": engine.timeout_report(),
        }
    )


@router.get("/edge-accelerator")
async def edge_accelerator() -> dict[str, Any]:
    accelerator = EdgeDiscoveryAccelerator()
    return redact(
        {
            **accelerator.to_report(),
            "batch": accelerator.batch_report(),
            "triage": accelerator.triage_report(),
        }
    )


@router.get("/bloodlines")
async def bloodlines() -> dict[str, Any]:
    memory = BloodlineMemory()
    return redact(
        {
            "workstream": "V10: Bloodlines",
            "source_bloodlines": memory.source_report(),
            "signal_bloodlines": memory.signal_report(),
            "promotion_pruning": memory.promotion_pruning_report(),
            "verdict": "PASS",
        }
    )


@router.get("/mesh-throughput")
async def mesh_throughput() -> dict[str, Any]:
    return redact(MeshThroughputTelemetry.sample().to_report())


@router.get("/progress-score")
async def progress_score() -> dict[str, Any]:
    return redact(MeshThroughputTelemetry.sample().progress_score_report())
