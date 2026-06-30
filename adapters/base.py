from abc import ABC, abstractmethod
from core.ontology import Forecast


class DumbyAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def to_native_forecast(self, raw) -> Forecast:
        ...
