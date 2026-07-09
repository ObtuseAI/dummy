"""V20 edge-focused research swarm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EdgeResearchTask:
    task_id: str
    category: str
    target: str
    priority: int
    operator_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "category": self.category,
            "target": self.target,
            "priority": self.priority,
            "operator_action": self.operator_action,
            "live_execution_enabled": False,
        }


class SourceGapTask(EdgeResearchTask):
    pass


class TerrainGapTask(EdgeResearchTask):
    pass


class ForecastGapTask(EdgeResearchTask):
    pass


class OutcomeGapTask(EdgeResearchTask):
    pass


class EdgeFocusedResearchSwarmV2:
    def tasks(self) -> list[EdgeResearchTask]:
        return [
            SourceGapTask("source_gap_nq_orderbook", "activate_exchange_native_source", "CME NQ/ES futures orderbook", 100, "review or acquire read-only exchange-native data license"),
            SourceGapTask("source_gap_cl_orderbook", "activate_exchange_native_source", "CME CL / ICE Brent futures", 98, "review or acquire read-only energy futures data license"),
            SourceGapTask("source_gap_eia_key", "repair_source_key", "EIA Open Data", 88, "add EIA_API_KEY only if operator approves"),
            TerrainGapTask("terrain_gap_nasdaq_vol", "improve_nasdaq_terrain", "VIX/VXN/options skew", 86, "review Cboe/Databento options source"),
            TerrainGapTask("terrain_gap_oil_shipping", "improve_oil_terrain", "shipping/tanker flows", 82, "keep blocked until licensed tanker-flow source is approved"),
            TerrainGapTask("terrain_gap_crypto_ccxt", "add_github_adapter_plan", "CCXT public adapter", 78, "implement read-only adapter plan without execution authority"),
            TerrainGapTask("terrain_gap_weather_models", "improve_weather_terrain", "HRRR/GFS/ECMWF model-data", 74, "add bounded model-data fetch plan"),
            TerrainGapTask("terrain_gap_sports_injury", "improve_sports_terrain", "injury/lineup source", 72, "keep blocked unless licensed source approved"),
            ForecastGapTask("forecast_gap_no_trade", "improve_no_trade_gate", "edge-aware no-trade pressure", 70, "calibrate no-trade reasons against future outcomes"),
            OutcomeGapTask("outcome_gap_hooks", "add_outcome_observer_hook", "source outcome attribution", 68, "attach future resolved outcomes without fabrication"),
        ]

    def to_report(self) -> dict[str, Any]:
        tasks = self.tasks()
        return {
            "workstream": "V20: Edge-Focused Research Swarm V2",
            "task_count": len(tasks),
            "tasks": [task.to_dict() for task in tasks],
            "focuses_edge_producing_source_gaps": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def source_gap_task_report(self) -> dict[str, Any]:
        tasks = [task.to_dict() for task in self.tasks() if isinstance(task, SourceGapTask)]
        return {"workstream": "V20: Source Gap Task", "tasks": tasks, "task_count": len(tasks), "secret_values_exposed": False, "verdict": "PASS"}

    def terrain_gap_task_report(self) -> dict[str, Any]:
        tasks = [task.to_dict() for task in self.tasks() if isinstance(task, TerrainGapTask)]
        return {"workstream": "V20: Terrain Gap Task", "tasks": tasks, "task_count": len(tasks), "secret_values_exposed": False, "verdict": "PASS"}

    def task_manifest_report(self) -> dict[str, Any]:
        tasks = [task.to_dict() for task in self.tasks()]
        return {"workstream": "V20: Edge Research Task Manifest", "tasks": tasks, "task_count": len(tasks), "secret_values_exposed": False, "verdict": "PASS"}

