"""One inert implementation for every DORMANT harvested adapter candidate."""

from __future__ import annotations

from typing import Any, Mapping

from adapters.base import DummyAdapter
from core.ontology import Forecast
from repo_harvester.lifecycle import DORMANT, DORMANT_TEST_STATUS


class PendingAdapter(DummyAdapter):
    """Fail-closed placeholder for DORMANT metadata without verified integration.

    A DORMANT candidate is not a source adapter. It performs no import of the
    harvested project, emits no forecast, and has no prediction or execution
    authority.  Keeping one implementation prevents dozens of generated
    modules from masquerading as distinct capabilities.
    """

    LIFECYCLE_STATUS = DORMANT
    INTEGRATION_STATUS = DORMANT
    TEST_STATUS = DORMANT_TEST_STATUS
    UPSTREAM_INTEGRATION_VERIFIED = False
    PRODUCTION_CAPABILITY = False
    PREDICTION_AUTHORITY = False
    EXECUTION_AUTHORITY = False

    def __init__(
        self,
        name: str,
        *,
        category: str | None = None,
        data_only: bool = False,
        passthrough_model_zoo: bool = False,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("pending adapter name is required")
        self.name = name.strip()
        self.CATEGORY = category
        self.DATA_ONLY = bool(data_only)
        self.PASSTHROUGH_MODEL_ZOO = bool(passthrough_model_zoo)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PendingAdapter":
        return cls(
            str(record.get("adapter_name") or ""),
            category=(
                str(record["category"])
                if record.get("category") is not None
                else None
            ),
            data_only=bool(record.get("data_only")),
            passthrough_model_zoo=bool(record.get("passthrough_model_zoo")),
        )

    def to_native_forecast(self, raw: Any) -> Forecast | None:
        del raw
        return None


__all__ = ["PendingAdapter"]
