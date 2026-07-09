from abc import ABC, abstractmethod
from core.ontology import Forecast


class DummyAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def to_native_forecast(self, raw) -> Forecast:
        ...


# Compatibility alias for legacy pre-rename artifact readers.
DumbyAdapter = DummyAdapter
