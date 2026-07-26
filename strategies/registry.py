"""Single truthful catalog for the legacy research-strategy surface.

These strategies can produce research proposals in the strategy-intelligence
lane. They are not the canonical autonomy forecaster and have no execution
authority. The prior constant-abstention modules are deleted; non-predictive
repo-derived implementations remain visible here only as DORMANT rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from strategies.probability_disagreement import ProbabilityDisagreement
from strategies.repo_derived import (
    CommoditiesEnergyStrategy,
    CryptoEventMarketStrategy,
    KalshiWeatherForecastStrategy,
    OrderbookSpreadCaptureStrategy,
    RepoDerivedCrossMarketArbitrage,
    SportsMomentumStrategy,
    StaleQuoteDetectionStrategy,
    StockMacroMomentumStrategy,
)

StrategyLifecycle = Literal["RESEARCH_ONLY", "DORMANT"]


@dataclass(frozen=True)
class StrategyCatalogEntry:
    name: str
    implementation: object
    source: Literal["local", "repo_derived"]
    lifecycle_status: StrategyLifecycle
    prediction_authority: bool
    execution_authority: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "implementation": (
                f"{self.implementation.__class__.__module__}."
                f"{self.implementation.__class__.__name__}"
            ),
            "source": self.source,
            "lifecycle_status": self.lifecycle_status,
            "prediction_authority": self.prediction_authority,
            "execution_authority": self.execution_authority,
            "reason": self.reason,
        }


def has_prediction_authority(strategy: object) -> bool:
    """Return whether a strategy may be evaluated for a research proposal."""

    return (
        not bool(getattr(strategy, "DATA_ONLY", False))
        and getattr(strategy, "PREDICTION_AUTHORITY", None) is True
        and getattr(strategy, "EXECUTION_AUTHORITY", False) is False
    )


def _entry(strategy: object, *, source: Literal["local", "repo_derived"]) -> StrategyCatalogEntry:
    prediction_authority = has_prediction_authority(strategy)
    reason = (
        "prediction_authorized_research_strategy_not_an_execution_path"
        if prediction_authority
        else str(
            getattr(strategy, "QUARANTINE_REASON", None)
            or (
                "data_only_no_prediction_authority"
                if bool(getattr(strategy, "DATA_ONLY", False))
                else "prediction_authority_not_granted"
            )
        )
    )
    return StrategyCatalogEntry(
        name=str(getattr(strategy, "name", strategy.__class__.__name__)),
        implementation=strategy,
        source=source,
        lifecycle_status="RESEARCH_ONLY" if prediction_authority else "DORMANT",
        prediction_authority=prediction_authority,
        execution_authority=False,
        reason=reason,
    )


STRATEGY_CATALOG: tuple[StrategyCatalogEntry, ...] = (
    _entry(ProbabilityDisagreement(), source="local"),
    _entry(KalshiWeatherForecastStrategy(), source="repo_derived"),
    _entry(SportsMomentumStrategy(), source="repo_derived"),
    _entry(CryptoEventMarketStrategy(), source="repo_derived"),
    _entry(StockMacroMomentumStrategy(), source="repo_derived"),
    _entry(CommoditiesEnergyStrategy(), source="repo_derived"),
    _entry(RepoDerivedCrossMarketArbitrage(), source="repo_derived"),
    _entry(OrderbookSpreadCaptureStrategy(), source="repo_derived"),
    _entry(StaleQuoteDetectionStrategy(), source="repo_derived"),
)

# Compatibility collections are derived from the catalog, never maintained as
# parallel hand-written inventories.
REPO_DERIVED_STRATEGIES = [
    entry.implementation
    for entry in STRATEGY_CATALOG
    if entry.source == "repo_derived"
]
STRATEGIES = [
    entry.implementation
    for entry in STRATEGY_CATALOG
    if entry.lifecycle_status == "RESEARCH_ONLY"
]

ACTIVE_REPO_DERIVED_FAMILY_NAMES = tuple(
    entry.name
    for entry in STRATEGY_CATALOG
    if entry.source == "repo_derived"
    and entry.lifecycle_status == "RESEARCH_ONLY"
)
ACTIVE_REPO_DERIVED_FAMILY_COUNT = len(ACTIVE_REPO_DERIVED_FAMILY_NAMES)


def get_repo_derived_strategies() -> list[object]:
    """Return repo-derived research strategies with prediction authority."""

    return [
        entry.implementation
        for entry in STRATEGY_CATALOG
        if entry.source == "repo_derived"
        and entry.lifecycle_status == "RESEARCH_ONLY"
    ]


def strategy_catalog_payload() -> dict[str, Any]:
    """Serialize catalog truth without exposing live strategy objects."""

    rows = [entry.as_dict() for entry in STRATEGY_CATALOG]
    return {
        "catalog_status": "RESEARCH_ONLY_NO_EXECUTION_AUTHORITY",
        "strategy_count": len(rows),
        "research_only_count": sum(
            row["lifecycle_status"] == "RESEARCH_ONLY" for row in rows
        ),
        "dormant_count": sum(row["lifecycle_status"] == "DORMANT" for row in rows),
        "execution_authority_count": 0,
        "strategies": rows,
    }


__all__ = [
    "ACTIVE_REPO_DERIVED_FAMILY_COUNT",
    "ACTIVE_REPO_DERIVED_FAMILY_NAMES",
    "REPO_DERIVED_STRATEGIES",
    "STRATEGIES",
    "STRATEGY_CATALOG",
    "StrategyCatalogEntry",
    "get_repo_derived_strategies",
    "has_prediction_authority",
    "strategy_catalog_payload",
]
