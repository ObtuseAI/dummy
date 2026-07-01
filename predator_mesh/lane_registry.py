"""Registry of all mesh lanes."""

from __future__ import annotations

from typing import Any

from predator_mesh.lanes.anomaly_mining import AnomalyMiningLane
from predator_mesh.lanes.base import BaseLane
from predator_mesh.lanes.calibration import CalibrationLane
from predator_mesh.lanes.firewall_rehearsal import FirewallRehearsalLane
from predator_mesh.lanes.forecast_update import ForecastUpdateLane
from predator_mesh.lanes.kalshi_terrain import KalshiTerrainLane
from predator_mesh.lanes.mesh_health import MeshHealthLane
from predator_mesh.lanes.recursive_inflow import RecursiveDataInflowLane
from predator_mesh.lanes.signal_normalization import SignalNormalizationLane
from predator_mesh.lanes.strategy_governor import StrategyGovernorLane
from predator_mesh.lanes.strategy_intelligence import StrategyIntelligenceLane


LANE_REGISTRY: dict[str, type[BaseLane]] = {
    "kalshi_terrain": KalshiTerrainLane,
    "recursive_inflow": RecursiveDataInflowLane,
    "signal_normalization": SignalNormalizationLane,
    "anomaly_mining": AnomalyMiningLane,
    "forecast_update": ForecastUpdateLane,
    "strategy_intelligence": StrategyIntelligenceLane,
    "strategy_governor": StrategyGovernorLane,
    "firewall_rehearsal": FirewallRehearsalLane,
    "calibration": CalibrationLane,
    "mesh_health": MeshHealthLane,
}


def build_default_lanes() -> list[BaseLane]:
    """Instantiate one of each registered lane."""
    return [lane_cls() for lane_cls in LANE_REGISTRY.values()]
